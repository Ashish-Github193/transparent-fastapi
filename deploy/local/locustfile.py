from locust import HttpUser, between, task


class AsyncSleepUser(HttpUser):
    wait_time = between(0, 0)

    @task
    def hit(self) -> None:
        self.client.get("/sleep-async?seconds=0.5", name="/sleep-async")


class SyncSleepUser(HttpUser):
    wait_time = between(0, 0)

    @task
    def hit(self) -> None:
        self.client.get("/sleep-sync?seconds=0.5", name="/sleep-sync")
