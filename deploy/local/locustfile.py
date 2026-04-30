import random

from locust import HttpUser, between, task


class _BaseTrafficUser(HttpUser):
    """Shared task mix that mimics a real production app.

    Most traffic is cheap reads with the occasional slow async I/O, sync
    threadpool call, fire-and-forget background task, or 5xx — the same
    proportions you'd see on a typical web service. Subclasses differ only
    in `wait_time`, which is what dials the per-user request rate.
    """

    abstract = True

    @task(50)
    def hello(self) -> None:
        self.client.get("/hello", name="/hello")

    @task(20)
    def item_lookup(self) -> None:
        # Each request uses a random item_id from a 100k-wide space. Without
        # the route-template collapse this would explode the `route` label
        # cardinality; with it, all 20% of traffic lands on a single series
        # `route="/items/{item_id}"`.
        item_id = random.randint(1, 100_000)
        self.client.get(f"/items/{item_id}", name="/items/{item_id}")

    @task(12)
    def slow_async(self) -> None:
        # Mimics an awaited DB / HTTP call; durations span fast hits and tail.
        seconds = random.uniform(0.05, 0.4)
        self.client.get(
            f"/sleep-async?seconds={seconds:.3f}", name="/sleep-async"
        )

    @task(8)
    def cpu_like(self) -> None:
        # Sync `def` route — Starlette runs it in the threadpool. Stand-in for
        # any blocking sync call (legacy SDK, image resize, etc.).
        seconds = random.uniform(0.05, 0.2)
        self.client.get(
            f"/threadpool?seconds={seconds:.3f}", name="/threadpool"
        )

    @task(5)
    def notify(self) -> None:
        # Schedules 2 cheap background tasks. Kept short so completions keep
        # up with schedules under medium load.
        seconds = random.uniform(0.02, 0.1)
        self.client.post(f"/notify?seconds={seconds:.3f}", name="/notify")

    @task(2)
    def boom(self) -> None:
        # ~2% of traffic fails. Locust shouldn't flag the 500 as a test failure.
        with self.client.get(
            "/boom", name="/boom", catch_response=True
        ) as response:
            if response.status_code == 500:
                response.success()


class MediumLoadUser(_BaseTrafficUser):
    """Steady-state load: human-like think time, ~25 rps with 50 users.

    Every panel stays populated; nothing saturates. Tune via LOCUST_MEDIUM_USERS.
    """

    wait_time = between(0.5, 3.0)


class HighLoadUser(_BaseTrafficUser):
    """Aggressive but realistic: same ratios, much shorter think time.

    Defaults give ~570 rps with 100 users — visible threadpool draw, climbing
    bg-task backlog, and tail-latency spread. Tune via LOCUST_HIGH_USERS.
    """

    wait_time = between(0.05, 0.3)
