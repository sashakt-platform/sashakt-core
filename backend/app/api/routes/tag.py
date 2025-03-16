from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.models.tag import Tag

router = APIRouter(prefix="/tag", tags=["Tag"])


# Create a Tag
@router.post("/", response_model=Tag)
def create_tag(tag: Tag, session: SessionDep):
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


# Get all Tags
@router.get("/", response_model=list[Tag])
def get_tag(session: SessionDep):
    tag = session.exec(select(Tag)).all()
    return tag


# Get Tag by ID
@router.get("/{tag_id}", response_model=Tag)
def get_tag_by_id(tag_id: int, session: SessionDep):
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


# Update a Tag
@router.put("/{tag_id}", response_model=Tag)
def update_tag(
    tag_id: int,
    updated_data: Tag,
    session: SessionDep,
):
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.name = updated_data.name
    tag.description = updated_data.description
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


# Delete a Tag
@router.delete("/{tag_id}")
def delete_tag(tag_id: int, session: SessionDep):
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.is_deleted = True
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return {"message": "Tag deleted successfully"}
