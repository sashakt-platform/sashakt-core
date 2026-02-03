import base64
import csv
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.orm import selectinload
from sqlmodel import and_, col, func, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
from app.api.routes.utils import clean_value
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
    Organization,
)
from app.models.candidate import CandidateTestProfile
from app.models.entity import EntityBulkUploadResponse
from app.models.location import Block, District, State
from app.models.user import User

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


def transform_entity_types_to_public(
    items: list[EntityType] | Any,
) -> list[EntityTypePublic]:
    result: list[EntityTypePublic] = []
    entity_type_list: list[EntityType] = (
        list(items) if not isinstance(items, list) else items
    )

    for entity_type in entity_type_list:
        result.append(EntityTypePublic(**entity_type.model_dump()))
    return result


def transform_entities_to_public(
    entities: list[Entity] | Any, current_user: CurrentUser
) -> list[EntityPublic]:
    result: list[EntityPublic] = []
    entity_list: list[Entity] = (
        entities if isinstance(entities, list) else list(entities)
    )

    for entity in entity_list:
        entity_type: EntityType | None = (
            entity.entity_type
            if entity.entity_type
            and entity.entity_type.organization_id == current_user.organization_id
            else None
        )

        state = entity.state if entity.state_id else None
        district = entity.district if entity.district_id else None
        block = entity.block if entity.block_id else None

        result.append(
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
    return result


# Routers for EntityType
@router_entitytype.post(
    "/",
    response_model=EntityTypePublic,
    dependencies=[Depends(permission_dependency("create_entity"))],
)
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


@router_entitytype.get(
    "/",
    response_model=Page[EntityTypePublic],
    dependencies=[Depends(permission_dependency("read_entity"))],
)
def get_entitytype(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[EntityTypePublic]:
    query = select(EntityType).where(
        EntityType.organization_id == current_user.organization_id,
    )
    if name:
        query = query.where(
            func.trim(func.lower(EntityType.name)).like(f"%{name.strip().lower()}%")
        )

    entity_types: Page[EntityTypePublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: transform_entity_types_to_public(items),
    )

    return entity_types


@router_entitytype.get(
    "/{entitytype_id}",
    response_model=EntityTypePublic,
    dependencies=[Depends(permission_dependency("read_entity"))],
)
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
@router_entitytype.put(
    "/{entitytype_id}",
    response_model=EntityTypePublic,
    dependencies=[Depends(permission_dependency("update_entity"))],
)
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
@router_entitytype.delete(
    "/{entitytype_id}", dependencies=[Depends(permission_dependency("delete_entity"))]
)
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
@router_entity.post(
    "/",
    response_model=EntityPublic,
    dependencies=[Depends(permission_dependency("create_entity"))],
)
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
@router_entity.get(
    "/",
    response_model=Page[EntityPublic],
    dependencies=[Depends(permission_dependency("read_entity"))],
)
def get_entities(
    session: SessionDep,
    current_user: CurrentUser,
    sorting: EntitySortingDep,
    params: Pagination = Depends(),
    name: str | None = None,
) -> Page[EntityPublic]:
    query = select(Entity).options(
        selectinload(Entity.entity_type),  # type: ignore[arg-type]
        selectinload(Entity.state),  # type: ignore[arg-type]
        selectinload(Entity.district),  # type: ignore[arg-type]
        selectinload(Entity.block),  # type: ignore[arg-type]
    )

    if name:
        query = query.where(
            func.trim(func.lower(Entity.name)).like(f"%{name.strip().lower()}%")
        )

    # apply default sorting if no sorting was specified
    sorting_with_default = sorting.apply_default_if_none("name", SortOrder.ASC)
    query = sorting_with_default.apply_to_query(query, EntitySortConfig)

    entities: Page[EntityPublic] = paginate(
        session,
        query,
        params,
        transformer=lambda items: transform_entities_to_public(items, current_user),
    )

    return entities


# Get Entity by ID
@router_entity.get(
    "/{entity_id}",
    response_model=EntityPublic,
    dependencies=[Depends(permission_dependency("read_entity"))],
)
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
@router_entity.put(
    "/{entity_id}",
    response_model=EntityPublic,
    dependencies=[Depends(permission_dependency("update_entity"))],
)
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
@router_entity.delete(
    "/{entity_id}", dependencies=[Depends(permission_dependency("delete_entity"))]
)
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


@router_entity.post(
    "/import",
    response_model=EntityBulkUploadResponse,
    dependencies=[Depends(permission_dependency("create_entity"))],
)
async def import_entities_from_csv(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(
        ...,
        description="CSV file with entity_name, entity_type_name, block_name, district_name, state_name",
    ),
) -> EntityBulkUploadResponse:
    user_id = current_user.id
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    organization_id = current_user.organization_id
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")

    try:
        content = (await file.read()).decode("utf-8")
        if not content.strip():
            raise HTTPException(status_code=400, detail="CSV file is empty")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file encoding")

    csv_reader = csv.DictReader(StringIO(content))
    required_headers = {
        "entity_name",
        "entity_type_name",
        "block_name",
        "district_name",
        "state_name",
    }
    if not required_headers.issubset(csv_reader.fieldnames or []):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain headers: {', '.join(required_headers)}",
        )

    states = session.exec(select(State.id, State.name)).all()
    state_map = {state_name.lower(): state_id for state_id, state_name in states}

    districts = session.exec(
        select(District.id, District.name, State.id).join(State)
    ).all()

    district_map = {
        (district_name.lower(), state_id): district_id
        for district_id, district_name, state_id in districts
    }

    entity_types = session.exec(
        select(EntityType).where(EntityType.organization_id == organization_id)
    ).all()

    entity_type_map = {
        entity_type.name.lower(): entity_type for entity_type in entity_types
    }

    # First pass: collect all filters from CSV
    csv_state_ids: set[int] = set()
    csv_district_ids: set[int] = set()
    csv_block_ids: set[int] = set()
    csv_entity_type_ids: set[int] = set()

    for rows in csv_reader:
        district_name = clean_value(rows.get("district_name"))
        state_name = clean_value(rows.get("state_name"))
        block_name = clean_value(rows.get("block_name"))
        entity_type_name = clean_value(rows.get("entity_type_name"))

        state_id = state_map.get(state_name.lower())
        if state_id:
            csv_state_ids.add(state_id)

            district_id = district_map.get((district_name.lower(), state_id))
            if district_id:
                csv_district_ids.add(district_id)

        entity_type = entity_type_map.get(entity_type_name.lower())
        if entity_type and entity_type.id:
            csv_entity_type_ids.add(entity_type.id)

    block_map = {}

    if csv_district_ids:
        existing_block_rows = session.exec(
            select(Block.id, Block.name, Block.district_id).where(
                col(Block.district_id).in_(csv_district_ids)
            )
        ).all()
        block_map = {
            (block_name.lower(), district_id): block_id
            for block_id, block_name, district_id in existing_block_rows
        }
        csv_block_ids.update(
            block_id for block_id in block_map.values() if block_id is not None
        )

    existing_entity_map = {}

    filters = []
    if csv_entity_type_ids:
        filters = [
            col(Entity.entity_type_id).in_(csv_entity_type_ids),
        ]
        if csv_block_ids:
            filters.append(col(Entity.block_id).in_(csv_block_ids))
        if csv_district_ids:
            filters.append(col(Entity.district_id).in_(csv_district_ids))
        if csv_state_ids:
            filters.append(col(Entity.state_id).in_(csv_state_ids))
    existing_entities = session.exec(select(Entity).where(*filters)).all()
    existing_entity_map = {
        (
            entity.name.lower(),
            entity.block_id,
            entity.district_id,
            entity.state_id,
            entity.entity_type_id,
        ): entity
        for entity in existing_entities
    }

    csv_reader = csv.DictReader(StringIO(content))

    success_count = failed_count = 0
    failed_entity_details = []
    failed_references = set()
    duplicate_entities = set()
    new_entities_to_add = []

    for row_num, row in enumerate(csv_reader, start=1):
        try:
            entity_name = clean_value(row.get("entity_name"))
            entity_type_name = clean_value(row.get("entity_type_name"))
            block_name = clean_value(row.get("block_name"))
            district_name = clean_value(row.get("district_name"))
            state_name = clean_value(row.get("state_name"))

            if not all(
                [entity_name, entity_type_name, block_name, district_name, state_name]
            ):
                raise ValueError("Missing required value(s)")

            state_id = state_map.get(state_name.lower())
            if not state_id:
                failed_references.add(state_name)
                raise ValueError(f"State '{state_name}' not found")

            district_id = district_map.get((district_name.lower(), state_id or 0))
            if not district_id:
                failed_references.add(f"{district_name} in {state_name}")
                raise ValueError(f"District '{district_name}' not found")

            block_id = block_map.get((block_name.lower(), district_id or 0))
            if not block_id:
                failed_references.add(f"{block_name} in {district_name}")
                raise ValueError(f"Block '{block_name}' not found")

            entity_type = entity_type_map.get(entity_type_name.lower())
            if not entity_type:
                failed_references.add(entity_type_name)
                raise ValueError(f"Entity type '{entity_type_name}' not found")

            if (
                entity_name.lower(),
                block_id,
                district_id,
                state_id,
                entity_type.id,
            ) in existing_entity_map:
                duplicate_entities.add(entity_name)
                raise ValueError("Entity already exists")
            new_entity = Entity(
                name=entity_name,
                created_by_id=user_id,
                entity_type_id=entity_type.id,
                state_id=state_id,
                district_id=district_id,
                block_id=block_id,
                is_active=True,
            )

            new_entities_to_add.append(new_entity)

            success_count += 1

        except Exception as e:
            failed_count += 1
            failed_entity_details.append(
                {
                    "row_number": row_num,
                    "entity_name": entity_name,
                    "entity_type_name": entity_type_name,
                    "block_name": block_name,
                    "district_name": district_name,
                    "state_name": state_name,
                    "error": str(e),
                }
            )

    if new_entities_to_add:
        session.add_all(new_entities_to_add)
        session.commit()

    error_log = None
    if failed_entity_details:
        csv_buffer = StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "row_number",
                "entity_name",
                "entity_type_name",
                "block_name",
                "district_name",
                "state_name",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(failed_entity_details)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        error_log = (
            f"data:text/csv;base64,{base64.b64encode(csv_bytes).decode('utf-8')}"
        )

    message = f"Bulk upload complete. Created {success_count} entities successfully. Failed to create {failed_count} entities."
    if failed_references:
        message += f" Missing references: {', '.join(failed_references)}."
    if duplicate_entities:
        message += f" Duplicates skipped: {', '.join(duplicate_entities)}."

    return EntityBulkUploadResponse(
        message=message,
        uploaded_entities=success_count + failed_count,
        success_entities=success_count,
        failed_entities=failed_count,
        error_log=error_log,
    )
