import logging

from locust import HttpUser, events, task
from locust.exception import StopUser


@events.init_command_line_parser.add_listener
def add_arguments(parser, **kwargs):
    parser.add_argument(
        "--test-link-uuid",
        type=str,
        required=True,
        help="UUID of the test link. "
        "Requirements: active test, start_time in the past, no org time-window, "
        "no mandatory form, no mandatory questions (else submit_test returns 400).",
    )


class SubmitTestUser(HttpUser):
    def on_start(self):
        # Setup call, not measured: create a candidate test to submit below.
        response = self.client.post(
            "/api/v1/candidate/start_test",
            json={
                "test_link_uuid": self.environment.parsed_options.test_link_uuid,
                "device_info": "locust-loadtest",
            },
        )
        if response.status_code != 200:
            logging.error(
                "start_test failed (%s): %s", response.status_code, response.text
            )
            raise StopUser()

        data = response.json()
        self.candidate_uuid = data["candidate_uuid"]
        self.candidate_test_id = data["candidate_test_id"]

    @task
    def submit_test(self):
        self.client.post(
            f"/api/v1/candidate/submit_test/{self.candidate_test_id}",
            params={"candidate_uuid": str(self.candidate_uuid)},
            name="/api/v1/candidate/submit_test/[candidate_test_id]",
        )
        raise StopUser()
