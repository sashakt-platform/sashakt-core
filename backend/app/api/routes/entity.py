from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, paginate
from sqlmodel import and_, func, not_, select

from app.api.deps import CurrentUser, Pagination, SessionDep
from app.models import (
    Entity,
    EntityType,
    EntityTypeCreate,
    EntityTypePublic,
    EntityTypeUpdate,
    Message,
)
from app.models.entity import EntityCreate, EntityPublic, EntityUpdate

router_entitytype = APIRouter(
    prefix="/entitytype",
    tags=["EntityType"],
)
router_entity = APIRouter(
    prefix="/entity",
    tags=["Entity"],
)


# Routers for EntityType
@router_entitytype.post("/", response_model=EntityTypePublic)
def create_entitytype(
    entitytype_create: EntityTypeCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> EntityType:
    normalized_name = entitytype_create.name.strip().lower()
    existing = session.exec(
        select(EntityType)
        .where(func.lower(func.trim(EntityType.name)) == normalized_name)
        .where(EntityType.organization_id == entitytype_create.organization_id)
        .where(not_(EntityType.is_deleted))
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"EntityType with name '{entitytype_create.name}' already exists in this organization.",
        )
    entity_type = EntityType(
        **entitytype_create.model_dump(),
        created_by_id=current_user.id,
    )

    session.add(entity_type)
    session.commit()
    session.refresh(entity_type)
    return entity_type


@router_entitytype.get("/", response_model=Page[EntityTypePublic])
def get_entitytype(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[EntityType]:
    query = select(EntityType).where(
        EntityType.organization_id == current_user.organization_id,
        not_(EntityType.is_deleted),
    )
    if name:
        query = query.where(
            func.trim(func.lower(EntityType.name)).like(f"%{name.strip().lower()}%")
        )

    entitytypes = session.exec(query).all()
    return cast(Page[EntityType], paginate(entitytypes, params=params))


@router_entitytype.get("/{entitytype_id}", response_model=EntityTypePublic)
def get_entitytype_by_id(
    entitytype_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> EntityType:
    entitytype = session.get(EntityType, entitytype_id)
    if (
        not entitytype
        or entitytype.is_deleted is True
        or entitytype.organization_id != current_user.organization_id
    ):
        raise HTTPException(status_code=404, detail="EntityType not found")
    return entitytype


# Update EntityType
@router_entitytype.put("/{entitytype_id}", response_model=EntityTypePublic)
def update_entitytype(
    entitytype_id: int,
    updated_data: EntityTypeUpdate,
    session: SessionDep,
) -> EntityType:
    entitytype = session.get(EntityType, entitytype_id)
    if not entitytype or entitytype.is_deleted is True:
        raise HTTPException(status_code=404, detail="EntityType not found")

    entitytype_data = updated_data.model_dump(exclude_unset=True)
    entitytype.sqlmodel_update(entitytype_data)

    session.add(entitytype)
    session.commit()
    session.refresh(entitytype)
    return entitytype


# Delete EntityType
@router_entitytype.delete("/{entitytype_id}")
def delete_entitytype(entitytype_id: int, session: SessionDep) -> Message:
    entitytype = session.get(EntityType, entitytype_id)
    if not entitytype:
        raise HTTPException(status_code=404, detail="EntityType not found")

    has_active_entities = session.exec(
        select(Entity).where(
            Entity.entity_type_id == entitytype_id, not_(Entity.is_deleted)
        )
    ).first()

    if has_active_entities:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete EntityType as it has associated Entities",
        )

    session.delete(entitytype)
    session.commit()
    return Message(message="EntityType deleted successfully")


# Create an Entity (EntityType required)
@router_entity.post("/", response_model=EntityPublic)
def create_entity(
    entity_create: EntityCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> EntityPublic:
    entity_type_id = entity_create.entity_type_id
    if entity_type_id is None:
        raise HTTPException(
            status_code=400, detail="EntityType is required for creating an entity."
        )

    entity_type = session.get(EntityType, entity_type_id)
    if not entity_type or entity_type.is_deleted is True:
        raise HTTPException(status_code=404, detail="EntityType not found")

    organization_id = entity_type.organization_id

    # Check for duplicate entity name within same type and organization
    existing_entity = session.exec(
        select(Entity).where(
            and_(
                func.lower(func.trim(Entity.name))
                == entity_create.name.strip().lower(),
                Entity.organization_id == organization_id,
                not_(Entity.is_deleted),
                Entity.entity_type_id == entity_type_id,
            )
        )
    ).first()

    if existing_entity:
        raise HTTPException(
            status_code=400,
            detail="An entity with the same name and entity type already exists.",
        )

    entity_data = entity_create.model_dump(exclude_unset=True)
    entity_data["organization_id"] = organization_id
    entity_data["created_by_id"] = current_user.id

    entity = Entity.model_validate(entity_data)
    session.add(entity)
    session.commit()
    session.refresh(entity)
    session.refresh(entity_type)

    return EntityPublic(
        **entity.model_dump(exclude={"entity_type_id"}), entity_type=entity_type
    )


# Get all Entities
@router_entity.get("/", response_model=Page[EntityPublic])
def get_entities(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
    order_by: list[str] = Query(
        default=["entity_type_name", "name"],
        title="Order by",
        description="Order by fields: entity_type_name, name. Prefix with '-' for descending.",
        examples=["-name", "entity_type_name"],
    ),
) -> Page[EntityPublic]:
    query = select(Entity).where(
        Entity.organization_id == current_user.organization_id,
        not_(Entity.is_deleted),
    )

    if name:
        query = query.where(
            func.trim(func.lower(Entity.name)).like(f"%{name.strip().lower()}%")
        )

    join_entity_type = any("entity_type_name" in field for field in order_by)
    if join_entity_type:
        query = query.outerjoin(EntityType)

    ordering = []
    for field in order_by:
        desc = field.startswith("-")
        field_name = field[1:] if desc else field
        if field_name == "entity_type_name":
            col = getattr(EntityType, "name", None)
        else:
            col = getattr(Entity, field_name, None)

        if col is None:
            continue
        ordering.append(col.desc() if desc else col.asc())

    if ordering:
        query = query.order_by(*ordering)

    entities = session.exec(query).all()
    entity_public_list = []
    for entity in entities:
        entity_type = None
        if entity.entity_type_id:
            entity_type = session.get(EntityType, entity.entity_type_id)

            if (
                not entity_type
                or entity_type.is_deleted is True
                or entity_type.organization_id != current_user.organization_id
            ):
                entity_type = None

        entity_public_list.append(
            EntityPublic(
                **entity.model_dump(exclude={"entity_type_id"}), entity_type=entity_type
            )
        )

    return cast(Page[EntityPublic], paginate(entity_public_list, params=params))


# Get Entity by ID
@router_entity.get("/{entity_id}", response_model=EntityPublic)
def get_entity_by_id(
    entity_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> EntityPublic:
    entity = session.get(Entity, entity_id)
    if not entity or entity.is_deleted is True:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity_type = None
    if entity.entity_type_id:
        entity_type = session.get(EntityType, entity.entity_type_id)
        if (
            not entity_type
            or entity_type.is_deleted is True
            or entity_type.organization_id != current_user.organization_id
        ):
            entity_type = None

    return EntityPublic(
        **entity.model_dump(exclude={"entity_type_id"}), entity_type=entity_type
    )


# Update an Entity
@router_entity.put("/{entity_id}", response_model=EntityPublic)
def update_entity(
    entity_id: int,
    updated_data: EntityUpdate,
    session: SessionDep,
) -> EntityPublic:
    entity = session.get(Entity, entity_id)
    if not entity or entity.is_deleted is True:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity_data = updated_data.model_dump(exclude_unset=True)

    entity_type_id = entity_data.get("entity_type_id")
    if entity_type_id is not None:
        entity_type = session.get(EntityType, entity_type_id)
        if not entity_type or entity_type.is_deleted:
            raise HTTPException(status_code=404, detail="EntityType not found")
        entity_data["organization_id"] = entity_type.organization_id
    else:
        raise HTTPException(
            status_code=400, detail="EntityType is required for an entity."
        )

    entity.sqlmodel_update(entity_data)
    session.add(entity)
    session.commit()
    session.refresh(entity)

    entity_type = session.get(EntityType, entity.entity_type_id)

    return EntityPublic(
        **entity.model_dump(exclude={"entity_type_id"}), entity_type=entity_type
    )


# Delete an Entity
@router_entity.delete("/{entity_id}")
def delete_entity(entity_id: int, session: SessionDep) -> Message:
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    session.delete(entity)
    session.commit()

    return Message(message="Entity deleted successfully")
