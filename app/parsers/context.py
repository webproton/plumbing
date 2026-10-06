# parsers/context.py
from dataclasses import dataclass, field
from typing import Any

"""Это:

уже production-ready
уже расширяемо
уже подходит под pipeline
уже подходит под supplier overrides
уже подходит под scoring

Но:

без мусорных future fields
без god object
без хранения всего parser state подряд"""


@dataclass
class ParseContext:
    """
    Runtime context parser pipeline.

    Хранит:
    - состояние парсинга
    - результаты detection
    - confidence/scoring
    - runtime warnings
    - debug state

    НЕ хранит:
    - raw rows
    - final schema
    - parsed items
    """

    # =========================
    # DOCUMENT DETECTION
    # =========================
    supplier_code: str = "default"
    document_type: str | None = None
    language: str | None = None
    
    currency: str | None = None

    # =========================
    # TABLE STRUCTURE
    # =========================
    header_index: int | None = None

    column_map: dict[str, int] = field(default_factory=dict)
    
    
    table_started: bool = False
    table_ended: bool = False
    
    # =========================
    # PARSING FLAGS
    # =========================
    used_fallback_items: bool = False
    used_fallback_totals: bool = False

    # =========================
    # PARSING STATE
    # =========================
    confidence: float = 0.0

    warnings: list[str] = field(default_factory=list)

    # =========================
    # DEBUG / INTERNAL STATE
    # =========================
    debug: dict[str, Any] = field(default_factory=dict)

    # =========================
    # HELPERS
    # =========================
    def add_warning(self, code: str):
        if code not in self.warnings:
            self.warnings.append(code)

    def set_debug(self, key: str, value: Any):
        self.debug[key] = value