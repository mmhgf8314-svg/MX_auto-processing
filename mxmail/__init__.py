"""Mail triage helpers for the taku_yamashita@mxvideo.jp draft workflow."""

from .linkage import (
    CaseKey,
    Gap,
    ThreadRef,
    canonical_key,
    extract_keys,
    find_gaps,
    group_by_key,
    thread_has_matrox,
)
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
    "CaseKey",
    "Companion",
    "Config",
    "Gap",
    "Message",
    "Party",
    "ThreadRef",
    "Triage",
    "canonical_key",
    "classify",
    "counterparty_language",
    "detect_language",
    "extract_keys",
    "find_gaps",
    "group_by_key",
    "load_config",
    "strip_quoted",
    "thread_has_matrox",
]
