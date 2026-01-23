"""File validation and storage utilities for managing uploaded files."""

import io
import os
import uuid
from pathlib import Path

import magic
from fastapi import HTTPException, UploadFile
from PIL import Image

# Configuration
UPLOAD_ROOT = Path("/app/uploads")
LOGO_DIR = UPLOAD_ROOT / "organizations" / "logos"

# Validation configuration
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
MIN_DIMENSION = 50  # pixels
MAX_DIMENSION = 4096  # pixels

# Decompression bomb protection (89 megapixels max)
MAX_IMAGE_PIXELS = 89_478_485


# Validation functions


async def validate_logo_upload(file: UploadFile) -> tuple[bytes, str]:
    """
    Validates logo file upload with comprehensive security checks.

    Args:
        file: The uploaded file from FastAPI

    Returns:
        tuple: (file_content as bytes, file_extension as string)

    Raises:
        HTTPException: If validation fails
    """
    # Read file content
    file_content = await file.read()

    # 1. Check file size
    file_size = len(file_content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    if file_size > MAX_LOGO_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_LOGO_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File size ({size_mb:.2f} MB) exceeds maximum allowed size ({max_mb} MB)",
        )

    # 2. Check file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_extension = get_file_extension(file.filename)
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 3. Verify MIME type (prevent extension spoofing)
    mime_type = magic.from_buffer(file_content, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file content. Expected image file but got: {mime_type}",
        )

    # 4. Validate image dimensions
    validate_image_dimensions(file_content)

    return file_content, file_extension


def get_file_extension(filename: str) -> str:
    """
    Extract and normalize file extension.

    Args:
        filename: The filename

    Returns:
        str: Lowercase file extension including the dot (e.g., ".png")
    """
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_image_dimensions(file_content: bytes) -> None:
    """
    Validate image dimensions using PIL.

    Args:
        file_content: Image file content as bytes
        file_extension: File extension for error messages

    Raises:
        HTTPException: If dimensions are invalid or image cannot be opened
    """
    # Set decompression bomb protection
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

    # Check minimum dimensions
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions ({width}x{height}) too small. Minimum: {MIN_DIMENSION}x{MIN_DIMENSION}",
        )

    # Check maximum dimensions
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions ({width}x{height}) too large. Maximum: {MAX_DIMENSION}x{MAX_DIMENSION}",
        )


# Storage functions


def init_upload_directories() -> None:
    """
    Initialize upload directories with proper permissions.
    Creates the directory structure if it doesn't exist.

    """
    LOGO_DIR.mkdir(parents=True, exist_ok=True, mode=0o755)


def generate_logo_filename(organization_id: int, file_extension: str) -> str:
    """
    Generate a unique filename for logo upload.

    Args:
        organization_id: The organization's ID
        file_extension: File extension including the dot (e.g., ".png")

    Returns:
        str: Unique filename in format: org_<id>_<uuid>.<ext>

    Example:
        generate_logo_filename(42, ".png")
        => "org_42_f47ac10b-58cc-4372-a567-0e02b2c3d479.png"
    """
    unique_id = uuid.uuid4()
    return f"org_{organization_id}_{unique_id}{file_extension}"


def save_logo_file(
    organization_id: int, file_content: bytes, file_extension: str
) -> str:
    """
    Save logo file to disk atomically.

    Args:
        organization_id: The organization's ID
        file_content: File content as bytes
        file_extension: File extension including the dot (e.g., ".png")

    Returns:
        str: Relative path for database storage (e.g., "/uploads/organizations/logos/org_42_xxx.png")

    Raises:
        OSError: If file cannot be written
    """
    # Ensure directories exist
    init_upload_directories()

    # Generate unique filename
    filename = generate_logo_filename(organization_id, file_extension)
    file_path = LOGO_DIR / filename

    # Write file atomically (write to temp, then rename)
    temp_path = file_path.with_suffix(f"{file_extension}.tmp")
    try:
        # Write to temporary file
        temp_path.write_bytes(file_content)
        # Set file permissions (readable by all, writable only by owner)
        os.chmod(temp_path, 0o644)
        # Atomic rename
        temp_path.rename(file_path)
    except Exception:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise

    # Return relative path for database storage
    return f"/uploads/organizations/logos/{filename}"


def delete_logo_file(logo_path: str | None) -> None:
    """
    Delete logo file from disk with security checks.

    Args:
        logo_path: Relative path stored in database (e.g., "/uploads/organizations/logos/org_42_xxx.png")
                   Can be None if no logo exists.

    Note:
        Silently handles missing files (already deleted or never existed).
        Raises exception only for security violations (path traversal attempts).
    """
    if not logo_path:
        return

    # Security check: ensure path is within allowed directory
    if not logo_path.startswith("/uploads/organizations/logos/"):
        raise ValueError(f"Invalid logo path: {logo_path}")

    # Security check: prevent path traversal
    if ".." in logo_path or logo_path.startswith(".."):
        raise ValueError(f"Path traversal attempt detected: {logo_path}")

    # Construct absolute path
    # Remove leading slash from logo_path since UPLOAD_ROOT already has the base
    relative_path = logo_path.removeprefix("/uploads/")
    file_path = UPLOAD_ROOT / relative_path

    # Security check: verify resolved path is within upload directory
    try:
        resolved_path = file_path.resolve()
        if not str(resolved_path).startswith(str(UPLOAD_ROOT.resolve())):
            raise ValueError(f"Path escapes upload directory: {logo_path}")
    except Exception:
        # If path resolution fails, don't delete
        return

    # Delete file if it exists
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            # Silently ignore deletion errors (file in use, permissions, etc.)
            # The file will be orphaned but not cause issues
            pass
