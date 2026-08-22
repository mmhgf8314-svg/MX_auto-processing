"""Mail triage helpers for the taku_yamashita@mxvideo.jp draft workflow."""

from .triage import (
    Companion,
    Config,
    Message,
    Party,
    Triage,
    classify,
    counterparty_language,
    detect_language,
    load_config,
    strip_quoted,
)

__all__ = [
    "Companion",
    "Config",
    "Message",
    "Party",
    "Triage",
    "classify",
    "counterparty_language",
    "detect_language",
    "load_config",
    "strip_quoted",
]
