"""Utility helpers for working with supported locales."""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("zh-CN", "en-US")

LANGUAGE_LABELS = {
    "zh-CN": "Chinese",
    "en-US": "English",
}


def normalize_locale(locale: str | None) -> str:
    """Return a supported locale, falling back to zh-CN."""
    if not locale:
        return "zh-CN"
    locale = locale.strip()
    if locale in SUPPORTED_LANGUAGES:
        return locale
    # Handle e.g., en, en-US, en_us differences
    lowered = locale.lower()
    if lowered.startswith("en"):
        return "en-US"
    if lowered.startswith("zh"):
        return "zh-CN"
    return "zh-CN"


def get_language_label(locale: str | None) -> str:
    """Return a human-friendly language name for prompts."""
    normalized = normalize_locale(locale)
    return LANGUAGE_LABELS.get(normalized, LANGUAGE_LABELS["zh-CN"])
