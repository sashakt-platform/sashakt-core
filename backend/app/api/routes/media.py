"""Media upload endpoints for questions."""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.api.routes.question import check_question_permission
from app.core.media import (
    build_external_media_dict,
    build_image_media_dict,
    validate_external_media_url,
    validate_image_upload,
)
from app.core.provider_config import provider_config_service
from app.core.roles import state_admin, test_admin
from app.models import Message
from app.models.provider import OrganizationProvider, Provider, ProviderType
from app.models.question import (
    MatrixColumn,
    MatrixInputOptions,
    MatrixMatchOptions,
    Option,
    Question,
    QuestionRevision,
)
from app.models.role import Role
from app.services.storage.gcs import GCSStorageService

router = APIRouter(prefix="/media", tags=["Media"])


# Response models


class ImageUploadResponse(BaseModel):
    """Response for successful image upload."""

    gcs_path: str
    content_type: str
    size_bytes: int


class ExternalMediaResponse(BaseModel):
    """Response for external media registration."""

    type: str
    provider: str
    url: str
    embed_url: str | None
    thumbnail_url: str | None


# Helper functions


def get_gcs_service(session: SessionDep, organization_id: int) -> GCSStorageService:
    """Get GCS service for an organization."""
    statement = (
        select(OrganizationProvider)
        .join(Provider)
        .where(
            OrganizationProvider.organization_id == organization_id,
            OrganizationProvider.is_enabled == True,  # noqa: E712
            Provider.provider_type == ProviderType.GCS,
            Provider.is_active == True,  # noqa: E712
        )
    )
    org_provider = session.exec(statement).first()

    if not org_provider or not org_provider.config_json:
        raise HTTPException(
            status_code=400,
            detail="GCS storage is not configured for this organization",
        )

    config = provider_config_service.get_config_for_use(org_provider.config_json)
    return GCSStorageService(organization_id, config)


def get_question_with_permission(
    session: SessionDep, question_id: int, current_user: CurrentUser
) -> Question:
    """Get question and verify user has permission to modify it."""
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    role = session.get(Role, current_user.role_id)
    if role and role.name in (state_admin.name, test_admin.name):
        check_question_permission(session, current_user, question)

    return question


def get_revision(session: SessionDep, question: Question) -> QuestionRevision:
    """Get the current revision of a question."""
    if not question.last_revision_id:
        raise HTTPException(status_code=404, detail="Question has no revision")

    revision = session.get(QuestionRevision, question.last_revision_id)
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    return revision


def find_option(
    options: MatrixMatchOptions | MatrixInputOptions | list[Option] | None,
    option_id: int,
) -> tuple[list[Option], int, str | None]:
    """Find option by ID across flat list or matrix match/input structure.

    Returns (items_list, index, matrix_key).
    matrix_key is None for flat lists, "rows" or "columns" for matrix match,
    "rows" only for matrix input (columns has no selectable items).
    """
    if not options:
        raise HTTPException(status_code=404, detail="Question has no options")

    if isinstance(options, list):
        for i, opt in enumerate(options):
            if opt.get("id") == option_id:
                return options, i, None
    else:
        opts: Any = options

        is_matrix_input = "input_type" in opts.get("columns", {})
        keys: tuple[str, ...] = ("rows",) if is_matrix_input else ("rows", "columns")
        for key in keys:
            items = opts[key]["items"]
            for i, opt in enumerate(items):
                if opt.get("id") == option_id:
                    return items, i, key

    raise HTTPException(status_code=404, detail="Option not found")


def rebuild_options(
    original: MatrixMatchOptions | MatrixInputOptions | list[Option] | None,
    updated_items: list[Option],
    matrix_key: str | None,
) -> MatrixMatchOptions | MatrixInputOptions | list[Option]:
    """Rebuild options structure after modifying an items list."""
    if matrix_key is None:
        return updated_items
    assert isinstance(original, dict)
    orig: Any = original
    is_matrix_input = "input_type" in orig.get("columns", {})
    if is_matrix_input:
        rows = orig["rows"]
        return MatrixInputOptions(
            rows=MatrixColumn(label=rows["label"], items=updated_items),
            columns=orig["columns"],
        )
    rows = orig["rows"]
    columns = orig["columns"]
    if matrix_key == "rows":
        rows = {"label": rows["label"], "items": updated_items}
    else:
        columns = {"label": columns["label"], "items": updated_items}
    return MatrixMatchOptions(rows=rows, columns=columns)


# Question image endpoints


@router.post(
    "/questions/{question_id}/image",
    response_model=ImageUploadResponse,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def upload_question_image(
    question_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    alt_text: str | None = Form(None),
) -> ImageUploadResponse:
    """Upload an image for a question."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Validate image
    file_content, file_extension, content_type = await validate_image_upload(file)

    # Get GCS service and upload
    gcs_service = get_gcs_service(session, question.organization_id)
    gcs_path = gcs_service.generate_media_path(question_id, file_extension)
    gcs_service.upload(file_content, gcs_path, content_type)

    # Update revision media, rolling back GCS upload if commit fails
    try:
        media = dict(revision.media) if revision.media else {}
        media["image"] = build_image_media_dict(
            gcs_path=gcs_path,
            content_type=content_type,
            size_bytes=len(file_content),
            alt_text=alt_text,
        )
        revision.media = media
        flag_modified(revision, "media")
        session.add(revision)
        session.commit()
    except Exception:
        session.rollback()
        gcs_service.delete(gcs_path)
        raise

    return ImageUploadResponse(
        gcs_path=gcs_path,
        content_type=content_type,
        size_bytes=len(file_content),
    )


@router.delete(
    "/questions/{question_id}/image",
    response_model=Message,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def delete_question_image(
    question_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete the image for a question."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    if not revision.media or "image" not in revision.media:
        raise HTTPException(status_code=404, detail="No image found for this question")

    # Capture GCS path before modifying metadata
    gcs_path = revision.media["image"].get("gcs_path")

    # Update revision first
    media = dict(revision.media)
    del media["image"]
    revision.media = media if media else None
    flag_modified(revision, "media")
    session.add(revision)
    session.commit()

    # Delete from GCS after successful commit
    if gcs_path:
        gcs_service = get_gcs_service(session, question.organization_id)
        gcs_service.delete(gcs_path)

    return Message(message="Image deleted successfully")


# Question external media endpoints


@router.post(
    "/questions/{question_id}/external",
    response_model=ExternalMediaResponse,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def add_question_external_media(
    question_id: int,
    url: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> ExternalMediaResponse:
    """Add external media (YouTube, Vimeo, etc.) to a question."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Validate and parse URL
    external_media = validate_external_media_url(url)

    # Update revision
    media = dict(revision.media) if revision.media else {}
    media["external_media"] = build_external_media_dict(external_media)
    revision.media = media
    flag_modified(revision, "media")
    session.add(revision)
    session.commit()

    return ExternalMediaResponse(
        type=external_media.type,
        provider=external_media.provider,
        url=external_media.url,
        embed_url=external_media.embed_url,
        thumbnail_url=external_media.thumbnail_url,
    )


@router.delete(
    "/questions/{question_id}/external",
    response_model=Message,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def delete_question_external_media(
    question_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Remove external media from a question."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    if not revision.media or "external_media" not in revision.media:
        raise HTTPException(
            status_code=404, detail="No external media found for this question"
        )

    # Update revision
    media = dict(revision.media)
    del media["external_media"]
    revision.media = media if media else None
    flag_modified(revision, "media")
    session.add(revision)
    session.commit()

    return Message(message="External media removed successfully")


# Option image endpoints


@router.post(
    "/questions/{question_id}/options/{option_id}/image",
    response_model=ImageUploadResponse,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def upload_option_image(
    question_id: int,
    option_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    alt_text: str | None = Form(None),
) -> ImageUploadResponse:
    """Upload an image for a specific option."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Find the option
    items, option_index, matrix_key = find_option(revision.options, option_id)

    # Validate image
    file_content, file_extension, content_type = await validate_image_upload(file)

    # Get GCS service and upload
    gcs_service = get_gcs_service(session, question.organization_id)
    gcs_path = gcs_service.generate_media_path(question_id, file_extension, option_id)
    gcs_service.upload(file_content, gcs_path, content_type)

    # Update option with media, rolling back GCS upload if commit fails
    try:
        updated_items = list(items)
        option_media = {
            "image": build_image_media_dict(
                gcs_path=gcs_path,
                content_type=content_type,
                size_bytes=len(file_content),
                alt_text=alt_text,
            )
        }
        updated_items[option_index]["media"] = option_media
        revision.options = rebuild_options(revision.options, updated_items, matrix_key)
        flag_modified(revision, "options")
        session.add(revision)
        session.commit()
    except Exception:
        session.rollback()
        gcs_service.delete(gcs_path)
        raise

    return ImageUploadResponse(
        gcs_path=gcs_path,
        content_type=content_type,
        size_bytes=len(file_content),
    )


@router.delete(
    "/questions/{question_id}/options/{option_id}/image",
    response_model=Message,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def delete_option_image(
    question_id: int,
    option_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete the image for a specific option."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Find the option
    items, option_index, matrix_key = find_option(revision.options, option_id)

    updated_items = list(items)
    option = updated_items[option_index]

    option_media = option.get("media")
    if not option_media or "image" not in option_media:
        raise HTTPException(status_code=404, detail="No image found for this option")

    # Capture GCS path before modifying metadata
    gcs_path = option_media["image"].get("gcs_path")

    # Update option first
    del option_media["image"]
    if not option_media:
        del updated_items[option_index]["media"]
    else:
        updated_items[option_index]["media"] = option_media

    revision.options = rebuild_options(revision.options, updated_items, matrix_key)
    flag_modified(revision, "options")
    session.add(revision)
    session.commit()

    # Delete from GCS after successful commit
    if gcs_path:
        gcs_service = get_gcs_service(session, question.organization_id)
        gcs_service.delete(gcs_path)

    return Message(message="Option image deleted successfully")


# Option external media endpoints


@router.post(
    "/questions/{question_id}/options/{option_id}/external",
    response_model=ExternalMediaResponse,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def add_option_external_media(
    question_id: int,
    option_id: int,
    url: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> ExternalMediaResponse:
    """Add external media to a specific option."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Find the option
    items, option_index, matrix_key = find_option(revision.options, option_id)

    # Validate and parse URL
    external_media = validate_external_media_url(url)

    # Update option
    updated_items = list(items)
    option_media = updated_items[option_index].get("media", {}) or {}
    option_media["external_media"] = build_external_media_dict(external_media)
    updated_items[option_index]["media"] = option_media
    revision.options = rebuild_options(revision.options, updated_items, matrix_key)
    flag_modified(revision, "options")
    session.add(revision)
    session.commit()

    return ExternalMediaResponse(
        type=external_media.type,
        provider=external_media.provider,
        url=external_media.url,
        embed_url=external_media.embed_url,
        thumbnail_url=external_media.thumbnail_url,
    )


@router.delete(
    "/questions/{question_id}/options/{option_id}/external",
    response_model=Message,
    dependencies=[Depends(permission_dependency("update_question"))],
)
async def delete_option_external_media(
    question_id: int,
    option_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Remove external media from a specific option."""
    question = get_question_with_permission(session, question_id, current_user)
    revision = get_revision(session, question)

    # Find the option
    items, option_index, matrix_key = find_option(revision.options, option_id)

    updated_items = list(items)
    option = updated_items[option_index]

    option_media = option.get("media")
    if not option_media or "external_media" not in option_media:
        raise HTTPException(
            status_code=404, detail="No external media found for this option"
        )

    # Update option
    del option_media["external_media"]
    if not option_media:
        del updated_items[option_index]["media"]
    else:
        updated_items[option_index]["media"] = option_media

    revision.options = rebuild_options(revision.options, updated_items, matrix_key)
    flag_modified(revision, "options")
    session.add(revision)
    session.commit()

    return Message(message="Option external media removed successfully")
