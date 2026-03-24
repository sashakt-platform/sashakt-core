#!/usr/bin/env python3
"""
Import a quiz-backend style JSON file as a sectioned Sashakt test.

Example:
    uv run python scripts/import_quiz_json.py /path/to/quiz.json --dry-run
    uv run python scripts/import_quiz_json.py /path/to/quiz.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.api.routes.question import prepare_for_db
from app.api.routes.test import create_test
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.quiz_json_import import (
    build_question_create,
    build_question_set_create,
    build_test_create,
    count_quiz_question_types,
)
from app.models import Question, QuestionLocation, QuestionRevision, User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a quiz JSON file into Sashakt as a sectioned test."
    )
    parser.add_argument("json_path", help="Path to the quiz JSON file.")
    parser.add_argument(
        "--created-by-email",
        default=str(settings.FIRST_SUPERUSER),
        help="Email of the Sashakt user that should own the imported questions/test.",
    )
    parser.add_argument(
        "--organization-id",
        type=int,
        default=None,
        help="Override organization_id. Defaults to the creator user's organization.",
    )
    parser.add_argument(
        "--state-id",
        action="append",
        dest="state_ids",
        type=int,
        default=[],
        help="Attach the imported questions/test to a state. Can be passed multiple times.",
    )
    parser.add_argument(
        "--district-id",
        action="append",
        dest="district_ids",
        type=int,
        default=[],
        help="Attach the imported questions/test to a district. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and summarize the import without writing to the database.",
    )
    parser.add_argument(
        "--question-set-attempt-mode",
        choices=["source", "all", "half"],
        default="source",
        help=(
            "How to set max_questions_allowed_to_attempt for each imported question set. "
            "'source' keeps the JSON value, 'all' uses the full set size, 'half' uses ceil(set_size / 2)."
        ),
    )
    return parser.parse_args()


def resolve_creator(session: Session, email: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise ValueError(
            f"User with email '{email}' was not found. Pass --created-by-email with an existing user."
        )
    return user


def create_question_revision(
    session: Session,
    *,
    question_payload: dict,
    organization_id: int,
    created_by_id: int,
    state_ids: list[int],
    district_ids: list[int],
) -> QuestionRevision:
    question_create = build_question_create(
        question_payload,
        organization_id=organization_id,
        state_ids=state_ids,
        district_ids=district_ids,
    )

    question = Question(
        organization_id=organization_id,
        is_active=question_create.is_active,
    )
    session.add(question)
    session.flush()

    options, marking_scheme, media = prepare_for_db(question_create)
    revision = QuestionRevision(
        question_id=question.id,
        created_by_id=created_by_id,
        question_text=question_create.question_text,
        instructions=question_create.instructions,
        question_type=question_create.question_type,
        options=options,
        correct_answer=question_create.correct_answer,
        subjective_answer_limit=question_create.subjective_answer_limit,
        is_mandatory=question_create.is_mandatory,
        marking_scheme=marking_scheme,
        solution=question_create.solution,
        media=media,
        is_active=question_create.is_active,
    )
    session.add(revision)
    session.flush()

    question.last_revision_id = revision.id

    for state_id in state_ids:
        session.add(
            QuestionLocation(
                question_id=question.id,
                state_id=state_id,
                district_id=None,
                block_id=None,
            )
        )
    for district_id in district_ids:
        session.add(
            QuestionLocation(
                question_id=question.id,
                state_id=None,
                district_id=district_id,
                block_id=None,
            )
        )

    session.flush()
    return revision


def load_quiz_payload(json_path: Path) -> dict:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Quiz JSON file not found: {json_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse quiz JSON '{json_path}': {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Quiz JSON must be a top-level object.")
    if not payload.get("question_sets"):
        raise ValueError("Quiz JSON must contain at least one question set.")
    return payload


def print_summary(
    quiz_payload: dict,
    *,
    creator_email: str,
    organization_id: int,
    state_ids: list[int],
    district_ids: list[int],
) -> None:
    question_type_counts = count_quiz_question_types(quiz_payload)
    question_sets = quiz_payload.get("question_sets") or []
    total_questions = sum(
        len(question_set.get("questions") or []) for question_set in question_sets
    )
    print("Import summary")
    print(f"  title: {quiz_payload.get('title')}")
    print(f"  question_sets: {len(question_sets)}")
    print(f"  total_questions: {total_questions}")
    print(f"  question_types: {dict(question_type_counts)}")
    print(f"  created_by_email: {creator_email}")
    print(f"  organization_id: {organization_id}")
    print(f"  state_ids: {state_ids}")
    print(f"  district_ids: {district_ids}")


def build_question_sets_for_import(
    quiz_payload: dict,
    *,
    organization_id: int,
    created_by_id: int | None,
    state_ids: list[int],
    district_ids: list[int],
    question_set_attempt_mode: str,
    session: Session | None = None,
) -> list:
    question_set_creates = []
    for display_order, question_set_payload in enumerate(
        quiz_payload.get("question_sets") or [],
        start=1,
    ):
        question_revision_ids: list[int] = []
        for question_index, question_payload in enumerate(
            question_set_payload.get("questions") or [],
            start=1,
        ):
            build_question_create(
                question_payload,
                organization_id=organization_id,
                state_ids=state_ids,
                district_ids=district_ids,
            )
            if session is not None and created_by_id is not None:
                revision = create_question_revision(
                    session,
                    question_payload=question_payload,
                    organization_id=organization_id,
                    created_by_id=created_by_id,
                    state_ids=state_ids,
                    district_ids=district_ids,
                )
                question_revision_ids.append(revision.id)
            else:
                question_revision_ids.append(display_order * 1000 + question_index)

        question_count = len(question_revision_ids)
        if question_set_attempt_mode == "all":
            max_questions_allowed_to_attempt = question_count
        elif question_set_attempt_mode == "half":
            max_questions_allowed_to_attempt = max(1, math.ceil(question_count / 2))
        else:
            max_questions_allowed_to_attempt = None

        question_set_creates.append(
            build_question_set_create(
                question_set_payload,
                display_order=display_order,
                question_revision_ids=question_revision_ids,
                max_questions_allowed_to_attempt=max_questions_allowed_to_attempt,
            )
        )

    return question_set_creates


def main() -> int:
    args = parse_args()
    json_path = Path(args.json_path).expanduser().resolve()
    quiz_payload = load_quiz_payload(json_path)

    with Session(engine) as session:
        init_db(session)
        creator = resolve_creator(session, args.created_by_email)
        organization_id = args.organization_id or creator.organization_id

        print_summary(
            quiz_payload,
            creator_email=creator.email,
            organization_id=organization_id,
            state_ids=args.state_ids,
            district_ids=args.district_ids,
        )
        if args.dry_run:
            question_set_creates = build_question_sets_for_import(
                quiz_payload,
                organization_id=organization_id,
                created_by_id=None,
                state_ids=args.state_ids,
                district_ids=args.district_ids,
                question_set_attempt_mode=args.question_set_attempt_mode,
                session=None,
            )
            build_test_create(
                quiz_payload,
                question_sets=question_set_creates,
                source_path=str(json_path),
                state_ids=args.state_ids,
                district_ids=args.district_ids,
            )
            print("Dry run succeeded. No rows were written.")
            return 0

        try:
            question_set_creates = build_question_sets_for_import(
                quiz_payload,
                organization_id=organization_id,
                created_by_id=creator.id,
                state_ids=args.state_ids,
                district_ids=args.district_ids,
                question_set_attempt_mode=args.question_set_attempt_mode,
                session=session,
            )
            total_created_questions = sum(
                len(question_set.question_revision_ids)
                for question_set in question_set_creates
            )

            test_create = build_test_create(
                quiz_payload,
                question_sets=question_set_creates,
                source_path=str(json_path),
                state_ids=args.state_ids,
                district_ids=args.district_ids,
            )
            created_test = create_test(test_create, session, creator)
        except Exception:
            session.rollback()
            raise

    print("Created sectioned test")
    print(f"  test_id: {created_test.id}")
    print(f"  link: {created_test.link}")
    print(f"  question_sets: {len(created_test.question_sets or [])}")
    print(f"  questions_created: {total_created_questions}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
