"""Multimodal content utilities for image attachments."""

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

MODALITY_EXTENSIONS: dict[str, set[str]] = {
    "image": IMAGE_EXTENSIONS,
    "video": {".mp4", ".webm", ".avi", ".mov"},
    "audio": {".mp3", ".wav", ".ogg", ".flac"},
}


def detect_modalities(tasks: list[dict]) -> list[str]:
    """Detect modalities from task attachments. Always includes 'text'."""
    modalities = {"text"}
    for task in tasks:
        if attachment := task.get("attachment"):
            ext = Path(attachment).suffix.lower()
            for modality, extensions in MODALITY_EXTENSIONS.items():
                if ext in extensions:
                    modalities.add(modality)
    return sorted(modalities)

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
    """Load image, resize if too large, return base64 and MIME type.

    If the image doesn't need resizing or mode conversion, sends the original
    file bytes to avoid re-encoding artifacts and compatibility issues.
    Falls back to high-quality JPEG for large images to avoid payload size issues.
    """
    MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".gif": "image/gif", ".webp": "image/webp"}
    MAX_BASE64_BYTES = 1_000_000  # ~1MB base64 threshold

    ext = Path(image_path).suffix.lower()

    with Image.open(image_path) as img:
        needs_resize = max(img.size) > MAX_IMAGE_DIMENSION
        needs_convert = img.mode in ("RGBA", "P")

        if not needs_resize and not needs_convert and ext in MIME_TYPES:
            # Send original file bytes — avoids re-encoding issues
            raw = Path(image_path).read_bytes()
            b64 = base64.b64encode(raw).decode("utf-8")
            if len(b64) <= MAX_BASE64_BYTES:
                return b64, MIME_TYPES[ext]

        if needs_convert:
            img = img.convert("RGB")
        if needs_resize:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

        # Try PNG first for lossless fidelity
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        if len(png_bytes) <= MAX_BASE64_BYTES:
            return base64.b64encode(png_bytes).decode("utf-8"), "image/png"

        # Fall back to high-quality JPEG for large images
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
