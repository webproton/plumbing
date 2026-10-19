"""
Эталонные кейсы парсеров накладных (parser_cases/*.json): обезличенные копии реальных макетов.

Тест падает при любом изменении результата разбора. Если изменение — улучшение, обновить эталон:
    cd app && python -m parsers.regress record apps/warehouse/tests/parser_cases
и проверить diff JSON глазами перед коммитом.
"""

import json
from pathlib import Path

import pytest

from parsers.regress import case_rows, run_rows

CASES = sorted((Path(__file__).parent / "parser_cases").glob("*.json"))


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_parser_case(path):
    case = json.loads(path.read_text())
    assert json.loads(json.dumps(run_rows(case_rows(case)), default=str)) == case["expected"]
