# parsers/schema.py
UNIVERSAL_SCHEMA = {
    "supplier": None,

    "meta": {
        "raw_title": None,
        "number": None,
        "date": None,

        "supplier": None,
        "buyer": None,
        
        "supplier_edrpou": None,
        "buyer_edrpou": None,
        "buyer_raw": None,
        
        "iban": None,
        "mfo": None,
        
        "delivery_address": None,

        "supplier_phones": [],
        "buyer_phones": [],
        "supplier_emails": [],
        "buyer_emails": [],

        "contact_person": None,
        "shipping_terms": None,
    },

       "items": [
        {
            "position": None,
            "sku": None,
            "barcode": None,  # 🔥 ДОБАВИЛИ СЮДА: для интеграции со сканером
            "name": None,

            "qty": None,
            "unit": None,

            "price": None,
            "total": None
        }
    ],
    
    "totals": {
        "total": None,
        "vat": None,
        "weight": None,
        "volume": None,
        "summary": None
    },

    "footer": [],
    "warnings": [],
    "signatures": {
        "executor": None,
        "receiver": None
    },

    "confidence": 0.0,
    "detected_supplier": None
}