import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateTest,
    CandidateTestAnswer,
    QuestionRevision,
    QuestionType,
)


def test_submit_answer_for_qr_candidate(
    client: TestClient,
    test_db: Session,
    test_candidate: Candidate,
    test_candidate_test: CandidateTest,
    test_question_revision: QuestionRevision,
):
    """Test submitting a single answer"""
    answer_request = {
        "question_revision_id": test_question_revision.id,
        "response": "1",
        "visited": True,
        "time_spent": 30,
    }

    response = client.post(
        f"/api/candidate/submit_answer/{test_candidate_test.id}",
        json=answer_request,
        params={"candidate_uuid": str(test_candidate.identity)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question_revision_id"] == test_question_revision.id
    assert data["response"] == "1"
    assert data["visited"] is True
    assert data["time_spent"] == 30

    # Verify answer in database
    answer = test_db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == test_candidate_test.id)
        .where(CandidateTestAnswer.question_revision_id == test_question_revision.id)
    ).first()
    assert answer.response == "1"
    assert answer.visited is True
    assert answer.time_spent == 30


def test_submit_batch_answers_for_qr_candidate(
    client: TestClient,
    test_db: Session,
    test_candidate: Candidate,
    test_candidate_test: CandidateTest,
    test_question_revision: QuestionRevision,
):
    """Test submitting multiple answers at once"""
    # Create a second question revision for testing
    second_question_revision = QuestionRevision(
        question_id=test_question_revision.question_id,
        question_text="Second test question",
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1", "value": "1"}],
        created_by_id=1,
    )
    test_db.add(second_question_revision)
    test_db.commit()
    test_db.refresh(second_question_revision)

    # Prepare batch request
    batch_request = {
        "answers": [
            {
                "question_revision_id": test_question_revision.id,
                "response": "1",
                "visited": True,
                "time_spent": 30,
            },
            {
                "question_revision_id": second_question_revision.id,
                "response": "1",
                "visited": True,
                "time_spent": 45,
            },
        ]
    }

    # Submit batch answers
    response = client.post(
        f"/api/candidate/submit_answers/{test_candidate_test.id}",
        json=batch_request,
        params={"candidate_uuid": str(test_candidate.identity)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Verify first answer
    assert data[0]["question_revision_id"] == test_question_revision.id
    assert data[0]["response"] == "1"
    assert data[0]["visited"] is True
    assert data[0]["time_spent"] == 30

    # Verify second answer
    assert data[1]["question_revision_id"] == second_question_revision.id
    assert data[1]["response"] == "1"
    assert data[1]["visited"] is True
    assert data[1]["time_spent"] == 45

    # Verify answers in database
    answers = test_db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == test_candidate_test.id)
        .order_by(CandidateTestAnswer.question_revision_id)
    ).all()
    assert len(answers) == 2
    assert answers[0].response == "1"
    assert answers[1].response == "1"


def test_submit_batch_answers_invalid_uuid(
    client: TestClient,
    test_candidate_test: CandidateTest,
):
    """Test submitting batch answers with invalid UUID"""
    batch_request = {
        "answers": [
            {
                "question_revision_id": 1,
                "response": "1",
                "visited": True,
                "time_spent": 30,
            }
        ]
    }

    response = client.post(
        f"/api/candidate/submit_answers/{test_candidate_test.id}",
        json=batch_request,
        params={"candidate_uuid": str(uuid.uuid4())},  # Random UUID
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate test not found or invalid UUID"


def test_submit_batch_answers_empty_list(
    client: TestClient,
    test_candidate: Candidate,
    test_candidate_test: CandidateTest,
):
    """Test submitting empty batch answers list"""
    batch_request = {"answers": []}

    response = client.post(
        f"/api/candidate/submit_answers/{test_candidate_test.id}",
        json=batch_request,
        params={"candidate_uuid": str(test_candidate.identity)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_submit_batch_answers_update_existing(
    client: TestClient,
    test_db: Session,
    test_candidate: Candidate,
    test_candidate_test: CandidateTest,
    test_question_revision: QuestionRevision,
):
    """Test updating existing answers in batch"""
    # Create initial answer
    initial_answer = CandidateTestAnswer(
        candidate_test_id=test_candidate_test.id,
        question_revision_id=test_question_revision.id,
        response="2",
        visited=True,
        time_spent=20,
    )
    test_db.add(initial_answer)
    test_db.commit()

    # Prepare batch request to update the answer
    batch_request = {
        "answers": [
            {
                "question_revision_id": test_question_revision.id,
                "response": "1",
                "visited": True,
                "time_spent": 30,
            }
        ]
    }

    # Submit batch answers
    response = client.post(
        f"/api/candidate/submit_answers/{test_candidate_test.id}",
        json=batch_request,
        params={"candidate_uuid": str(test_candidate.identity)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["response"] == "1"
    assert data[0]["time_spent"] == 30

    # Verify answer was updated in database
    answer = test_db.get(CandidateTestAnswer, initial_answer.id)
    assert answer.response == "1"
    assert answer.time_spent == 30
