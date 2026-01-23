"""Test utilities for file operations."""

import io

from PIL import Image


def create_test_image(
    width: int = 100, height: int = 100, format: str = "PNG", color: str = "red"
) -> io.BytesIO:
    """
    Create a test image in memory.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        format: Image format (PNG, JPEG, etc.)
        color: Image color

    Returns:
        BytesIO: Image data as bytes in memory
    """
    img = Image.new("RGB", (width, height), color=color)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    img_bytes.seek(0)
    img_bytes.name = f"test_image.{format.lower()}"
    return img_bytes


def create_large_test_image(size_mb: float = 3) -> io.BytesIO:
    """
    Create a large test image for testing file size limits.

    Args:
        size_mb: Approximate size in megabytes

    Returns:
        BytesIO: Large image data as bytes in memory
    """
    # Calculate dimensions to achieve approximate size
    # JPEG with default quality ~= 30KB per 1000x1000 pixels
    dimension = int((size_mb * 1024 * 1024 / 30000) ** 0.5 * 1000)
    return create_test_image(width=dimension, height=dimension, format="JPEG")


def create_text_file() -> io.BytesIO:
    """
    Create a text file for testing invalid file type validation.

    Returns:
        BytesIO: Text file data as bytes in memory
    """
    text_content = "This is not an image file"
    text_bytes = io.BytesIO(text_content.encode("utf-8"))
    text_bytes.seek(0)
    text_bytes.name = "test.txt"
    return text_bytes
