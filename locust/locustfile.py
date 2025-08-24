# locust/locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    # This specifies the time range (in seconds) that a simulated user will wait
    # between completing two tasks. This helps simulate more realistic user behavior.
    wait_time = between(1, 2.5)

    @task(3) # This task will be called 3 times more often than the /health task
    def get_data(self):
        """
        Simulates a user requesting data from the /api/data endpoint.
        This endpoint is designed to generate metrics, logs, and traces,
        including simulated errors.
        """
        self.client.get("/api/data", name="/api/data")

    @task(1) # This task will be called 1 time for every 3 calls to /api/data
    def get_health(self):
        """
        Simulates a user requesting the health check endpoint.
        This is a simple successful request.
        """
        self.client.get("/health", name="/health")
