from locust import HttpUser, task, between

# Replace with a valid test_link_uuid from the DB
# Requirements: active test, start_time in the past, no org time-window, no mandatory form
TEST_LINK_UUID = "4f87e1f0-d800-456f-b07f-3ee4af97ff6b"


class StartTestUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def start_test(self):
        self.client.post(
            "/api/v1/candidate/start_test",
            json={
                "test_link_uuid": TEST_LINK_UUID,
                "device_info": "locust-loadtest",
            },
        )
