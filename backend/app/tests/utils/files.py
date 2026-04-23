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


def create_test_pdf() -> io.BytesIO:
    """
    Create a minimal but valid PDF for upload tests. libmagic detects this as
    application/pdf via the `%PDF-` header + trailer.
    """
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n160\n%%EOF\n"
    )
    buf = io.BytesIO(pdf_content)
    buf.seek(0)
    buf.name = "test_guide.pdf"
    return buf


def create_large_test_pdf(size_mb: float = 11) -> io.BytesIO:
    """Create an oversize PDF (valid header + padding) to trigger size limit."""
    header = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
    )
    trailer = (
        b"\nxref\n0 3\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"trailer<</Size 3/Root 1 0 R>>\nstartxref\n100\n%%EOF\n"
    )
    target = int(size_mb * 1024 * 1024)
    padding = b"0" * max(0, target - len(header) - len(trailer))
    buf = io.BytesIO(header + padding + trailer)
    buf.seek(0)
    buf.name = "large.pdf"
    return buf
