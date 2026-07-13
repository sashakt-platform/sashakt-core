from locust import HttpUser, task, between, events


@events.init_command_line_parser.add_listener
def add_arguments(parser, **kwargs):
    parser.add_argument(
        "--test-link-uuid",
        type=str,
        required=True,
        help="UUID of the test link to use for load testing. "
        "Requirements: active test, start_time in the past, no org time-window, no mandatory form.",
    )


class StartTestUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def start_test(self):
        self.client.post(
            "/api/v1/candidate/start_test",
            json={
                "test_link_uuid": self.environment.parsed_options.test_link_uuid,
                "device_info": "locust-loadtest",
            },
        )
