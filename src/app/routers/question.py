from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.question import (
    Question,
    QuestionRevision,
)

router = APIRouter(prefix="/questions", tags=["Questions"])


# Delete a Question
@router.delete("/{question_id}")
def delete_question(question_id: int, session: Session = Depends(get_session)):
    question = session.get(Question, question_id)

    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Soft delete
    question.is_deleted = True
    question.is_active = False
    question.modified_date = datetime.now(timezone.utc)

    session.add(question)
    session.commit()

    return {"message": "Question deleted successfully"}


# Get Question Revisions
@router.get("/{question_id}/revisions", response_model=list[dict[str, Any]])
def get_question_revisions(question_id: int, session: Session = Depends(get_session)):
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    revisions_query = (
        select(QuestionRevision)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.created_date.desc())
    )

    revisions = session.exec(revisions_query).all()

    # can add things to return later
    return [
        {
            "id": rev.id,
            "created_date": rev.created_date,
            "text": rev.question_text,
            "type": rev.question_type,
            "is_current": rev.id == question.last_revision_id,
        }
        for rev in revisions
    ]


# Get a specific revision
@router.get("/revisions/{revision_id}", response_model=QuestionRevision)
def get_revision(revision_id: int, session: Session = Depends(get_session)) -> Any:
    """Get a specific question revision by its ID."""
    revision = session.get(QuestionRevision, revision_id)

    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Check if parent question exists and is not deleted
    question = session.get(Question, revision.question_id)
    if not question or question.is_deleted:
        raise HTTPException(
            status_code=404, detail="Parent question not found or deleted"
        )

    # Add is_current as an attribute
    revision.is_current = revision.id == question.last_revision_id

    return revision
