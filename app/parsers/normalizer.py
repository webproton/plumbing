# parsers/normalizer.py



from parsers.core.numbers import safe_float

def normalize_item(item):
    if not item or not isinstance(item, dict):
        return item
    
    item = item.copy()  # чтобы не мутировать оригинал
    item["name"] = str(item.get("name", "")).strip().lower()
    item["sku"] = str(item.get("sku") or "").upper().strip()
    
    # Можно добавить очистку других полей
    if "qty" in item:
        item["qty"] = safe_float(item["qty"])
    
    return item