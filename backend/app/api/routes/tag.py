from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import not_, select

from app.api.deps import SessionDep, permission_dependency
from app.models import (
    Message,
    Tag,
    TagCreate,
    TagPublic,
    TagType,
    TagTypeCreate,
    TagTypePublic,
    TagTypeUpdate,
    TagUpdate,
)

router_tagtype = APIRouter(
    prefix="/tagtype",
    tags=["TagType"],
    dependencies=[Depends(permission_dependency("create_tag"))],
)
router_tag = APIRouter(
    prefix="/tag",
    tags=["Tag"],
    dependencies=[Depends(permission_dependency("create_tag"))],
)


# Routers fro Tag-Types


@router_tagtype.post("/", response_model=TagTypePublic)
def create_tagtype(tagtype_create: TagTypeCreate, session: SessionDep) -> TagType:
    tagtype = TagType.model_validate(tagtype_create)
    session.add(tagtype)
    session.commit()
    session.refresh(tagtype)
    return tagtype


@router_tagtype.get("/", response_model=list[TagTypePublic])
def get_tagtype(session: SessionDep) -> Sequence[TagType]:
    tagtype = session.exec(select(TagType).where(not_(TagType.is_deleted))).all()
    return tagtype


@router_tagtype.get("/{tagtype_id}", response_model=TagTypePublic)
def get_tagtype_by_id(tagtype_id: int, session: SessionDep) -> TagType:
    tagtype = session.get(TagType, tagtype_id)
    if not tagtype or tagtype.is_deleted is True:
        raise HTTPException(status_code=404, detail="TagType not found")
    return tagtype


@router_tagtype.put("/{tagtype_id}", response_model=TagTypePublic)
def update_tagtype(
    tagtype_id: int,
    updated_data: TagTypeUpdate,
    session: SessionDep,
) -> TagType:
    tagtype = session.get(TagType, tagtype_id)
    if not tagtype or tagtype.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")
    tagtype_data = updated_data.model_dump(exclude_unset=True)
    tagtype.sqlmodel_update(tagtype_data)
    session.add(tagtype)
    session.commit()
    session.refresh(tagtype)
    return tagtype


@router_tagtype.patch("/{tagtype_id}", response_model=TagTypePublic)
def visibility_tagtype(
    tagtype_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of TagType"),
) -> TagType:
    tagtype = session.get(TagType, tagtype_id)
    if not tagtype or tagtype.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")
    tagtype.is_active = is_active
    session.add(tagtype)
    session.commit()
    session.refresh(tagtype)
    return tagtype


@router_tagtype.delete("/{tagtype_id}")
def delete_tagtype(tagtype_id: int, session: SessionDep) -> Message:
    tagtype = session.get(TagType, tagtype_id)
    if not tagtype or tagtype.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")
    tagtype.is_deleted = True
    session.add(tagtype)
    session.commit()
    session.refresh(tagtype)
    return Message(message="Tag Type deleted successfully")


# Routers for Tags


# Create a Tag
@router_tag.post("/", response_model=TagPublic)
def create_tag(tag_create: TagCreate, session: SessionDep) -> TagPublic:
    tag_type_id = tag_create.tag_type_id
    tag_type = session.get(TagType, tag_type_id)
    if not tag_type or tag_type.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")
    organization_id = tag_type.organization_id

    tag_data = tag_create.model_dump(exclude_unset=True)
    tag_data["organization_id"] = organization_id
    tag = Tag.model_validate(tag_data)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    session.refresh(tag_type)

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Get all Tags
@router_tag.get("/", response_model=list[TagPublic])
def get_tags(session: SessionDep) -> Sequence[TagPublic]:
    tags = session.exec(select(Tag).where(not_(Tag.is_deleted))).all()
    tag_public = []
    for tag in tags:
        tag_type = session.get(TagType, tag.tag_type_id)
        if not tag_type or tag_type.is_deleted is True:
            continue
        tag_public.append(
            TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)
        )

    return tag_public


# Get Tag by ID
@router_tag.get("/{tag_id}", response_model=TagPublic)
def get_tag_by_id(tag_id: int, session: SessionDep) -> TagPublic:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_type = session.get(TagType, tag.tag_type_id)
    if not tag_type or tag_type.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")
    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Update a Tag
@router_tag.put("/{tag_id}", response_model=TagPublic)
def update_tag(
    tag_id: int,
    updated_data: TagUpdate,
    session: SessionDep,
) -> TagPublic:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_data = updated_data.model_dump(exclude_unset=True)
    tag.sqlmodel_update(tag_data)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    tag_type = session.get(TagType, tag.tag_type_id)
    if not tag_type or tag_type.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Set visibility of Tag


@router_tag.patch("/{tag_id}", response_model=TagPublic)
def visibility_tag(
    tag_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of Tag"),
) -> TagPublic:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.is_active = is_active
    session.add(tag)
    session.commit()
    session.refresh(tag)
    tag_type = session.get(TagType, tag.tag_type_id)
    if not tag_type or tag_type.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag Type not found")

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Delete a Tag
@router_tag.delete("/{tag_id}")
def delete_tag(tag_id: int, session: SessionDep) -> Message:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.is_deleted = True
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return Message(message="Tag deleted successfully")
