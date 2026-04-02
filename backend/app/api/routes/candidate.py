import json
import random
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import and_, col, not_, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.api.routes.question import (
    enrich_media_with_signed_urls,
    enrich_options_with_signed_urls,
    get_gcs_service_for_org,
)
from app.api.routes.utils import get_current_time
from app.core.certificate_token import generate_certificate_token
from app.core.config import TOLERANCE
from app.core.question_sets import (
    build_assigned_question_membership,
    build_question_set_id_map,
    get_effective_marking_scheme,
    group_question_ids_by_set,
    is_attempted_response,
    is_sectioned_test,
    normalize_question_set_ids,
)
from app.core.roles import state_admin, test_admin
from app.core.timezone import get_timezone_aware_now
from app.models import (
    BatchAnswerSubmitRequest,
    Candidate,
    CandidateAnswerSubmitRequest,
    CandidateCreate,
    CandidatePublic,
    CandidateTest,
    CandidateTestAnswer,
    CandidateTestAnswerCreate,
    CandidateTestAnswerFeedback,
    CandidateTestAnswerPublic,
    CandidateTestAnswerUpdate,
    CandidateTestCreate,
    CandidateTestPublic,
    CandidateTestUpdate,
    CandidateUpdate,
    Message,
    QuestionCandidatePublic,
    QuestionRevision,
    QuestionSet,
    QuestionSetCandidatePublic,
    Test,
    TestCandidatePublic,
    TestQuestion,
)
from app.models.candidate import (
    CandidateReviewResponse,
    OverallTestAnalyticsResponse,
    Result,
    StartTestRequest,
    StartTestResponse,
    TestStatusSummary,
)
from app.models.form import FormResponse
from app.models.question import Question, QuestionTag, QuestionType
from app.models.tag import Tag
from app.models.test import OMRMode, TestDistrict, TestState, TestTag
from app.models.user import User
from app.models.utils import MarkingScheme, TimeLeft
from app.services.certificate_tokens import resolve_form_response_values

router = APIRouter(prefix="/candidate", tags=["Candidate"])
router_candidate_test = APIRouter(prefix="/candidate_test", tags=["Candidate Test"])
router_candidate_test_answer = APIRouter(
    prefix="/candidate_test_answer", tags=["Candidate-Test Answer"]
)


def validate_subjective_answer_limit(
    answer_limit: int,
    response: str | None,
) -> None:
    """
    Validates the response length for a subjective question.
    Assumes answer_limit is provided (not None).
    """
    if response and len(response) > answer_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Answer exceeds character limit of "
                f"{answer_limit}. "
                f"Current length: {len(response)}"
            ),
        )


def is_candidate_test_expired(
    session: SessionDep, candidate_test: CandidateTest
) -> bool:
    if not candidate_test or not candidate_test.start_time:
        return False
    test = session.get(Test, candidate_test.test_id)
    if not test:
        return False

    time_now = get_timezone_aware_now()

    if (test.end_time and time_now > test.end_time) or (
        test.time_limit
        and time_now > candidate_test.start_time + timedelta(minutes=test.time_limit)
    ):
        return True

    return False


def validate_question_response_format(
    response: Any, question_type: QuestionType
) -> Any:
    if response is None:
        return None

    if question_type not in (QuestionType.single_choice, QuestionType.multi_choice):
        return response

    parsed = json.loads(response)
    if question_type == QuestionType.single_choice:
        if (
            not isinstance(parsed, list)
            or len(parsed) != 1
            or not all(isinstance(x, int) for x in parsed)
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid Response Format. Kindly submit _Single-choice question_ as list of length 1 (e.g., [1])",
            )

        return json.dumps(parsed)
    elif question_type == QuestionType.multi_choice:
        if (
            not isinstance(parsed, list)
            or not all(isinstance(x, int) for x in parsed)
            or len(parsed) < 1
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid Response Format. Kindly submit _Multi-choice question_ as a list (e.g., [1, 2])",
            )

        return json.dumps(parsed)


def get_test_question_links(session: SessionDep, test_id: int) -> list[TestQuestion]:
    return list(
        session.exec(
            select(TestQuestion)
            .where(TestQuestion.test_id == test_id)
            .order_by(col(TestQuestion.id))
        ).all()
    )


def get_test_question_sets(session: SessionDep, test_id: int) -> list[QuestionSet]:
    return list(
        session.exec(
            select(QuestionSet)
            .where(QuestionSet.test_id == test_id)
            .order_by(col(QuestionSet.display_order), col(QuestionSet.id))
        ).all()
    )


def get_question_revisions_map(
    session: SessionDep, question_revision_ids: list[int]
) -> dict[int, QuestionRevision]:
    if not question_revision_ids:
        return {}
    question_revisions = session.exec(
        select(QuestionRevision).where(
            col(QuestionRevision.id).in_(question_revision_ids)
        )
    ).all()
    return {
        question_revision.id: question_revision
        for question_revision in question_revisions
        if question_revision.id is not None
    }


def get_persisted_test_id(test: Test) -> int:
    if test.id is None:
        raise HTTPException(status_code=500, detail="Test is missing a database id.")
    return test.id


def build_candidate_safe_question(
    question_revision: QuestionRevision,
    *,
    hide_question_text: bool,
    marking_scheme: MarkingScheme | None,
    gcs_service: Any | None = None,
) -> QuestionCandidatePublic:
    safe_options = enrich_options_with_signed_urls(
        question_revision.options, gcs_service
    )
    if hide_question_text and isinstance(question_revision.options, list):
        safe_options = []
        for option in question_revision.options:
            if isinstance(option, dict):
                option_id = option.get("id")
                option_key = option.get("key")
            else:
                option_id = getattr(option, "id", None)
                option_key = getattr(option, "key", None)

            if option_id is None and option_key is None:
                continue

            safe_options.append(
                {
                    "id": option_id,
                    "key": option_key,
                }
            )

    return QuestionCandidatePublic(
        id=question_revision.id,
        question_text=None if hide_question_text else question_revision.question_text,
        instructions=question_revision.instructions,
        question_type=question_revision.question_type,
        options=safe_options,
        subjective_answer_limit=question_revision.subjective_answer_limit,
        is_mandatory=question_revision.is_mandatory,
        media=enrich_media_with_signed_urls(question_revision.media, gcs_service),
        marking_scheme=marking_scheme,
    )


def build_candidate_question_payload(
    *,
    test: Test,
    candidate_test: CandidateTest,
    question_revisions_map: dict[int, QuestionRevision],
    question_sets_by_id: dict[int, QuestionSet],
    hide_question_text: bool,
    sectioned: bool,
    gcs_service: Any | None = None,
) -> tuple[list[QuestionCandidatePublic], list[QuestionSetCandidatePublic] | None]:
    ordered_question_ids = candidate_test.question_revision_ids
    normalized_question_set_ids = normalize_question_set_ids(
        ordered_question_ids, candidate_test.question_set_ids
    )
    question_set_id_by_revision = build_question_set_id_map(
        ordered_question_ids, normalized_question_set_ids
    )

    candidate_questions: list[QuestionCandidatePublic] = []
    candidate_questions_by_id: dict[int, QuestionCandidatePublic] = {}

    for question_revision_id in ordered_question_ids:
        question_revision = question_revisions_map.get(question_revision_id)
        if not question_revision:
            continue
        question_set = question_sets_by_id.get(
            question_set_id_by_revision.get(question_revision_id) or -1
        )
        safe_question = build_candidate_safe_question(
            question_revision,
            hide_question_text=hide_question_text,
            marking_scheme=get_effective_marking_scheme(
                test,
                question_revision,
                question_set=question_set,
                sectioned=sectioned,
            ),
            gcs_service=gcs_service,
        )
        candidate_questions.append(safe_question)
        candidate_questions_by_id[question_revision_id] = safe_question

    if not sectioned:
        return candidate_questions, None

    grouped_question_ids = group_question_ids_by_set(
        ordered_question_ids, normalized_question_set_ids
    )
    candidate_question_sets: list[QuestionSetCandidatePublic] = []
    fallback_display_order = max(
        [question_set.display_order for question_set in question_sets_by_id.values()],
        default=0,
    )

    for question_set in sorted(
        question_sets_by_id.values(),
        key=lambda item: (item.display_order, item.id or 0),
    ):
        question_ids = grouped_question_ids.pop(question_set.id, [])
        if not question_ids:
            continue
        candidate_question_sets.append(
            QuestionSetCandidatePublic(
                id=question_set.id,
                title=question_set.title,
                description=question_set.description,
                display_order=question_set.display_order,
                max_questions_allowed_to_attempt=question_set.max_questions_allowed_to_attempt,
                marking_scheme=question_set.marking_scheme,
                question_revisions=[
                    candidate_questions_by_id[question_id]
                    for question_id in question_ids
                    if question_id in candidate_questions_by_id
                ],
            )
        )

    for orphan_index, (question_set_id, question_ids) in enumerate(
        grouped_question_ids.items(), start=1
    ):
        if question_set_id is None or not question_ids:
            continue
        candidate_question_sets.append(
            QuestionSetCandidatePublic(
                id=question_set_id,
                title=f"Section {question_set_id}",
                description=None,
                display_order=fallback_display_order + orphan_index,
                max_questions_allowed_to_attempt=len(question_ids),
                marking_scheme=test.marking_scheme,
                question_revisions=[
                    candidate_questions_by_id[question_id]
                    for question_id in question_ids
                    if question_id in candidate_questions_by_id
                ],
            )
        )

    return candidate_questions, candidate_question_sets or None


def enforce_question_set_attempt_limit(
    session: SessionDep,
    *,
    candidate_test: CandidateTest,
    question_revision_id: int,
    response: str | None,
    existing_answer: CandidateTestAnswer | None,
) -> None:
    question_set_id_by_revision = build_question_set_id_map(
        candidate_test.question_revision_ids,
        candidate_test.question_set_ids,
    )
    question_set_id = question_set_id_by_revision.get(question_revision_id)
    if question_set_id is None:
        return

    question_set = session.get(QuestionSet, question_set_id)
    if not question_set:
        return

    if not is_attempted_response(response):
        return

    if existing_answer and is_attempted_response(existing_answer.response):
        return

    answers = session.exec(
        select(CandidateTestAnswer).where(
            CandidateTestAnswer.candidate_test_id == candidate_test.id
        )
    ).all()
    attempted_count = 0
    for answer in answers:
        if answer.question_revision_id == question_revision_id:
            continue
        if not is_attempted_response(answer.response):
            continue
        if (
            question_set_id_by_revision.get(answer.question_revision_id)
            == question_set_id
        ):
            attempted_count += 1

    if attempted_count >= question_set.max_questions_allowed_to_attempt:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum attempt limit reached for section '{question_set.title}'."
            ),
        )


def get_score_and_time(
    session: SessionDep, candidate_test: CandidateTest
) -> tuple[float, float, float]:
    """
    Returns total_score_obtained, total_max_score, total_time_minutes
    """
    test = session.get(Test, candidate_test.test_id)
    if not test:
        return 0.0, 0.0, 0.0
    test_id = get_persisted_test_id(test)

    answers_map = {
        ans.question_revision_id: ans
        for ans in session.exec(
            select(CandidateTestAnswer).where(
                CandidateTestAnswer.candidate_test_id == candidate_test.id
            )
        ).all()
    }
    test_questions = get_test_question_links(session, test_id)
    question_sets = get_test_question_sets(session, test_id)
    question_sets_by_id = {
        question_set.id: question_set
        for question_set in question_sets
        if question_set.id is not None
    }
    try:
        sectioned = is_sectioned_test(
            test_questions,
            question_sets_by_id,
            test_id=test_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    total_score_obtained = 0.0
    total_max_score = 0.0
    question_revisions = session.exec(
        select(QuestionRevision).where(
            col(QuestionRevision.id).in_(candidate_test.question_revision_ids)
        )
    ).all()
    question_rev_map = {q.id: q for q in question_revisions}
    question_set_id_by_revision = build_question_set_id_map(
        candidate_test.question_revision_ids,
        candidate_test.question_set_ids,
    )

    for q_id in candidate_test.question_revision_ids:
        question_rev = question_rev_map.get(q_id)
        if not question_rev:
            continue

        marking_scheme = get_effective_marking_scheme(
            test,
            question_rev,
            question_set=question_sets_by_id.get(
                question_set_id_by_revision.get(q_id) or -1
            ),
            sectioned=sectioned,
        )
        if not marking_scheme:
            continue

        total_max_score += marking_scheme.get("correct", 0.0)
        answer = answers_map.get(q_id)

        if answer is None or not is_attempted_response(answer.response):
            total_score_obtained += marking_scheme.get("skipped", 0.0)
        else:
            correct_answer = question_rev.correct_answer
            response_list = convert_to_list(answer.response)
            correct_list = convert_to_list(correct_answer)
            if set(response_list) == set(correct_list):
                total_score_obtained += marking_scheme.get("correct", 0.0)
            else:
                total_score_obtained += marking_scheme.get("wrong", 0.0)

    if candidate_test.start_time and candidate_test.end_time:
        time_diff = candidate_test.end_time - candidate_test.start_time
        total_time_minutes = time_diff.total_seconds() / 60.0
    else:
        total_time_minutes = 0.0

    return total_score_obtained, total_max_score, total_time_minutes


@router.get(
    "/overall-analytics",
    response_model=OverallTestAnalyticsResponse,
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_overall_tests_analytics(
    session: SessionDep,
    current_user: CurrentUser,
    tag_type_ids: list[int] | None = Query(None),
    state_ids: list[int] | None = Query(None),
    district_ids: list[int] | None = Query(None),
) -> OverallTestAnalyticsResponse:
    """
    Calculate overall average score and average test duration across all tests.
    """

    query = (
        select(CandidateTest)
        .join(Test)
        .where(
            Test.organization_id == current_user.organization_id,
            col(CandidateTest.end_time).is_not(None),
        )
    )

    current_user_state_ids: list[int] = []
    if (
        current_user.role.name == state_admin.name
        or current_user.role.name == test_admin.name
    ):
        current_user_state_ids = (
            [state.id for state in current_user.states if state.id is not None]
            if current_user.states
            else []
        )

    if current_user_state_ids:
        query = query.join(TestState).where(
            CandidateTest.test_id == TestState.test_id,
            col(TestState.state_id).in_(current_user_state_ids),
        )

    if tag_type_ids:
        query = query.join(TestTag).where(
            CandidateTest.test_id == TestTag.test_id,
            col(Tag.tag_type_id).in_(tag_type_ids),
        )

    if state_ids:
        query = query.join(TestState).where(
            CandidateTest.test_id == TestState.test_id,
            col(TestState.state_id).in_(state_ids),
        )

    if district_ids:
        query = query.join(TestDistrict).where(
            CandidateTest.test_id == TestDistrict.test_id,
            col(TestDistrict.district_id).in_(district_ids),
        )

    candidate_tests = session.exec(query).all()

    total_scores = 0.0
    total_possible_scores = 0.0
    total_time = 0.0
    unique_candidates = set()

    for ct in candidate_tests:
        score_obtained, max_score, time_min = get_score_and_time(session, ct)
        total_scores += score_obtained
        total_possible_scores += max_score
        total_time += time_min
        unique_candidates.add(ct.candidate_id)

    overall_score_percent = (
        (total_scores / total_possible_scores) * 100
        if total_possible_scores > 0
        else 0.0
    )

    overall_avg_time = total_time / len(candidate_tests) if candidate_tests else 0.0
    overall_avg_time = round(overall_avg_time, 2)

    return OverallTestAnalyticsResponse(
        total_candidates=len(unique_candidates),
        overall_score_percent=round(overall_score_percent, 2),
        overall_avg_time_minutes=overall_avg_time,
    )


@router.post("/start_test", response_model=StartTestResponse)
def start_test_for_candidate(
    session: SessionDep,
    start_test_request: StartTestRequest = Body(...),
) -> StartTestResponse:
    """
    Creates a candidate when they start a test, links them to the test.
    Returns the candidate UUID for verification.
    """
    # Find the test by ID
    test = session.get(Test, start_test_request.test_id)
    if not test or (test.is_active is False):
        raise HTTPException(status_code=404, detail="Test not found or not active")
    test_id = get_persisted_test_id(test)
    test_questions = get_test_question_links(session, test_id)
    question_sets = get_test_question_sets(session, test_id)
    question_sets_by_id = {
        question_set.id: question_set
        for question_set in question_sets
        if question_set.id is not None
    }
    try:
        sectioned = is_sectioned_test(
            test_questions,
            question_sets_by_id,
            test_id=test_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    selected_test_questions = list(test_questions)
    if test.random_questions and test.no_of_random_questions:
        selected_test_questions = random.sample(
            selected_test_questions,
            min(test.no_of_random_questions, len(selected_test_questions)),
        )

    question_revision_ids, question_set_ids = build_assigned_question_membership(
        selected_test_questions,
        question_sets_by_id if sectioned else None,
        shuffle_questions=test.shuffle,
    )

    if test.random_tag_count:
        extra_question_ids: set[int] = set()

        for tag_rule in test.random_tag_count:
            tag_id = tag_rule["tag_id"]
            count = tag_rule["count"]

            question_ids_for_tag = session.exec(
                select(Question.last_revision_id)
                .join(
                    QuestionTag,
                    and_(
                        Question.id == QuestionTag.question_id,
                        Question.is_active,
                    ),
                )
                .where(QuestionTag.tag_id == tag_id)
                .where(
                    not_(
                        col(Question.last_revision_id).in_(
                            extra_question_ids | set(question_revision_ids)
                        )
                    )
                )
            ).all()

            question_revision_ids_for_tag = [
                rev_id for rev_id in question_ids_for_tag if rev_id is not None
            ]

            chosen_question_revision_ids = random.sample(
                question_revision_ids_for_tag,
                min(len(question_revision_ids_for_tag), count),
            )
            extra_question_ids.update(chosen_question_revision_ids)

        existing_question_ids = set(question_revision_ids)
        ordered_extra_question_ids = [
            question_revision_id
            for question_revision_id in extra_question_ids
            if question_revision_id not in existing_question_ids
        ]
        question_revision_ids.extend(ordered_extra_question_ids)
        question_set_ids.extend([None] * len(ordered_extra_question_ids))

    if not sectioned and (test.shuffle or test.random_questions):
        combined = list(zip(question_revision_ids, question_set_ids, strict=False))
        random.shuffle(combined)
        question_revision_ids = [
            question_revision_id for question_revision_id, _ in combined
        ]
        question_set_ids = [question_set_id for _, question_set_id in combined]

    current_time = get_current_time()
    if test.start_time and test.start_time > current_time:
        raise HTTPException(
            status_code=400,
            detail="Test has not started yet. Please wait until the scheduled start time.",
        )

    # Create a new anonymous candidate with UUID
    candidate = Candidate(
        identity=uuid.uuid4(),  # Generate UUID for anonymous candidate
        organization_id=test.organization_id,
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    # Set start_time when test begins, end_time will be set when test is submitted
    start_time = get_timezone_aware_now()

    # Create CandidateTest link
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=start_test_request.device_info or "unknown",
        consent=True,
        start_time=start_time,
        end_time=None,  # Will be set when test is actually submitted
        is_submitted=False,
        question_revision_ids=question_revision_ids,
        question_set_ids=question_set_ids,
    )
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)

    # Handle form responses
    if start_test_request.form_responses and test.form_id:
        form_response = FormResponse(
            candidate_test_id=candidate_test.id,
            form_id=test.form_id,
            responses=start_test_request.form_responses,
        )
        session.add(form_response)
        session.commit()

    return StartTestResponse(
        candidate_uuid=candidate.identity,
        candidate_test_id=candidate_test.id,
    )


def verify_candidate_uuid_access(
    session: SessionDep, candidate_test_id: int, candidate_uuid: uuid.UUID
) -> CandidateTest:
    """Helper function to verify UUID-based access to candidate test."""
    candidate_test_statement = (
        select(CandidateTest)
        .join(Candidate)
        .where(CandidateTest.id == candidate_test_id)
        .where(Candidate.identity == candidate_uuid)
    )
    candidate_test = session.exec(candidate_test_statement).first()

    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="Candidate test not found or invalid UUID"
        )
    return candidate_test


@router.post(
    "/submit_answer/{candidate_test_id}", response_model=CandidateTestAnswerPublic
)
def submit_answer_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    answer_request: CandidateAnswerSubmitRequest = Body(...),
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> CandidateTestAnswerPublic:
    """
    Submit answer for QR code candidates using UUID authentication.
    Creates new answer or updates existing one.
    Returns the answer along with correct answer from question revision.
    """
    # Verify UUID access
    candidate_test = verify_candidate_uuid_access(
        session, candidate_test_id, candidate_uuid
    )
    question_revision = session.get(
        QuestionRevision, answer_request.question_revision_id
    )
    if not question_revision:
        raise HTTPException(status_code=404, detail="Question revision not found")
    if answer_request.question_revision_id not in candidate_test.question_revision_ids:
        raise HTTPException(
            status_code=403,
            detail="Question revision is not assigned to this candidate test.",
        )

    if (
        question_revision.question_type == QuestionType.subjective
        and question_revision.subjective_answer_limit is not None
    ):
        validate_subjective_answer_limit(
            answer_limit=question_revision.subjective_answer_limit,
            response=answer_request.response,
        )

    if question_revision:
        answer_request.response = validate_question_response_format(
            answer_request.response, question_revision.question_type
        )
    # Check if answer already exists for this question
    existing_answer = session.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .where(
            CandidateTestAnswer.question_revision_id
            == answer_request.question_revision_id
        )
    ).first()

    enforce_question_set_attempt_limit(
        session,
        candidate_test=candidate_test,
        question_revision_id=answer_request.question_revision_id,
        response=answer_request.response,
        existing_answer=existing_answer,
    )

    if existing_answer:
        if existing_answer.is_reviewed:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify answer after it has been reviewed",
            )
        # Update existing answer
        existing_answer.response = answer_request.response
        existing_answer.visited = answer_request.visited
        existing_answer.time_spent = answer_request.time_spent
        existing_answer.bookmarked = answer_request.bookmarked
        existing_answer.is_reviewed = answer_request.is_reviewed
        session.add(existing_answer)
        session.commit()
        session.refresh(existing_answer)
        saved_answer = existing_answer
    else:
        # Create new answer
        candidate_test_answer = CandidateTestAnswer(
            candidate_test_id=candidate_test_id,
            question_revision_id=answer_request.question_revision_id,
            response=answer_request.response,
            visited=answer_request.visited,
            time_spent=answer_request.time_spent,
            bookmarked=answer_request.bookmarked,
            is_reviewed=answer_request.is_reviewed,
        )
        session.add(candidate_test_answer)
        session.commit()
        session.refresh(candidate_test_answer)
        saved_answer = candidate_test_answer

    return CandidateTestAnswerPublic(
        id=saved_answer.id,
        candidate_test_id=saved_answer.candidate_test_id,
        question_revision_id=saved_answer.question_revision_id,
        response=saved_answer.response,
        visited=saved_answer.visited,
        time_spent=saved_answer.time_spent,
        bookmarked=saved_answer.bookmarked,
        created_date=saved_answer.created_date,
        modified_date=saved_answer.modified_date,
    )


@router.post(
    "/submit_answers/{candidate_test_id}",
    response_model=list[CandidateTestAnswerPublic],
)
def submit_batch_answers_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    batch_request: BatchAnswerSubmitRequest = Body(...),
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> list[CandidateTestAnswerPublic]:
    """
    Submit multiple answers for QR code candidates using UUID authentication.
    Creates new answers or updates existing ones in a single transaction.
    Returns answers along with correct answers from question revisions.
    """
    # Verify UUID access
    candidate_test = verify_candidate_uuid_access(
        session, candidate_test_id, candidate_uuid
    )

    question_revision_ids = [
        answer.question_revision_id for answer in batch_request.answers
    ]
    invalid_question_ids = [
        question_revision_id
        for question_revision_id in question_revision_ids
        if question_revision_id not in candidate_test.question_revision_ids
    ]
    if invalid_question_ids:
        raise HTTPException(
            status_code=403,
            detail="One or more question revisions are not assigned to this candidate test.",
        )
    question_revisions = session.exec(
        select(QuestionRevision).where(
            col(QuestionRevision.id).in_(question_revision_ids)
        )
    ).all()
    question_revision_map = {qr.id: qr for qr in question_revisions}

    results = []
    for answer in batch_request.answers:
        question_revision = question_revision_map.get(answer.question_revision_id)
        if question_revision:
            answer.response = validate_question_response_format(
                answer.response, question_revision.question_type
            )
        if not question_revision:
            raise HTTPException(
                status_code=404,
                detail=f"Question revision {answer.question_revision_id} not found",
            )

        if (
            question_revision.question_type == QuestionType.subjective
            and question_revision.subjective_answer_limit is not None
        ):
            validate_subjective_answer_limit(
                answer_limit=question_revision.subjective_answer_limit,
                response=answer.response,
            )

        # Check if answer already exists for this question
        existing_answer = session.exec(
            select(CandidateTestAnswer)
            .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
            .where(
                CandidateTestAnswer.question_revision_id == answer.question_revision_id
            )
        ).first()

        enforce_question_set_attempt_limit(
            session,
            candidate_test=candidate_test,
            question_revision_id=answer.question_revision_id,
            response=answer.response,
            existing_answer=existing_answer,
        )

        if existing_answer:
            if existing_answer.is_reviewed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Cannot modify answer for question {answer.question_revision_id} after it has been reviewed",
                )
            # Update existing answer
            existing_answer.response = answer.response
            existing_answer.visited = answer.visited
            existing_answer.time_spent = answer.time_spent
            existing_answer.bookmarked = answer.bookmarked
            session.add(existing_answer)
            results.append(existing_answer)
        else:
            # Create new answer
            new_answer = CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=answer.question_revision_id,
                response=answer.response,
                visited=answer.visited,
                time_spent=answer.time_spent,
                bookmarked=answer.bookmarked,
            )
            session.add(new_answer)
            results.append(new_answer)

    # Commit all changes in a single transaction
    session.commit()

    # Refresh all results
    for result in results:
        session.refresh(result)

    response = []
    for result in results:
        response.append(
            CandidateTestAnswerPublic(
                id=result.id,
                candidate_test_id=result.candidate_test_id,
                question_revision_id=result.question_revision_id,
                response=result.response,
                visited=result.visited,
                time_spent=result.time_spent,
                bookmarked=result.bookmarked,
                created_date=result.created_date,
                modified_date=result.modified_date,
            )
        )

    return response


@router.post("/submit_test/{candidate_test_id}", response_model=CandidateTestPublic)
def submit_test_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> CandidateTestPublic:
    """
    Submit/finish test for QR code candidates using UUID authentication.
    Returns the test with all answers and their correct answers.
    """
    # Verify UUID access
    candidate_test = verify_candidate_uuid_access(
        session, candidate_test_id, candidate_uuid
    )

    if candidate_test.is_submitted:
        raise HTTPException(status_code=400, detail="Test already submitted")

    test_expired = is_candidate_test_expired(session, candidate_test)

    if not test_expired:
        # Validate mandatory questions are answered
        assigned_question_ids = candidate_test.question_revision_ids
        if assigned_question_ids:
            # Get all mandatory question revisions for this test
            mandatory_questions_query = select(QuestionRevision).where(
                col(QuestionRevision.id).in_(assigned_question_ids),
                col(QuestionRevision.is_mandatory),
            )
            mandatory_questions = session.exec(mandatory_questions_query).all()

            if mandatory_questions:
                mandatory_question_ids = {q.id for q in mandatory_questions}

                # Get answered mandatory questions (with non-empty response)
                answered_query = select(CandidateTestAnswer.question_revision_id).where(
                    CandidateTestAnswer.candidate_test_id == candidate_test_id,
                    col(CandidateTestAnswer.question_revision_id).in_(
                        mandatory_question_ids
                    ),
                    col(CandidateTestAnswer.response).is_not(None),
                    col(CandidateTestAnswer.response) != "",
                )
                answered_ids = set(session.exec(answered_query).all())

                # Find unanswered mandatory questions
                unanswered_mandatory = mandatory_question_ids - answered_ids

                if unanswered_mandatory:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot submit test. {len(unanswered_mandatory)} mandatory question(s) not answered.",
                    )

    # Mark test as submitted and set end time
    candidate_test.is_submitted = True
    candidate_test.end_time = get_timezone_aware_now()

    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)

    test = session.get(Test, candidate_test.test_id)
    show_feedback = test.show_feedback_on_completion if test else False

    answers_with_feedback = None
    if show_feedback:
        answers = session.exec(
            select(CandidateTestAnswer).where(
                CandidateTestAnswer.candidate_test_id == candidate_test_id
            )
        ).all()

        question_revision_ids = [answer.question_revision_id for answer in answers]
        correct_answers_map = {}
        if question_revision_ids:
            question_revisions = session.exec(
                select(QuestionRevision).where(
                    col(QuestionRevision.id).in_(question_revision_ids)
                )
            ).all()
            correct_answers_map = {
                question_revision.id: question_revision.correct_answer
                for question_revision in question_revisions
            }

        answers_with_feedback = [
            CandidateTestAnswerFeedback(
                question_revision_id=answer.question_revision_id,
                response=answer.response,
                correct_answer=correct_answers_map.get(answer.question_revision_id),
            )
            for answer in answers
        ]

    return CandidateTestPublic(
        id=candidate_test.id,
        test_id=candidate_test.test_id,
        candidate_id=candidate_test.candidate_id,
        device=candidate_test.device,
        consent=candidate_test.consent,
        start_time=candidate_test.start_time,
        end_time=candidate_test.end_time,
        is_submitted=candidate_test.is_submitted,
        certificate_data=candidate_test.certificate_data,
        created_date=candidate_test.created_date,
        modified_date=candidate_test.modified_date,
        answers=answers_with_feedback,
    )


# Get test questions after verification
@router.get("/test_questions/{candidate_test_id}", response_model=TestCandidatePublic)
def get_test_questions(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
    use_omr: bool = Query(
        False, description="Applicable only when test OMR mode is OPTIONAL"
    ),
) -> TestCandidatePublic:
    """
    Get test questions for a candidate test, verified by candidate UUID.
    """
    # Verify candidate_test belongs to the candidate with given UUID
    candidate_test_statement = (
        select(CandidateTest)
        .join(Candidate)
        .where(CandidateTest.id == candidate_test_id)
        .where(Candidate.identity == candidate_uuid)
    )
    candidate_test = session.exec(candidate_test_statement).first()

    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="Candidate test not found or invalid UUID"
        )

    # Get the full test with all relationships
    test = session.get(Test, candidate_test.test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    test_id = get_persisted_test_id(test)

    from app.models.location import State
    from app.models.tag import Tag
    from app.models.test import TestState, TestTag

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == test_id)
    tags = session.exec(tags_query).all()

    state_query = select(State).join(TestState).where(TestState.test_id == test_id)
    states = session.exec(state_query).all()
    assigned_ids = candidate_test.question_revision_ids
    if not assigned_ids:
        raise HTTPException(status_code=404, detail="No questions assigned")
    question_revisions_map = get_question_revisions_map(session, assigned_ids)
    test_questions = get_test_question_links(session, test_id)
    question_sets = get_test_question_sets(session, test_id)
    question_sets_by_id = {
        question_set.id: question_set
        for question_set in question_sets
        if question_set.id is not None
    }
    try:
        sectioned = is_sectioned_test(
            test_questions,
            question_sets_by_id,
            test_id=test_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    omr_mode = getattr(test, "omr", OMRMode.NEVER)

    if omr_mode == OMRMode.NEVER:
        hide_question_text = False

    elif omr_mode == OMRMode.ALWAYS:
        hide_question_text = True

    elif omr_mode == OMRMode.OPTIONAL:
        hide_question_text = bool(use_omr)

    gcs_service = (
        get_gcs_service_for_org(session, test.organization_id)
        if test.organization_id is not None
        else None
    )
    candidate_questions, candidate_question_sets = build_candidate_question_payload(
        test=test,
        candidate_test=candidate_test,
        question_revisions_map=question_revisions_map,
        question_sets_by_id=question_sets_by_id,
        hide_question_text=hide_question_text,
        sectioned=sectioned,
        gcs_service=gcs_service,
    )

    return TestCandidatePublic(
        **test.model_dump(),
        question_revisions=candidate_questions,
        question_sets=candidate_question_sets,
        tags=tags,
        states=states,
        total_questions=len(candidate_questions),
        candidate_test=candidate_test,
    )


# Create a Candidate
@router.post(
    "/",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("create_candidate"))],
)
def create_candidate(
    candidate_create: CandidateCreate, session: SessionDep, current_user: CurrentUser
) -> Candidate:
    candidate_dump = candidate_create.model_dump()
    candidate_dump["organization_id"] = current_user.organization_id
    candidate = Candidate.model_validate(candidate_dump)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Get all Candidates
@router.get(
    "/",
    response_model=list[CandidatePublic],
    dependencies=[Depends(permission_dependency("read_candidate"))],
)
def get_candidate(session: SessionDep) -> Sequence[Candidate]:
    candidate = session.exec(select(Candidate).where(not_(Candidate.is_deleted))).all()
    return candidate


@router.get(
    "/summary",
    response_model=TestStatusSummary,
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_test_summary(
    session: SessionDep,
    current_user: CurrentUser,
    start_date: datetime | None = Query(
        None, description="Start date in YYYY-MM-DD format"
    ),
    end_date: datetime | None = Query(
        None, description="End date in YYYY-MM-DD format"
    ),
) -> TestStatusSummary:
    """
    Get Summary of Tests: total submitted, not submitted (active/inactive)
    """
    current_user_district_ids: list[int] = []
    if (
        current_user.role.name == state_admin.name
        or current_user.role.name == test_admin.name
    ):
        current_user_district_ids = (
            [
                district.id
                for district in current_user.districts
                if district.id is not None
            ]
            if current_user.districts
            else []
        )

    query = (
        select(CandidateTest, Test)
        .join(Test)
        .where(CandidateTest.test_id == Test.id)
        .join(User)
        .where(Test.created_by_id == User.id)
        .where(User.organization_id == current_user.organization_id)
    )

    if current_user_district_ids:
        district_test_ids = select(TestDistrict.test_id).where(
            col(TestDistrict.district_id).in_(current_user_district_ids)
        )
        query = query.where(col(Test.id).in_(district_test_ids))

    else:
        current_user_state_ids: list[int] = []
        current_user_state_ids = (
            [state.id for state in current_user.states if state.id is not None]
            if current_user.states
            else []
        )

        if current_user_state_ids:
            state_test_ids = select(TestState.test_id).where(
                col(TestState.state_id).in_(current_user_state_ids)
            )
            query = query.where(col(Test.id).in_(state_test_ids))

    if start_date and Test.start_time is not None:
        query = query.where(Test.start_time >= start_date)

    if end_date and Test.end_time is not None:
        query = query.where(Test.end_time <= end_date)
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    results = session.exec(query).all()
    submitted = 0
    not_submitted = 0
    not_submitted_active = 0
    not_submitted_inactive = 0
    now = get_current_time()
    for candidate_test, test in results:
        c_start = candidate_test.start_time
        c_end = candidate_test.end_time

        t_end = test.end_time
        time_limit = getattr(test, "time_limit", None)
        if candidate_test.is_submitted or c_end:
            submitted += 1
            continue
        not_submitted += 1

        potential_time_spent = (now - c_start).total_seconds() / 60 if c_start else None

        if not t_end:
            if (
                not time_limit
                or potential_time_spent is None
                or potential_time_spent < time_limit
            ):
                not_submitted_active += 1
            else:
                not_submitted_inactive += 1
        elif t_end and now < t_end:
            if time_limit:
                if potential_time_spent is None or potential_time_spent < time_limit:
                    not_submitted_active += 1
                else:
                    not_submitted_inactive += 1
            else:
                not_submitted_active += 1
        else:
            not_submitted_inactive += 1

    return TestStatusSummary(
        total_test_submitted=submitted,
        total_test_not_submitted=not_submitted,
        not_submitted_active=not_submitted_active,
        not_submitted_inactive=not_submitted_inactive,
    )


# Get Candidate by ID
@router.get(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("read_candidate"))],
)
def get_candidate_by_id(candidate_id: int, session: SessionDep) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


# Update a Candidate
@router.put(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("update_candidate"))],
)
def update_candidate(
    candidate_id: int,
    updated_data: CandidateUpdate,
    session: SessionDep,
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate_data = updated_data.model_dump(exclude_unset=True)
    candidate.sqlmodel_update(candidate_data)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Set Visibility of Candidate
@router.patch(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("update_candidate"))],
)
def visibility_candidate(
    candidate_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of candidate"),
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_active = is_active
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Delete a Candidate
@router.delete(
    "/{candidate_id}",
    dependencies=[Depends(permission_dependency("delete_candidate"))],
)
def delete_candidate(candidate_id: int, session: SessionDep) -> Message:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_deleted = True
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return Message(message="Candidate deleted successfully")


# Create Link between Candidate and Test


# Create a Candidate-Test Link
@router_candidate_test.post(
    "/",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("create_candidate_test"))],
)
def create_candidate_test(
    candidate_test_create: CandidateTestCreate, session: SessionDep
) -> CandidateTest:
    candidate_test = CandidateTest.model_validate(candidate_test_create)
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test


# Get all Candidate-Test Link
@router_candidate_test.get(
    "/",
    response_model=list[CandidateTestPublic],
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_candidate_test(session: SessionDep) -> Sequence[CandidateTest]:
    candidate_test = session.exec(select(CandidateTest)).all()
    return candidate_test


# Get Candidate-Test Link by ID
@router_candidate_test.get(
    "/{candidate_test_id}",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_candidate_test_by_id(
    candidate_test_id: int, session: SessionDep
) -> CandidateTest:
    candidate_test = session.get(CandidateTest, candidate_test_id)
    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="No combination of candidate and test found"
        )
    return candidate_test


# Update Candidate-Test Link
@router_candidate_test.put(
    "/{candidate_test_id}",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("update_candidate_test"))],
)
def update_candidate_test(
    candidate_test_id: int,
    updated_data: CandidateTestUpdate,
    session: SessionDep,
) -> CandidateTest:
    candidate_test = session.get(CandidateTest, candidate_test_id)
    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="No combination of candidate and test found"
        )

    candidate_test_data = updated_data.model_dump(exclude_unset=True)
    candidate_test.sqlmodel_update(candidate_test_data)
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test


# Route for Answering a Question for a test by a candidate


# Create a Candidate-Test & Answers Link
@router_candidate_test_answer.post(
    "/",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("create_candidate_test_answer"))],
)
def create_candidate_test_answer(
    candidate_test_answer_create: CandidateTestAnswerCreate, session: SessionDep
) -> CandidateTestAnswer:
    candidate_test_answer = CandidateTestAnswer.model_validate(
        candidate_test_answer_create
    )
    session.add(candidate_test_answer)
    session.commit()
    session.refresh(candidate_test_answer)
    return candidate_test_answer


# Get all Candidate-Test  & Answer Link
@router_candidate_test_answer.get(
    "/",
    response_model=list[CandidateTestAnswerPublic],
    dependencies=[Depends(permission_dependency("read_candidate_test_answer"))],
)
def get_candidate_test_answer(session: SessionDep) -> Sequence[CandidateTestAnswer]:
    candidate_test_answer = session.exec(select(CandidateTestAnswer)).all()
    return candidate_test_answer


# Get Candidate-Test  & Answer Link by ID
@router_candidate_test_answer.get(
    "/{candidate_test_answer_id}",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("read_candidate_test_answer"))],
)
def get_candidate_test_answer_by_id(
    candidate_test_answer_id: int, session: SessionDep
) -> CandidateTestAnswer:
    candidate_test_answer = session.get(CandidateTestAnswer, candidate_test_answer_id)
    if not candidate_test_answer:
        raise HTTPException(
            status_code=404,
            detail="No Answer found",
        )
    return candidate_test_answer


# Update Candidate-Test & Answer Link
@router_candidate_test_answer.put(
    "/{candidate_test_answer_id}",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("update_candidate_test_answer"))],
)
def update_candidate_answer_test(
    candidate_test_answer_id: int,
    updated_data: CandidateTestAnswerUpdate,
    session: SessionDep,
) -> CandidateTestAnswer:
    candidate_test_answer = session.get(CandidateTestAnswer, candidate_test_answer_id)
    if not candidate_test_answer:
        raise HTTPException(status_code=404, detail="No Answer found")

    # Block update if answer has been reviewed
    if candidate_test_answer.is_reviewed:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify answer after it has been reviewed",
        )

    candidate_test_answer_data = updated_data.model_dump(exclude_unset=True)
    candidate_test_answer.sqlmodel_update(candidate_test_answer_data)
    session.add(candidate_test_answer)
    session.commit()
    session.refresh(candidate_test_answer)
    return candidate_test_answer


def convert_to_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}"):
            return value[1:-1].split(",")
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
            return [v.strip() for v in value.split(",")]

        return [value.strip()]

    return [str(value)]


@router.get("/result/{candidate_test_id}", response_model=Result)
def get_test_result(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> Result:
    candidate_test = session.get(CandidateTest, candidate_test_id)

    if not candidate_test:
        raise HTTPException(status_code=404, detail="Candidate test not found")
    test = session.get(Test, candidate_test.test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found")
    if not test.show_result:
        raise HTTPException(
            status_code=403, detail="Results are not visible for this test"
        )
    test_id = get_persisted_test_id(test)

    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)
    test_questions = get_test_question_links(session, test_id)
    question_sets = get_test_question_sets(session, test_id)
    question_sets_by_id = {
        question_set.id: question_set
        for question_set in question_sets
        if question_set.id is not None
    }
    try:
        sectioned = is_sectioned_test(
            test_questions,
            question_sets_by_id,
            test_id=test_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    question_revisions_map = get_question_revisions_map(
        session, candidate_test.question_revision_ids
    )
    answers = session.exec(
        select(CandidateTestAnswer).where(
            CandidateTestAnswer.candidate_test_id == candidate_test_id
        )
    ).all()
    answers_by_question_id = {answer.question_revision_id: answer for answer in answers}
    question_set_id_by_revision = build_question_set_id_map(
        candidate_test.question_revision_ids,
        candidate_test.question_set_ids,
    )

    correct = 0
    incorrect = 0
    mandatory_not_attempted = 0
    optional_not_attempted = 0
    marks_obtained = 0.0
    marks_maximum = 0.0
    has_marking_scheme = False

    for question_revision_id in candidate_test.question_revision_ids:
        revision = question_revisions_map.get(question_revision_id)
        if not revision:
            continue

        answer = answers_by_question_id.get(question_revision_id)
        question_set = question_sets_by_id.get(
            question_set_id_by_revision.get(question_revision_id) or -1
        )
        marking_scheme = get_effective_marking_scheme(
            test,
            revision,
            question_set=question_set,
            sectioned=sectioned,
        )
        if marking_scheme:
            has_marking_scheme = True

        correct_mark = marking_scheme["correct"] if marking_scheme else 0
        wrong_mark = marking_scheme["wrong"] if marking_scheme else 0
        skipped_mark = marking_scheme["skipped"] if marking_scheme else 0

        marks_maximum += correct_mark

        if answer is None or not is_attempted_response(answer.response):
            marks_obtained += skipped_mark
            if revision.is_mandatory:
                mandatory_not_attempted += 1
            else:
                optional_not_attempted += 1
        else:
            if (
                revision.question_type == QuestionType.subjective
                or revision.question_type == QuestionType.matrix_rating
            ):
                is_attempted = bool(answer.response)
                if is_attempted:
                    correct += 1
                    marks_obtained += correct_mark
                else:
                    incorrect += 1
                    marks_obtained += wrong_mark

            elif revision.question_type is QuestionType.single_choice:
                response_set = set(convert_to_list(answer.response))
                correct_set = set(convert_to_list(revision.correct_answer))
                if response_set == correct_set:
                    marks_obtained += correct_mark
                    correct += 1
                else:
                    marks_obtained += wrong_mark
                    incorrect += 1

            elif revision.question_type.value == "multi-choice":
                response_set = set(convert_to_list(answer.response))
                correct_set = set(convert_to_list(revision.correct_answer))
                selected_correct = len(response_set & correct_set)
                selected_wrong = len(response_set - correct_set)

                whole_correct = (
                    selected_correct == len(correct_set) and selected_wrong == 0
                )
                if whole_correct:
                    marks_obtained += correct_mark
                    correct += 1
                else:
                    if marking_scheme and marking_scheme.get("partial"):
                        partial_rule = marking_scheme["partial"]

                        if selected_wrong == 0 and selected_correct > 0:
                            partial = 0.0

                            for condition in partial_rule["correct_answers"]:
                                if (
                                    condition["num_correct_selected"]
                                    == selected_correct
                                ):
                                    partial = condition["marks"]
                                    break

                            marks_obtained += partial
                            correct += 1
                        else:
                            marks_obtained += wrong_mark
                            incorrect += 1
                    else:
                        marks_obtained += wrong_mark
                        incorrect += 1

            elif revision.question_type.value in [
                "numerical-integer",
                "numerical-decimal",
            ]:
                try:
                    response_value = answer.response
                    if response_value is None:
                        raise TypeError
                    user_value = float(response_value)
                except (TypeError, ValueError):
                    incorrect += 1
                    marks_obtained += wrong_mark
                    continue

                if isinstance(revision.correct_answer, int | float):
                    correct_value = float(revision.correct_answer)
                else:
                    continue

                if revision.question_type.value == "numerical-integer":
                    is_correct = user_value.is_integer() and int(user_value) == int(
                        correct_value
                    )
                else:
                    is_correct = abs(user_value - correct_value) <= TOLERANCE

                if is_correct:
                    correct += 1
                    marks_obtained += correct_mark
                else:
                    incorrect += 1
                    marks_obtained += wrong_mark

            elif revision.question_type.value == "matrix-match":
                try:
                    matrix_response = answer.response
                    if matrix_response is None:
                        raise TypeError
                    candidate_matrix_response = json.loads(matrix_response)
                except (TypeError, ValueError, json.JSONDecodeError):
                    incorrect += 1
                    marks_obtained += wrong_mark
                    continue

                expected_matrix_answer = revision.correct_answer

                if isinstance(candidate_matrix_response, dict) and isinstance(
                    expected_matrix_answer, dict
                ):
                    expected_row_to_columns = {
                        str(row_id): {int(col_id) for col_id in column_ids}
                        for row_id, column_ids in expected_matrix_answer.items()
                    }

                    # Only expected rows are evaluated; extra candidate rows are ignored.
                    correctly_matched_rows = 0
                    for row_id, expected_cols in expected_row_to_columns.items():
                        candidate_cols = candidate_matrix_response.get(row_id)
                        if isinstance(candidate_cols, list):
                            candidate_col_set = {
                                int(col_id) for col_id in candidate_cols
                            }
                        else:
                            candidate_col_set = set()
                        if candidate_col_set == expected_cols:
                            correctly_matched_rows += 1

                    if correctly_matched_rows == len(expected_row_to_columns):
                        marks_obtained += correct_mark
                        correct += 1
                    elif (
                        marking_scheme
                        and marking_scheme.get("partial")
                        and correctly_matched_rows > 0
                    ):
                        partial_marks = next(
                            (
                                cond["marks"]
                                for cond in marking_scheme["partial"]["correct_answers"]
                                if cond["num_correct_selected"]
                                == correctly_matched_rows
                            ),
                            0.0,
                        )
                        marks_obtained += partial_marks
                        correct += 1
                    else:
                        marks_obtained += wrong_mark
                        incorrect += 1
                else:
                    marks_obtained += wrong_mark
                    incorrect += 1

    total_questions = len(candidate_test.question_revision_ids)

    # Generate certificate download URL if test has a certificate assigned
    certificate_download_url = None
    if test.certificate_id:
        # Check if certificate_data already exists (reuse token)
        if candidate_test.certificate_data and candidate_test.certificate_data.get(
            "token"
        ):
            token = candidate_test.certificate_data["token"]
        else:
            # Generate new token and save certificate data snapshot
            token = generate_certificate_token()

            # Format score string from already-calculated values
            if marks_maximum > 0:
                score_percentage = marks_obtained / marks_maximum * 100
                score_str = f"{marks_obtained:.1f}/{marks_maximum:.1f} ({score_percentage:.1f}%)"
            else:
                score_str = "N/A"

            # Format completion date
            completion_date = (
                candidate_test.end_time.strftime("%B %d, %Y")
                if candidate_test.end_time
                else "N/A"
            )

            # Get form response values if available
            form_response_data: dict[str, Any] = {}
            if test.form_id:
                raw_responses: dict[str, Any] = {}
                form_response = session.exec(
                    select(FormResponse).where(
                        FormResponse.candidate_test_id == candidate_test.id,
                        FormResponse.form_id == test.form_id,
                    )
                ).first()
                if form_response and form_response.responses:
                    raw_responses = form_response.responses
                # Always resolve so unanswered fields default to "N/A"
                form_response_data = resolve_form_response_values(
                    form_id=test.form_id,
                    responses=raw_responses,
                    session=session,
                )

            # Save certificate data snapshot (fixed tokens + form field values)
            candidate_test.certificate_data = {
                "token": token,
                # Fixed tokens
                "test_name": test.name,
                "score": score_str,
                "completion_date": completion_date,
                # Dynamic tokens from form response
                **form_response_data,
            }
            session.add(candidate_test)
            session.commit()

        certificate_download_url = f"/api/v1/certificate/download/{token}"

    return Result(
        correct_answer=correct,
        incorrect_answer=incorrect,
        mandatory_not_attempted=mandatory_not_attempted,
        optional_not_attempted=optional_not_attempted,
        total_questions=total_questions,
        marks_obtained=marks_obtained if has_marking_scheme else None,
        marks_maximum=marks_maximum if has_marking_scheme else None,
        certificate_download_url=certificate_download_url,
    )


@router.get("/time_left/{candidate_test_id}", response_model=TimeLeft)
def get_time_left(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> TimeLeft:
    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)
    candidate_test = session.exec(
        select(CandidateTest).where(CandidateTest.id == candidate_test_id)
    ).first()
    if not candidate_test:
        raise HTTPException(status_code=404, detail="Candidate test not found")
    test = session.exec(select(Test).where(Test.id == candidate_test.test_id)).first()

    if not test:
        raise HTTPException(status_code=404, detail="Associated test not found")
    current_time = get_current_time()

    elapsed_time = current_time - candidate_test.start_time
    remaining_times = []
    if test.time_limit is not None:
        remaining_by_limit = timedelta(minutes=float(test.time_limit)) - elapsed_time
        remaining_times.append(remaining_by_limit)
    if test.end_time is not None:
        remaining_by_endtime = test.end_time - current_time
        remaining_times.append(remaining_by_endtime)
    if not remaining_times:
        return TimeLeft(time_left=None)
    final_time_left = min(remaining_times)
    if final_time_left.total_seconds() <= 0:
        return TimeLeft(time_left=0)

    time_left = int(final_time_left.total_seconds())
    return TimeLeft(time_left=time_left)


@router.get(
    "/{candidate_test_id}/review-feedback",
    response_model=list[CandidateReviewResponse],
)
def get_review_feedback(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
    question_revision_ids: list[int] | None = Query(
        None, description="Optional list of question revision IDs for feedback"
    ),
) -> list[CandidateReviewResponse]:
    candidate_test = verify_candidate_uuid_access(
        session, candidate_test_id, candidate_uuid
    )

    test = session.get(Test, candidate_test.test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    show_instant_feedback = test.show_feedback_immediately
    show_feedback_on_completion = test.show_feedback_on_completion

    if candidate_test.end_time is None and not show_instant_feedback:
        raise HTTPException(
            status_code=403,
            detail="Feedback is not enabled for this test during attempt",
        )

    if candidate_test.end_time is not None and not show_feedback_on_completion:
        raise HTTPException(
            status_code=403,
            detail="Post-submission feedback is not enabled for this test",
        )

    assigned_ids = set(candidate_test.question_revision_ids)
    if question_revision_ids:
        question_ids_to_fetch = [
            question_revision_id
            for question_revision_id in question_revision_ids
            if question_revision_id in assigned_ids
        ]
    else:
        question_ids_to_fetch = candidate_test.question_revision_ids

    submitted_answers = session.exec(
        select(CandidateTestAnswer).where(
            CandidateTestAnswer.candidate_test_id == candidate_test_id,
            col(CandidateTestAnswer.question_revision_id).in_(question_ids_to_fetch),
        )
    ).all()

    answers_by_question_id = {
        ans.question_revision_id: ans for ans in submitted_answers
    }

    question_revisions = session.exec(
        select(QuestionRevision).where(
            col(QuestionRevision.id).in_(question_ids_to_fetch)
        )
    ).all()

    revisions_by_id = {rev.id: rev for rev in question_revisions}

    feedback_list: list[CandidateReviewResponse] = []

    for question_id in question_ids_to_fetch:
        if question_revision := revisions_by_id.get(question_id):
            candidate_answer = answers_by_question_id.get(question_id)

            if candidate_answer and not candidate_answer.is_reviewed:
                candidate_answer.is_reviewed = True
                session.add(candidate_answer)

            feedback_list.append(
                CandidateReviewResponse(
                    question_revision_id=question_id,
                    submitted_answer=(
                        candidate_answer.response if candidate_answer else None
                    ),
                    correct_answer=question_revision.correct_answer,
                )
            )

    session.commit()

    return feedback_list
