from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import Message, Question

router = APIRouter(prefix="/question", tags=["Question"])


# Create a Question
@router.post("/", response_model=Question)
def create_question(question: Question, session: SessionDep) -> Question:
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# Get all Questions
@router.get("/", response_model=list[Question])
def get_question(session: SessionDep) -> Sequence[Question]:
    question = session.exec(select(Question)).all()
    return question


# Get Question by ID
@router.get("/{question_id}", response_model=Question)
def get_question_by_id(question_id: int, session: SessionDep) -> Question:
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


# Update a Question
@router.put("/{question_id}", response_model=Question)
def update_question(
    question_id: int,
    updated_data: Question,
    session: SessionDep,
) -> Question:
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    question.question = updated_data.question
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# Delete a Question
@router.delete("/{question_id}")
def delete_question(question_id: int, session: SessionDep) -> Message:
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    question.is_deleted = True
    session.add(question)
    session.commit()
    session.refresh(question)
    return Message(message="Question deleted successfully")
