import random

from locust import HttpUser, between, events, task
from locust.exception import StopUser


@events.init_command_line_parser.add_listener
def add_arguments(parser, **kwargs):
    parser.add_argument(
        "--test-link-uuid",
        type=str,
        required=True,
        help="UUID of the test link. "
        "Requirements: active test, start_time in the past, no org time-window, no mandatory form.",
    )


class ExamUser(HttpUser):
    wait_time = between(1, 3)  # simulates time taken per question

    def on_start(self):
        # Step 1: start the test
        response = self.client.post(
            "/api/v1/candidate/start_test",
            json={
                "test_link_uuid": self.environment.parsed_options.test_link_uuid,
                "device_info": "locust-loadtest",
            },
        )
        if response.status_code != 200:
            raise StopUser()

        data = response.json()
        self.candidate_uuid = data["candidate_uuid"]
        self.candidate_test_id = data["candidate_test_id"]

        # Step 2: fetch questions for this candidate test
        questions_response = self.client.get(
            f"/api/v1/candidate/test_questions/{self.candidate_test_id}",
            params={"candidate_uuid": self.candidate_uuid},
        )
        if questions_response.status_code != 200:
            raise StopUser()

        question_revisions = questions_response.json().get("question_revisions", [])
        question_ids = [q["id"] for q in question_revisions]

        # each candidate answers in random order
        random.shuffle(question_ids)
        self.questions = question_ids
        self.question_index = 0

    @task
    def submit_answer(self):
        if self.question_index >= len(self.questions):
            raise StopUser()

        question_revision_id = self.questions[self.question_index]
        self.question_index += 1

        self.client.post(
            f"/api/v1/candidate/submit_answer/{self.candidate_test_id}",
            params={"candidate_uuid": str(self.candidate_uuid)},
            json={
                "question_revision_id": question_revision_id,
                "response": "[1]",
                "visited": True,
                "bookmarked": False,
                "time_spent": random.randint(10, 120),
            },
        )
