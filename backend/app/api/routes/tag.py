from typing import cast

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi_pagination import Page, paginate
from sqlmodel import and_, col, exists, func, not_, or_, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
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
from app.models.question import Question, QuestionTag
from app.models.tag import DeleteTagtype
from app.models.test import Test, TestTag

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


def check_linked_tag(session: SessionDep, tagtype_id: int) -> bool:
    has_active_tags = session.exec(
        select(Tag).where(
            Tag.tag_type_id == tagtype_id,
        )
    ).first()

    return bool(has_active_tags)


@router_tagtype.post("/", response_model=TagTypePublic)
def create_tagtype(
    tagtype_create: TagTypeCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TagType:
    normalized_name = tagtype_create.name.strip().lower()
    existing = session.exec(
        select(TagType)
        .where(func.lower(func.trim(TagType.name)) == normalized_name)
        .where(TagType.organization_id == tagtype_create.organization_id)
        .where(not_(TagType.is_deleted))
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"TagType with name '{tagtype_create.name}' already exists in this organization.",
        )
    tag_type = TagType(
        **tagtype_create.model_dump(),
        created_by_id=current_user.id,
    )

    session.add(tag_type)
    session.commit()
    session.refresh(tag_type)
    return tag_type


@router_tagtype.get("/", response_model=Page[TagTypePublic])
def get_tagtype(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[TagType]:
    query = select(TagType).where(
        TagType.organization_id == current_user.organization_id,
        not_(TagType.is_deleted),
    )
    if name:
        query = query.where(
            func.trim(func.lower(TagType.name)).like(f"%{name.strip().lower()}%")
        )

    tagtype = session.exec(query).all()
    return cast(Page[TagType], paginate(tagtype, params=params))


@router_tagtype.get("/{tagtype_id}", response_model=TagTypePublic)
def get_tagtype_by_id(
    tagtype_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TagType:
    tagtype = session.get(TagType, tagtype_id)
    if (
        not tagtype
        or tagtype.is_deleted is True
        or tagtype.organization_id != current_user.organization_id
    ):
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


@router_tagtype.patch(
    "/{tagtype_id}",
    response_model=TagTypePublic,
    dependencies=[Depends(permission_dependency("delete_tag"))],
)
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
    if not tagtype:
        raise HTTPException(status_code=404, detail="Tag Type not found")

    if check_linked_tag(session, tagtype_id):
        raise HTTPException(
            status_code=400, detail="Cannot delete Tag Type as it has associated Tags"
        )
    session.delete(tagtype)
    session.commit()
    return Message(message="Tag Type deleted successfully")


@router_tagtype.delete(
    "/",
    response_model=DeleteTagtype,
    dependencies=[Depends(permission_dependency("delete_tag"))],
)
def bulk_delete_tagtype(
    session: SessionDep, tagtype_ids: list[int] = Body(...)
) -> DeleteTagtype:
    """Soft delete a question."""
    success_count = 0
    failure_list = []
    db_tagtype = session.exec(
        select(TagType).where(col(TagType.id).in_(tagtype_ids))
    ).all()

    found_ids = {q.id for q in db_tagtype}
    missing_ids = set(tagtype_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404, detail=f"Tagtype IDs not found in DB: {missing_ids}"
        )

    for tagtype in db_tagtype:
        if tagtype.id and check_linked_tag(session, tagtype.id):
            failure_list.append(
                TagTypePublic(
                    **tagtype.model_dump(),
                )
            )
        else:
            session.delete(tagtype)
            success_count += 1

    session.commit()

    return DeleteTagtype(
        delete_success_count=success_count, delete_failure_list=failure_list or None
    )


# Routers for Tags


# Create a Tag
@router_tag.post("/", response_model=TagPublic)
def create_tag(
    tag_create: TagCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TagPublic:
    tag_type = None
    tag_type_id = tag_create.tag_type_id
    if tag_type_id is not None:
        tag_type = session.get(TagType, tag_type_id)
        if not tag_type or tag_type.is_deleted is True:
            raise HTTPException(status_code=404, detail="Tag Type not found")
        organization_id = tag_type.organization_id
    else:
        organization_id = current_user.organization_id
    existing_tag = session.exec(
        select(Tag).where(
            and_(
                func.lower(func.trim(Tag.name)) == tag_create.name.strip().lower(),
                Tag.organization_id == organization_id,
                not_(Tag.is_deleted),
                or_(
                    and_(
                        Tag.tag_type_id is None,
                        tag_type_id is None,
                    ),
                    Tag.tag_type_id == tag_type_id,
                ),
            )
        )
    ).first()

    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail="A tag with the same name and tag type already exists.",
        )

    tag_data = tag_create.model_dump(exclude_unset=True)

    tag_data["organization_id"] = organization_id
    tag_data["created_by_id"] = current_user.id
    tag = Tag.model_validate(tag_data)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    if tag_type:
        session.refresh(tag_type)

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Get all Tags
@router_tag.get("/", response_model=Page[TagPublic])
def get_tags(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
    order_by: list[str] = Query(
        default=["tag_type_name", "name"],
        title="Order by",
        description="Order by fields: tag_type_name, name. Prefix with '-' for descending.",
        examples=["-name", "tag_type_name"],
    ),
) -> Page[TagPublic]:
    query = select(Tag).where(
        Tag.organization_id == current_user.organization_id, not_(Tag.is_deleted)
    )
    if name:
        query = query.where(
            func.trim(func.lower(Tag.name)).like(f"%{name.strip().lower()}%")
        )
    join_tag_type = any("tag_type_name" in field for field in order_by)
    if join_tag_type:
        query = query.outerjoin(TagType)

    ordering = []
    for field in order_by:
        desc = field.startswith("-")
        field_name = field[1:] if desc else field
        if field_name == "tag_type_name":
            col = getattr(TagType, "name", None)
        else:
            col = getattr(Tag, field_name, None)

        if col is None:
            continue
        ordering.append(col.desc() if desc else col.asc())
    if ordering:
        query = query.order_by(*ordering)
    tags = session.exec(query).all()
    tag_public = []
    for tag in tags:
        tag_type = None
        if tag.tag_type_id:
            tag_type = session.get(TagType, tag.tag_type_id)

            if (
                not tag_type
                or tag_type.is_deleted is True
                or tag_type.organization_id != current_user.organization_id
            ):
                tag_type = None

        tag_public.append(
            TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)
        )

    return cast(Page[TagPublic], paginate(tag_public, params=params))


# Get Tag by ID
@router_tag.get("/{tag_id}", response_model=TagPublic)
def get_tag_by_id(
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TagPublic:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_type = None
    if tag.tag_type_id:
        tag_type = session.get(TagType, tag.tag_type_id)
        if (
            not tag_type
            or tag_type.is_deleted is True
            or tag_type.organization_id != current_user.organization_id
        ):
            tag_type = None
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
    tag_type_id = tag_data.get("tag_type_id")
    if tag_type_id is not None:
        tag_type = session.get(TagType, tag_type_id)
        if not tag_type or tag_type.is_deleted:
            raise HTTPException(status_code=404, detail="Tag Type not found")
    tag.sqlmodel_update(tag_data)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    tag_type = session.get(TagType, tag.tag_type_id) if tag.tag_type_id else None

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Set visibility of Tag


@router_tag.patch("/{tag_id}", response_model=TagPublic)
def visibility_tag(
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    is_active: bool = Query(False, description="Set visibility of Tag"),
) -> TagPublic:
    tag = session.get(Tag, tag_id)
    if not tag or tag.is_deleted is True:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.is_active = is_active
    session.add(tag)
    session.commit()
    session.refresh(tag)
    tag_type = None
    if tag.tag_type_id:
        tag_type = session.get(TagType, tag.tag_type_id)
        if (
            not tag_type
            or tag_type.is_deleted is True
            or tag_type.organization_id != current_user.organization_id
        ):
            tag_type = None

    return TagPublic(**tag.model_dump(exclude={"tag_type_id"}), tag_type=tag_type)


# Delete a Tag
@router_tag.delete("/{tag_id}")
def delete_tag(tag_id: int, session: SessionDep) -> Message:
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    has_questions = session.exec(
        select(
            exists().where(
                and_(
                    QuestionTag.tag_id == tag_id,
                    QuestionTag.question_id == Question.id,
                    not_(Question.is_deleted),
                )
            )
        )
    ).one()
    has_tests = session.exec(
        select(
            exists().where(
                and_(
                    TestTag.tag_id == tag_id,
                    TestTag.test_id == Test.id,
                    not_(Test.is_deleted),
                )
            )
        )
    ).one()

    if has_questions or has_tests:
        raise HTTPException(
            status_code=400,
            detail="Tag is associated with a question or test and cannot be deleted.",
        )

    session.delete(tag)
    session.commit()

    return Message(message="Tag deleted successfully")
