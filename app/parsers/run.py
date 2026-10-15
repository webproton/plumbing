"""
Отладка парсера накладной из консоли (из каталога app/):
    python -m parsers.run путь/к/накладной.xlsx
Печатает распознанный JSON.
"""

import json
import sys

from parsers.core.loader import load_rows
from parsers.registry import parse


def main():
    if len(sys.argv) < 2:
        print("Использование: python -m parsers.run файл.xlsx")
        return 1
    rows = load_rows(sys.argv[1])
    print(json.dumps(parse(rows), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
