"""The journal's user-facing translations."""

from functools import cache
import json
from pathlib import Path


_language = "bg"


def set_language(language: str) -> None:
    global _language
    _language = language


def language() -> str:
    return _language


@cache
def english_catalog() -> dict[str, str]:
    return json.loads(Path(__file__).with_name("en.json").read_text(encoding="utf-8"))


def localized(source: str, *, context: str = "") -> str:
    if _language != "en":
        return source
    catalog = english_catalog()
    return catalog.get(f"{context}|{source}", catalog.get(source, source))
