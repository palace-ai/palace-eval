"""Multimodal content utilities for attachments."""

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

MIME_MAP: dict[str, str] = {
    # Image
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
    # Audio
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".flac": "audio/flac",
    # Video
    ".mp4": "video/mp4", ".webm": "video/webm", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
    # Document
    ".pdf": "application/pdf",
}


def mime_from_extension(ext: str) -> str:
    """Return MIME type for a file extension. Falls back to application/octet-stream."""
    return MIME_MAP.get(ext.lower(), "application/octet-stream")


def detect_modalities(tasks: list[dict]) -> list[str]:
    """Detect modalities from task attachments. Always includes 'text'."""
    modalities = {"text"}
    for task in tasks:
        atts = task.get("attachments", [])
        if not atts and (att := task.get("attachment")):
            atts = [att]
        for attachment in atts:
            ext = Path(attachment).suffix.lower()
            for modality, extensions in MODALITY_EXTENSIONS.items():
                if ext in extensions:
                    modalities.add(modality)
    return sorted(modalities)

# Max dimension for images (OpenAI recommends 2048 max, we use 1024 for safety)
MAX_IMAGE_DIMENSION = 1024


def is_image_attachment(path: str) -> bool:
    """Check if attachment is an image by extension.

    Deprecated: Pipeline now uses mime_from_extension() for MIME-based classification.
    Kept for backward compatibility with external consumers.
    """
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def build_multimodal_content(
    prompt: str, attachments: "list[Any] | None" = None
) -> str | list[dict[str, Any]]:
    """Build message content for OpenAI API, with optional typed attachments.

    Args:
        prompt: The text prompt
        attachments: List of Attachment objects (with path, mime_type, filename)

    Returns:
        String if no attachments, list of content parts if attachments provided
    """
    if not attachments:
        return prompt

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for att in attachments:
        part = _build_content_part(att)
        if part:
            content.append(part)
    # If no parts were buildable, return plain text
    if len(content) == 1:
        return prompt
    return content


def _build_content_part(att: Any) -> dict[str, Any] | None:
    """Map an Attachment to a provider-agnostic content part by MIME prefix."""
    if att.mime_type.startswith("image/"):
        image_data, mime_type = _load_and_resize_image(att.path)
        return {"type": "image", "media_type": mime_type, "data": image_data}
    elif att.mime_type.startswith("audio/"):
        return _build_audio_part(att)
    # video, pdf, etc: unsupported
    return None


def _build_audio_part(att: Any) -> dict[str, Any]:
    """Build a provider-agnostic audio content part from an Attachment."""
    raw = Path(att.path).read_bytes()
    data = base64.b64encode(raw).decode("utf-8")
    ext = Path(att.path).suffix.lstrip(".").lower()
    fmt = ext if ext in ("wav", "mp3", "flac", "ogg") else "wav"
    return {"type": "audio", "format": fmt, "data": data}


def _detect_mime_from_format(img_format: str | None) -> str:
    """Map PIL image format to MIME type based on actual content, not extension."""
    FORMAT_TO_MIME = {
        "JPEG": "image/jpeg", "PNG": "image/png",
        "GIF": "image/gif", "WEBP": "image/webp",
    }
    return FORMAT_TO_MIME.get(img_format or "", "image/png")


def _load_and_resize_image(image_path: str) -> tuple[str, str]:
    """Load image, resize if too large, return base64 and MIME type.

    If the image doesn't need resizing or mode conversion, sends the original
    file bytes to avoid re-encoding artifacts and compatibility issues.
    Falls back to high-quality JPEG for large images to avoid payload size issues.

    MIME type is detected from actual image content (not file extension) to
    prevent mismatches rejected by Anthropic's API.
    """
    MAX_BASE64_BYTES = 1_000_000  # ~1MB base64 threshold

    with Image.open(image_path) as img:
        actual_format = img.format  # Detected from file content (e.g. "JPEG", "PNG")
        actual_mime = _detect_mime_from_format(actual_format)
        needs_resize = max(img.size) > MAX_IMAGE_DIMENSION
        needs_convert = img.mode in ("RGBA", "P")

        if not needs_resize and not needs_convert and actual_format:
            # Send original file bytes — avoids re-encoding issues
            raw = Path(image_path).read_bytes()
            b64 = base64.b64encode(raw).decode("utf-8")
            if len(b64) <= MAX_BASE64_BYTES:
                return b64, actual_mime

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
