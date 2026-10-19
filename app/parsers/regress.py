"""
Эталон разбора накладных: защита от регрессий при доработке парсеров.

Из каталога app/:
    python -m parsers.regress snapshot ПАПКА   # запомнить, как файлы разбираются сейчас
    python -m parsers.regress compare ПАПКА    # сравнить текущий разбор с запомненным
    python -m parsers.regress record ПАПКА     # обновить "expected" в JSON-кейсах тестов (после проверки глазами!)

Снимки лежат в ПАПКА/.parser-snapshots/. Сравнение показывает по каждому файлу:
  OK — разбор не изменился; CHANGED — изменились строки (нужно посмотреть глазами: улучшение или нет);
  LOST — строк стало меньше или файл перестал разбираться (регрессия); FIXED — раньше была ошибка, теперь разобран.
Код выхода 1, если есть LOST.
"""

import json
import sys
from pathlib import Path

from parsers.core.loader import load_rows
from parsers.registry import parse

EXTENSIONS = {".xlsx", ".xls", ".xml", ".yml", ".pdf"}
SNAPSHOT_DIR = ".parser-snapshots"
ITEM_FIELDS = ("position", "sku", "barcode", "name", "qty", "unit", "price", "total")


def _round(value):
    return round(value, 4) if isinstance(value, float) else value


def run_file(path: Path) -> dict:
    """Результат разбора файла в компактном виде (только то, что влияет на приёмку)."""
    try:
        return summarize(parse(load_rows(str(path))))
    except Exception as exc:  # noqa: BLE001 — для эталона важен сам факт ошибки
        return {"error": f"{exc.__class__.__name__}: {exc}", "items": []}


def run_rows(rows: list) -> dict:
    try:
        return summarize(parse(rows))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}", "items": []}


def case_rows(case: dict) -> list:
    """Строки JSON-кейса: разреженный формат {"индекс колонки": значение} → список ячеек."""
    width = case.get("width", 0)
    rows = []
    for sparse in case["rows"]:
        row = [None] * max(width, 1 + max((int(k) for k in sparse), default=-1))
        for k, v in sparse.items():
            row[int(k)] = v
        rows.append(row)
    return rows


def summarize(result: dict) -> dict:
    meta = result.get("meta") or {}
    totals = result.get("totals") or {}
    return {
        "error": None,
        "supplier": result.get("detected_supplier"),
        "number": meta.get("number"),
        "date": str(meta["date"]) if meta.get("date") else None,
        "total": _round(totals.get("total")),
        "items": [{k: _round(item.get(k)) for k in ITEM_FIELDS} for item in result.get("items") or []],
    }


def _files(folder: Path):
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTENSIONS and SNAPSHOT_DIR not in p.parts)


def _snapshot_path(folder: Path, file: Path) -> Path:
    return folder / SNAPSHOT_DIR / (str(file.relative_to(folder)).replace("/", "__") + ".json")


def snapshot(folder: Path) -> int:
    for file in _files(folder):
        target = _snapshot_path(folder, file)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = run_file(file)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))
        status = data["error"] or f"{len(data['items'])} строк, поставщик {data['supplier']}"
        print(f"  {file.relative_to(folder)}: {status}")
    return 0


def diff_items(old: list, new: list, limit: int = 8) -> list[str]:
    lines = []
    for i in range(max(len(old), len(new))):
        a = old[i] if i < len(old) else None
        b = new[i] if i < len(new) else None
        if a == b:
            continue
        if a is None:
            lines.append(f"    + строка {i + 1}: {b}")
        elif b is None:
            lines.append(f"    - строка {i + 1}: {a}")
        else:
            changed = {k: (a.get(k), b.get(k)) for k in ITEM_FIELDS if a.get(k) != b.get(k)}
            lines.append(f"    ~ строка {i + 1}: " + "; ".join(f"{k}: {x!r} → {y!r}" for k, (x, y) in changed.items()))
        if len(lines) >= limit:
            lines.append("    …")
            break
    return lines


def compare_one(old: dict, new: dict) -> tuple[str, list[str]]:
    if old.get("error") and not new.get("error"):
        return "FIXED", [f"    было: {old['error']}", f"    стало: {len(new['items'])} строк"]
    if new.get("error") and not old.get("error"):
        return "LOST", [f"    ошибка: {new['error']}"]
    if len(new["items"]) < len(old["items"]):
        return "LOST", [
            f"    строк было {len(old['items'])}, стало {len(new['items'])}",
            *diff_items(old["items"], new["items"]),
        ]
    details = []
    for key in ("supplier", "number", "date", "total"):
        if old.get(key) != new.get(key):
            details.append(f"    {key}: {old.get(key)!r} → {new.get(key)!r}")
    details += diff_items(old["items"], new["items"])
    return ("CHANGED", details) if details else ("OK", [])


def compare(folder: Path) -> int:
    counts = {"OK": 0, "CHANGED": 0, "LOST": 0, "FIXED": 0, "NEW": 0}
    for file in _files(folder):
        snap = _snapshot_path(folder, file)
        new = run_file(file)
        if not snap.exists():
            counts["NEW"] += 1
            print(
                f"NEW      {file.relative_to(folder)} — эталона нет ({new['error'] or str(len(new['items'])) + ' строк'})"
            )
            continue
        status, details = compare_one(json.loads(snap.read_text()), json.loads(json.dumps(new, default=str)))
        counts[status] += 1
        if status != "OK":
            print(f"{status:<8} {file.relative_to(folder)}")
            print("\n".join(details))
    print("\nИтого: " + ", ".join(f"{k} {v}" for k, v in counts.items() if v))
    return 1 if counts["LOST"] else 0


def record(folder: Path) -> int:
    for path in sorted(folder.glob("*.json")):
        case = json.loads(path.read_text())
        new = json.loads(json.dumps(run_rows(case_rows(case)), default=str))
        if case.get("expected") != new:
            print(f"{path.name}: обновлён")
            for line in diff_items((case.get("expected") or {}).get("items", []), new["items"]):
                print(line)
        case["expected"] = new
        path.write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n")
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    commands = {"snapshot": snapshot, "compare": compare, "record": record}
    if len(argv) != 2 or argv[0] not in commands:
        print(__doc__)
        return 2
    return commands[argv[0]](Path(argv[1]).resolve())


if __name__ == "__main__":
    sys.exit(main())
