from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.models.question import Question

router = APIRouter(prefix="/question", tags=["Question"])


# Create a Question
@router.post("/", response_model=Question)
def create_question(question: Question, session: SessionDep):
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# Get all Questions
@router.get("/", response_model=list[Question])
def get_question(session: SessionDep):
    question = session.exec(select(Question)).all()
    return question


# Get Question by ID
@router.get("/{question_id}", response_model=Question)
def get_question_by_id(question_id: int, session: SessionDep):
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
):
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    question.name = updated_data.name
    question.description = updated_data.description
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# Delete a Question
@router.delete("/{question_id}")
def delete_question(question_id: int, session: SessionDep):
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    question.is_deleted = True
    session.add(question)
    session.commit()
    session.refresh(question)
    return {"message": "Question deleted successfully"}
