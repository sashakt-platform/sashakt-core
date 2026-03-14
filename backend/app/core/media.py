"""Media validation and processing utilities for question media."""

import io
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import magic
from fastapi import HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.timezone import get_timezone_aware_now

# Validation configuration
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
MIN_DIMENSION = 50  # pixels
MAX_DIMENSION = 4096  # pixels
MAX_IMAGE_PIXELS = 89_478_485  # Decompression bomb protection


# Pydantic models for media data


class ImageMedia(BaseModel):
    """Image media stored in GCS."""

    gcs_path: str = Field(..., description="Path in GCS bucket")
    alt_text: str | None = Field(default=None, description="Alternative text for image")
    content_type: str = Field(..., description="MIME type of the image")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(
        default_factory=get_timezone_aware_now, description="Upload timestamp"
    )


class ExternalMedia(BaseModel):
    """External media (YouTube, Vimeo, etc.)."""

    type: str = Field(..., description="Media type: video or audio")
    provider: str = Field(
        ..., description="Provider: youtube, vimeo, soundcloud, spotify, or other"
    )
    url: str = Field(..., description="Original URL")
    embed_url: str | None = Field(default=None, description="Embeddable URL")
    thumbnail_url: str | None = Field(default=None, description="Thumbnail URL")


class QuestionMedia(BaseModel):
    """Media attached to a question."""

    image: ImageMedia | None = Field(default=None, description="Uploaded image")
    external_media: ExternalMedia | None = Field(
        default=None, description="External video/audio"
    )


class OptionMedia(BaseModel):
    """Media attached to a question option."""

    image: ImageMedia | None = Field(default=None, description="Uploaded image")
    external_media: ExternalMedia | None = Field(
        default=None, description="External video/audio"
    )


# Validation functions


async def validate_image_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """
    Validate image file upload with security checks.

    Args:
        file: The uploaded file from FastAPI

    Returns:
        tuple: (file_content as bytes, file_extension as string, mime_type as string)

    Raises:
        HTTPException: If validation fails
    """
    max_size_bytes = settings.MAX_QUESTION_IMAGE_SIZE_MB * 1024 * 1024

    # Read file content with bounded memory consumption
    file_content = await file.read(max_size_bytes + 1)

    # 1. Check file size
    file_size = len(file_content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File size ({size_mb:.2f} MB) exceeds maximum "
            f"({settings.MAX_QUESTION_IMAGE_SIZE_MB} MB)",
        )

    # 2. Check file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_extension = _get_file_extension(file.filename)
    if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    # 3. Verify MIME type (prevent extension spoofing)
    mime_type = magic.from_buffer(file_content, mime=True)
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file content. Expected image but got: {mime_type}",
        )

    # 4. Validate image dimensions
    _validate_image_dimensions(file_content)

    return file_content, file_extension, mime_type


def _get_file_extension(filename: str) -> str:
    """Extract and normalize file extension."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _validate_image_dimensions(file_content: bytes) -> None:
    """Validate image dimensions using PIL."""
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        image = Image.open(io.BytesIO(file_content))
        width, height = image.size
    except Image.DecompressionBombError:
        raise HTTPException(
            status_code=400,
            detail="Image too large: potential decompression bomb detected",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file: cannot read image data ({str(e)})",
        )

    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions ({width}x{height}) too small. "
            f"Minimum: {MIN_DIMENSION}x{MIN_DIMENSION}",
        )

    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions ({width}x{height}) too large. "
            f"Maximum: {MAX_DIMENSION}x{MAX_DIMENSION}",
        )


# External media URL parsing


def validate_external_media_url(url: str) -> ExternalMedia:
    """
    Validate and parse external media URL.

    Supports YouTube, Vimeo, SoundCloud, Spotify, and generic URLs.

    Args:
        url: The external media URL

    Returns:
        ExternalMedia object with parsed information

    Raises:
        HTTPException: If URL is invalid
    """
    url = url.strip()

    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, detail="Invalid URL. Must start with http:// or https://"
        )

    # YouTube
    youtube_id = _extract_youtube_id(url)
    if youtube_id:
        return ExternalMedia(
            type="video",
            provider="youtube",
            url=url,
            embed_url=f"https://www.youtube.com/embed/{youtube_id}",
            thumbnail_url=f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg",
        )

    # Vimeo
    vimeo_id = _extract_vimeo_id(url)
    if vimeo_id:
        return ExternalMedia(
            type="video",
            provider="vimeo",
            url=url,
            embed_url=f"https://player.vimeo.com/video/{vimeo_id}",
            thumbnail_url=None,  # Vimeo requires API call for thumbnail
        )

    # SoundCloud
    if _is_soundcloud_url(url):
        return ExternalMedia(
            type="audio",
            provider="soundcloud",
            url=url,
            embed_url=None,  # SoundCloud embeds require oEmbed API
            thumbnail_url=None,
        )

    # Spotify
    spotify_info = _extract_spotify_info(url)
    if spotify_info:
        return ExternalMedia(
            type="audio",
            provider="spotify",
            url=url,
            embed_url=spotify_info["embed_url"],
            thumbnail_url=None,
        )

    # Generic/unknown - still allow it
    return ExternalMedia(
        type="video",  # Default to video for unknown
        provider="other",
        url=url,
        embed_url=None,
        thumbnail_url=None,
    )


def _extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _extract_vimeo_id(url: str) -> str | None:
    """Extract Vimeo video ID from URL."""
    match = re.search(r"vimeo\.com/(\d+)", url)
    if match:
        return match.group(1)
    return None


def _extract_spotify_info(url: str) -> dict[str, str] | None:
    """Extract Spotify track/album/playlist info from URL."""
    match = re.search(r"spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)", url)
    if match:
        content_type = match.group(1)
        content_id = match.group(2)
        return {
            "embed_url": f"https://open.spotify.com/embed/{content_type}/{content_id}"
        }
    return None


def _is_soundcloud_url(url: str) -> bool:
    """Check if URL is a valid SoundCloud URL by verifying the host."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        # Must be exactly soundcloud.com or a subdomain like m.soundcloud.com
        return host == "soundcloud.com" or host.endswith(".soundcloud.com")
    except Exception:
        return False


# Helper functions for building media JSON


def build_image_media_dict(
    gcs_path: str, content_type: str, size_bytes: int, alt_text: str | None = None
) -> dict[str, Any]:
    """Build image media dictionary for JSON storage."""
    return ImageMedia(
        gcs_path=gcs_path,
        alt_text=alt_text,
        content_type=content_type,
        size_bytes=size_bytes,
    ).model_dump(mode="json")


def build_external_media_dict(external_media: ExternalMedia) -> dict[str, Any]:
    """Build external media dictionary for JSON storage."""
    return external_media.model_dump(mode="json")
