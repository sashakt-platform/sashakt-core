from app.models.candidate import CandidateTest


def get_time_taken_seconds(candidate_test: CandidateTest) -> int | None:
    if candidate_test.start_time and candidate_test.end_time:
        return int(
            (candidate_test.end_time - candidate_test.start_time).total_seconds()
        )
    return None
