from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page, paginate
from sqlmodel import and_, func, select

from app.api.deps import CurrentUser, Pagination, SessionDep
from app.core.sorting import (
    EntitySortConfig,
    SortingParams,
    SortOrder,
    create_sorting_dependency,
)
from app.models import (
    Entity,
    EntityCreate,
    EntityPublic,
    EntityType,
    EntityTypeCreate,
    EntityTypePublic,
    EntityTypeUpdate,
    EntityUpdate,
    Message,
)
from app.models.candidate import CandidateTestProfile
from app.models.location import Block, District, State

router_entitytype = APIRouter(
    prefix="/entitytype",
    tags=["EntityType"],
)
router_entity = APIRouter(
    prefix="/entity",
    tags=["Entity"],
)

# create sorting dependency
EntitySorting = create_sorting_dependency(EntitySortConfig)
EntitySortingDep = Annotated[SortingParams, Depends(EntitySorting)]


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
    if not entitytype or entitytype.organization_id != current_user.organization_id:
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
    if not entitytype:
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
            Entity.entity_type_id == entitytype_id,
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
    if not entity_type:
        raise HTTPException(status_code=404, detail="EntityType not found")

    # Check for duplicate entity name within same type and organization
    existing_entity = session.exec(
        select(Entity).where(
            and_(
                func.lower(func.trim(Entity.name))
                == entity_create.name.strip().lower(),
                Entity.entity_type_id == entity_type_id,
                Entity.state_id == entity_create.state_id,
                Entity.district_id == entity_create.district_id,
                Entity.block_id == entity_create.block_id,
            )
        )
    ).first()

    if existing_entity:
        raise HTTPException(
            status_code=400,
            detail="An entity with the same name and entity type already exists.",
        )

    entity_data = entity_create.model_dump(exclude_unset=True)
    entity_data["created_by_id"] = current_user.id

    entity = Entity.model_validate(entity_data)
    session.add(entity)
    session.commit()
    session.refresh(entity)
    session.refresh(entity_type)
    state = session.get(State, entity.state_id) if entity.state_id else None
    district = session.get(District, entity.district_id) if entity.district_id else None
    block = session.get(Block, entity.block_id) if entity.block_id else None

    return EntityPublic(
        **entity.model_dump(exclude={"entity_type_id"}),
        entity_type=entity_type,
        state=state,
        district=district,
        block=block,
    )


# Get all Entities
@router_entity.get("/", response_model=Page[EntityPublic])
def get_entities(
    session: SessionDep,
    current_user: CurrentUser,
    sorting: EntitySortingDep,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[EntityPublic]:
    query = select(Entity)

    if name:
        query = query.where(
            func.trim(func.lower(Entity.name)).like(f"%{name.strip().lower()}%")
        )

    # apply default sorting if no sorting was specified
    sorting_with_default = sorting.apply_default_if_none("name", SortOrder.ASC)
    query = sorting_with_default.apply_to_query(query, EntitySortConfig)

    entities = session.exec(query).all()
    entity_public_list = []
    for entity in entities:
        entity_type = None
        if entity.entity_type_id:
            entity_type = session.get(EntityType, entity.entity_type_id)

            if (
                not entity_type
                or entity_type.organization_id != current_user.organization_id
            ):
                entity_type = None
        state = session.get(State, entity.state_id) if entity.state_id else None
        district = (
            session.get(District, entity.district_id) if entity.district_id else None
        )
        block = session.get(Block, entity.block_id) if entity.block_id else None

        entity_public_list.append(
            EntityPublic(
                **entity.model_dump(
                    exclude={"entity_type_id", "state_id", "district_id", "block_id"}
                ),
                entity_type=entity_type,
                state=state,
                district=district,
                block=block,
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
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity_type = None
    if entity.entity_type_id:
        entity_type = session.get(EntityType, entity.entity_type_id)
        if (
            not entity_type
            or entity_type.organization_id != current_user.organization_id
        ):
            entity_type = None
    state = session.get(State, entity.state_id) if entity.state_id else None
    district = session.get(District, entity.district_id) if entity.district_id else None
    block = session.get(Block, entity.block_id) if entity.block_id else None

    return EntityPublic(
        **entity.model_dump(
            exclude={"entity_type_id", "state_id", "district_id", "block_id"}
        ),
        entity_type=entity_type,
        state=state,
        district=district,
        block=block,
    )


# Update an Entity
@router_entity.put("/{entity_id}", response_model=EntityPublic)
def update_entity(
    entity_id: int,
    updated_data: EntityUpdate,
    session: SessionDep,
) -> EntityPublic:
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity_data = updated_data.model_dump(exclude_unset=True)

    entity_type_id = entity_data.get("entity_type_id")
    if entity_type_id is not None:
        entity_type = session.get(EntityType, entity_type_id)
        if not entity_type:
            raise HTTPException(status_code=404, detail="EntityType not found")
    else:
        raise HTTPException(
            status_code=400, detail="EntityType is required for an entity."
        )

    entity.sqlmodel_update(entity_data)
    session.add(entity)
    session.commit()
    session.refresh(entity)

    entity_type = session.get(EntityType, entity.entity_type_id)
    state = session.get(State, entity.state_id) if entity.state_id else None
    district = session.get(District, entity.district_id) if entity.district_id else None
    block = session.get(Block, entity.block_id) if entity.block_id else None

    return EntityPublic(
        **entity.model_dump(
            exclude={"entity_type_id", "state_id", "district_id", "block_id"}
        ),
        entity_type=entity_type,
        state=state,
        district=district,
        block=block,
    )


# Delete an Entity
@router_entity.delete("/{entity_id}")
def delete_entity(entity_id: int, session: SessionDep) -> Message:
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    attempted_entity_exists = session.exec(
        select(CandidateTestProfile).where(CandidateTestProfile.entity_id == entity.id)
    ).first()
    if attempted_entity_exists:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete entity because it is referenced in Candidate Profile",
        )

    session.delete(entity)
    session.commit()

    return Message(message="Entity deleted successfully")
