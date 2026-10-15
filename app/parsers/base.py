# parsers/base.py
from abc import ABC, abstractmethod
from typing import Any

from parsers.context import ParseContext
from parsers.core.numbers import extract_numbers
from parsers.core.sku import extract_sku_from_row
from parsers.core.text_utils import row_text
from parsers.utils import normalize_output


class BaseInvoiceParser(ABC):
    """
    Базовый класс для всех invoice parser'ов.

    Pipeline:
        rows
        -> meta
        -> items
        -> totals
        -> normalize_output
    """

    supplier_code: str = "unknown"

    # =========================
    # MAIN PIPELINE
    # =========================
    def parse(
        self,
        rows: list[tuple],
        context: ParseContext,
    ) -> dict[str, Any]:

        meta = self.extract_meta(rows, context)
        meta = self.enrich_meta(rows, meta, context)

        items = self.extract_items(rows, context)
        for item in items:
            # некоторые парсеры кладут штрихкод под другим ключом; очистку делает normalizer
            if isinstance(item, dict) and not item.get("barcode"):
                item["barcode"] = item.get("штрихкод") or item.get("ean") or ""

        raw_result = {
            "supplier": self.supplier_code,
            "meta": meta,
            "items": items,
            "totals": self.extract_totals(rows, context),
            "footer": self.extract_footer(rows, context),
            "warnings": self.extract_warnings(rows, context),
            "signatures": self.extract_signatures(rows, context),
        }

        result = normalize_output(raw_result)

        return result

    # =========================
    # PIPELINE HOOKS
    # =========================
    def enrich_meta(
        self,
        rows,
        data: dict[str, Any],
        context: ParseContext,
    ) -> dict[str, Any]:
        """
        post-processing layer

        Используется для:
        - cleanup
        - enrichment
        - fallback logic
        """

        return data

    # =========================
    # REQUIRED CORE METHODS
    # =========================
    @abstractmethod
    def extract_meta(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:
        """
        Извлечение meta/header информации
        """
        pass

    @abstractmethod
    def extract_items(
        self,
        rows,
        context: ParseContext,
    ) -> list[dict[str, Any]]:
        """
        Извлечение товарных позиций
        """
        pass

    @abstractmethod
    def extract_header(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:
        """
        Разделение:
        - supplier
        - buyer
        - contacts
        - phones
        - emails
        """
        pass

    @abstractmethod
    def detect_context(self, text: str) -> str:
        """
        supplier / buyer / delivery / unknown
        """
        pass

    # =========================
    # CONTACT SYSTEM
    # =========================
    def extract_contact_and_phones(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:

        return {
            "buyer_phones": [],
            "supplier_phones": [],
            "contact_person": None,
        }

    # =========================
    # OPTIONAL LAYERS
    # =========================
    def extract_totals(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:

        return {
            "total": None,
            "vat": None,
            "weight": None,
            "volume": None,
            "summary": None,
        }

    def extract_footer(
        self,
        rows,
        context: ParseContext,
    ) -> list[str]:

        return []

    def extract_warnings(
        self,
        rows,
        context: ParseContext,
    ) -> list[str]:

        return []

    def extract_signatures(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:

        return {
            "executor": None,
            "receiver": None,
        }

    # =========================
    # OPTIONAL EXTENSIONS
    # =========================
    def detect_currency(
        self,
        rows,
        context: ParseContext,
    ) -> str | None:
        """
        Валюта документа
        """

        return None

    def detect_language(
        self,
        rows,
        context: ParseContext,
    ) -> str | None:
        """
        Язык документа
        """

        return None

    def extract_tax_info(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:
        """
        Налоги / НДС
        """

        return {}

    def extract_delivery_info(
        self,
        rows,
        context: ParseContext,
    ) -> dict[str, Any]:
        """
        Логистика / доставка
        """

        return {}

    # =========================
    # FALLBACK ITEM ENGINE
    # =========================
    def extract_items_fallback(self, rows, context):
        if getattr(context, "use_table_engine", False):
            return []
        return self._generic_fallback(rows, context)

    def _generic_fallback(
        self,
        rows,
        context: ParseContext,
    ):

        import re

        items = []

        position = 0
        started = False

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            # =========================
            # TABLE START
            # =========================
            if not started:
                if any(
                    k in lower
                    for k in [
                        "товар",
                        "наименование",
                        "назва",
                    ]
                ):
                    started = True

                continue

            # =========================
            # TABLE END
            # =========================
            if any(
                k in lower
                for k in [
                    "итого",
                    "разом",
                    "всього",
                ]
            ):
                break

            nums = extract_numbers(row)

            if len(nums) < 2:
                continue

            price = nums[-2]
            total = nums[-1]

            if price <= 0 or total <= 0:
                continue

            position += 1

            sku = extract_sku_from_row(row)

            # fallback SKU
            if not sku:
                m = re.search(
                    r"№\s*([A-Za-z0-9\-]{2,})",
                    text,
                    re.IGNORECASE,
                )

                if m:
                    sku = m.group(1)

            name = text

            if sku:
                name = re.sub(
                    rf"№\s*{re.escape(sku)}",
                    "",
                    name,
                    flags=re.IGNORECASE,
                )

            name = re.sub(r"^\d+\s*", "", name)
            name = re.sub(r"\s+", " ", name).strip()

            items.append(
                {
                    "position": position,
                    "sku": sku or "",
                    "name": name,
                    "qty": None,
                    "unit": None,
                    "price": price,
                    "total": total,
                }
            )

        return items
