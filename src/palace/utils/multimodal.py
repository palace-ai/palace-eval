"""Multimodal content utilities for image attachments."""

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Max dimension for images (OpenAI recommends 2048 max, we use 1024 for safety)
MAX_IMAGE_DIMENSION = 1024


def is_image_attachment(path: str) -> bool:
    """Check if attachment is an image by extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def build_multimodal_content(
    prompt: str, image_path: str | None = None
) -> str | list[dict[str, Any]]:
    """Build message content for OpenAI API, with optional image.

    Args:
        prompt: The text prompt
        image_path: Path to image file, or None for text-only

    Returns:
        String if no image, list of content parts if image provided
    """
    if image_path is None:
        return prompt

    # Load, resize if needed, and encode image
    image_data, mime_type = _load_and_resize_image(image_path)

    return [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
        },
    ]


def _load_and_resize_image(image_path: str) -> tuple[str, str]:
    """Load image, resize if too large, return base64 and MIME type."""
    with Image.open(image_path) as img:
        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if larger than max dimension
        if max(img.size) > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

        # Save to bytes as JPEG (good compression)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        image_bytes = buffer.getvalue()

    image_data = base64.b64encode(image_bytes).decode("utf-8")
    return image_data, "image/jpeg"
