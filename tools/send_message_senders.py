"""Standalone per-platform senders and error helpers for send_message."""

from pm import install_hint
import asyncio
import contextlib
import logging
import os
import re
import time

from agent.redact import redact_sensitive_text

logger = logging.getLogger("tools.send_message_tool")

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
_AUDIO_EXTS = {".ogg", ".opus", ".mp3", ".m2a", ".wav", ".m4a", ".flac"}
_VOICE_EXTS = {".ogg", ".opus"}
# Captionable on the media bubble; voice/audio notes excluded (a caption there reads as a separate label).
_CAPTIONABLE_EXTS = _IMAGE_EXTS | _VIDEO_EXTS | {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".zip"}
# Shared native caption ceiling (characters).
_DEFAULT_CAPTION_LIMIT = 4096


def _media_caption_split(text, media_files, *, max_caption_len):
    """Single chokepoint deciding whether text rides on the media bubble as its caption:
    ``(caption, "")`` only for exactly one captionable file (not a voice/audio note) whose
    text fits ``max_caption_len``, else ``(None, text)`` — multi-file caption→file association
    is ambiguous. Length is measured in codepoints."""
    stripped = (text or "").strip()
    media = media_files or []
    if (not stripped or len(media) != 1 or len(stripped) > max_caption_len or media[0][1]
            or os.path.splitext(media[0][0])[1].lower() not in _CAPTIONABLE_EXTS):
        return None, text
    return stripped, ""


_URL_SECRET_QUERY_RE = re.compile(
    r"([?&](?:access_token|api[_-]?key|auth[_-]?token|token|signature|sig)=)([^&#\s]+)", re.IGNORECASE)
_GENERIC_SECRET_ASSIGN_RE = re.compile(
    r"\b(access_token|api[_-]?key|auth[_-]?token|signature|sig)\s*=\s*([^\s,;]+)", re.IGNORECASE)


def _sanitize_error_text(text) -> str:
    """Redact secrets from error text before surfacing it to users/models."""
    redacted = _URL_SECRET_QUERY_RE.sub(lambda m: f"{m.group(1)}***", redact_sensitive_text(text))
    return _GENERIC_SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)}=***", redacted)


def _error(message: str) -> dict:
    """Build a standardized error payload with redacted content."""
    return {"error": _sanitize_error_text(message)}


def _success(platform: str, chat_id, warnings=None, **fields) -> dict:
    """Standard success payload; ``warnings`` is only included when non-empty."""
    return {"success": True, "platform": platform, "chat_id": chat_id, **fields,
            **({"warnings": warnings} if warnings else {})}


_NO_DELIVERABLE = "No deliverable text or media remained after processing MEDIA tags"


def _adapter_media_method(ext, voice, force_document=False):
    """``(adapter method, kind)``: document when forced, else image / video / voice by
    extension (``voice`` already folds in the caller's audio rule)."""
    if force_document:
        return "send_document", "document"
    if ext in _IMAGE_EXTS:
        return "send_image_file", "image"
    if ext in _VIDEO_EXTS:
        return "send_video", "video"
    return ("send_voice", "audio") if voice else ("send_document", "document")


def _live_adapter(platform, *, lookup_failed_warning=None):
    """``(runner, adapter)`` for the in-process gateway; ``(None, None)`` standalone (cron);
    ``(runner, None)`` when the lookup fails — logged when a warning is given, never silently
    swallowed (a silent fall-through could recreate a reconnect storm).

    Multiplex: the adapter is the ACTIVE PROFILE's (``_profile_adapters[profile]``), never a bare
    ``runner.adapters`` hit — that map holds the default profile's bots, so a secondary profile's turn
    would post/react with the default bot's identity. A profile with no adapter for the platform
    yields ``None`` (fail closed → the caller's scoped standalone sender or an error), never the
    default bot. Same resolver shape as ``hermes_cli/platform_actions.py::_resolve_adapter``."""
    try:
        from gateway.run import _gateway_runner_ref
        runner = _gateway_runner_ref()
    except Exception:
        runner = None
    if runner is None:
        return None, None
    try:
        resolve = getattr(runner, "_authorization_adapter", None)
        if not callable(resolve):  # bare runner stubs without the authz mixin
            return runner, runner.adapters.get(platform)
        from hermes_cli.profiles import get_active_profile_name
        return runner, resolve(platform, get_active_profile_name())
    except Exception:
        if lookup_failed_warning:
            logger.warning(lookup_failed_warning, exc_info=True)
        return runner, None


def _plugin_standalone_sender(platform_name, *, label=None, discover=True):
    """``(standalone_sender_fn, None)`` for a registered plugin or ``(None, error_dict)``;
    ``discover`` runs the idempotent plugin scan first."""
    from gateway.platform_registry import platform_registry
    if discover:
        from hermes_cli.plugins import discover_plugins
        discover_plugins()
    entry = platform_registry.get(platform_name)
    if entry is None or entry.standalone_sender_fn is None:
        return None, {"error": f"{label or platform_name} plugin not registered or missing standalone_sender_fn"}
    return entry.standalone_sender_fn, None


async def _registry_standalone_send(platform_name, pconfig, chat_id, message, thread_id=None):
    """One-shot text send through a plugin's ``standalone_sender_fn``."""
    sender, err = _plugin_standalone_sender(platform_name)
    return err or await sender(pconfig, chat_id, message, thread_id=thread_id)


# "ephemeral connect (may re-init E2EE per send, see #46310)",
