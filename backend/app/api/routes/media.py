"""Media upload endpoints for questions."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.core.media import (
    build_external_media_dict,
    build_image_media_dict,
    validate_external_media_url,
    validate_image_upload,
)
from app.core.provider_config import provider_config_service
from app.models import Message
from app.models.provider import OrganizationProvider, Provider, ProviderType
from app.models.question import (
    MatrixMatchOptions,
    Option,
    Question,
    QuestionRevision,
)
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

    return question


def get_revision(session: SessionDep, question: Question) -> QuestionRevision:
    """Get the current revision of a question."""
    if not question.last_revision_id:
        raise HTTPException(status_code=404, detail="Question has no revision")

    revision = session.get(QuestionRevision, question.last_revision_id)
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    return revision


def get_options_list(
    options: MatrixMatchOptions | list[Option] | None,
) -> list[Option]:
    """Get options as a list, raising 404 if not available or not a list type."""
    if not options:
        raise HTTPException(status_code=404, detail="Question has no options")
    if isinstance(options, dict):
        raise HTTPException(
            status_code=400,
            detail="Media operations are not supported for matrix match questions",
        )
    return options


def find_option_index(options: list[Option], option_id: int) -> int:
    """Find the index of an option by ID."""
    for i, opt in enumerate(options):
        if opt.get("id") == option_id:
            return i

    raise HTTPException(status_code=404, detail="Option not found")


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

    # Update revision media
    media = dict(revision.media) if revision.media else {}
    media["image"] = build_image_media_dict(
        gcs_path=gcs_path,
        content_type=content_type,
        size_bytes=len(file_content),
        alt_text=alt_text,
    )
    revision.media = media
    session.add(revision)
    session.commit()

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

    # Delete from GCS
    gcs_path = revision.media["image"].get("gcs_path")
    if gcs_path:
        gcs_service = get_gcs_service(session, question.organization_id)
        gcs_service.delete(gcs_path)

    # Update revision
    media = dict(revision.media)
    del media["image"]
    revision.media = media if media else None
    session.add(revision)
    session.commit()

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
    options = get_options_list(revision.options)
    option_index = find_option_index(options, option_id)

    # Validate image
    file_content, file_extension, content_type = await validate_image_upload(file)

    # Get GCS service and upload
    gcs_service = get_gcs_service(session, question.organization_id)
    gcs_path = gcs_service.generate_media_path(question_id, file_extension, option_id)
    gcs_service.upload(file_content, gcs_path, content_type)

    # Update option with media
    options = list(options)
    option_media = {
        "image": build_image_media_dict(
            gcs_path=gcs_path,
            content_type=content_type,
            size_bytes=len(file_content),
            alt_text=alt_text,
        )
    }
    options[option_index]["media"] = option_media
    revision.options = options
    session.add(revision)
    session.commit()

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
    options = get_options_list(revision.options)
    option_index = find_option_index(options, option_id)

    options_copy = list(options)
    option = options_copy[option_index]

    option_media = option.get("media")
    if not option_media or "image" not in option_media:
        raise HTTPException(status_code=404, detail="No image found for this option")

    # Delete from GCS
    gcs_path = option_media["image"].get("gcs_path")
    if gcs_path:
        gcs_service = get_gcs_service(session, question.organization_id)
        gcs_service.delete(gcs_path)

    # Update option
    del option_media["image"]
    if not option_media:
        del options_copy[option_index]["media"]
    else:
        options_copy[option_index]["media"] = option_media

    revision.options = options_copy
    session.add(revision)
    session.commit()

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
    options = get_options_list(revision.options)
    option_index = find_option_index(options, option_id)

    # Validate and parse URL
    external_media = validate_external_media_url(url)

    # Update option
    options_copy = list(options)
    option_media = options_copy[option_index].get("media", {}) or {}
    option_media["external_media"] = build_external_media_dict(external_media)
    options_copy[option_index]["media"] = option_media
    revision.options = options_copy
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
    options = get_options_list(revision.options)
    option_index = find_option_index(options, option_id)

    options_copy = list(options)
    option = options_copy[option_index]

    option_media = option.get("media")
    if not option_media or "external_media" not in option_media:
        raise HTTPException(
            status_code=404, detail="No external media found for this option"
        )

    # Update option
    del option_media["external_media"]
    if not option_media:
        del options_copy[option_index]["media"]
    else:
        options_copy[option_index]["media"] = option_media

    revision.options = options_copy
    session.add(revision)
    session.commit()

    return Message(message="Option external media removed successfully")
