"""
Клиент API Новой Почты (https://developers.novaposhta.ua).

Без ключа работают: поиск населённых пунктов и отделений, стоимость и срок доставки, отслеживание.
Ключ (NOVA_POSHTA_API_KEY) нужен для создания ТТН. Справочники кэшируются.
"""

import hashlib
import json
import logging
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

API_URL = "https://api.novaposhta.ua/v2.0/json/"
TIMEOUT = (5, 15)
# Статусы ТТН (StatusCode): получено / окончательные / отказ и возврат
# 7 — прибыл в отделение, 8 — прибыл и загружен в почтомат: покупателю пора забирать
ARRIVED_CODES = {"7", "8"}
RECEIVED_CODES = {"9", "10", "11", "106"}
FINAL_CODES = RECEIVED_CODES | {"2", "102", "103", "105", "108"}


class NovaPoshtaError(Exception):
    pass


def enabled_ttn() -> bool:
    return bool(settings.NOVA_POSHTA_API_KEY)


def call(model: str, method: str, props: dict, *, cache_for: int = 0, use_key: bool = True) -> list:
    payload = {
        "apiKey": settings.NOVA_POSHTA_API_KEY if use_key else "",
        "modelName": model,
        "calledMethod": method,
        "methodProperties": props,
    }
    key = None
    if cache_for:
        digest = hashlib.sha1(
            json.dumps([model, method, props], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        key = f"np:{digest}"
        cached = cache.get(key)
        if cached is not None:
            return cached
    try:
        response = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Нова Пошта %s.%s недоступна: %s", model, method, exc)
        raise NovaPoshtaError(_("Сервис Новой Почты временно недоступен")) from exc
    if not data.get("success"):
        errors = "; ".join(data.get("errors") or []) or _("неизвестная ошибка")
        raise NovaPoshtaError(_("Нова Пошта: {error}").format(error=errors))
    result = data.get("data") or []
    if key:
        cache.set(key, result, cache_for)
    return result


def search_cities(query: str, limit: int = 15) -> list[dict]:
    """Населённые пункты, где есть отделения: ref — CityRef для поиска отделений."""
    query = query.strip()
    if len(query) < 2:
        return []
    rows = call(
        "Address",
        "searchSettlements",
        {"CityName": query, "Limit": str(limit), "Page": "1"},
        cache_for=86400,
        use_key=False,
    )
    found = []
    for block in rows:
        for a in block.get("Addresses") or []:
            if int(a.get("Warehouses") or 0) > 0 and a.get("DeliveryCity"):
                found.append(
                    {
                        "ref": a["DeliveryCity"],
                        "name": a.get("MainDescription") or "",
                        "label": a.get("Present") or a.get("MainDescription") or "",
                        "warehouses": int(a.get("Warehouses") or 0),
                    }
                )
    return found


def warehouses(city_ref: str, query: str = "", lang: str = "uk", limit: int = 40) -> list[dict]:
    """Отделения и поштоматы города; поиск по номеру или улице."""
    props = {"CityRef": city_ref, "Limit": str(limit), "Page": "1"}
    if query.strip():
        props["FindByString"] = query.strip()
    rows = call("AddressGeneral", "getWarehouses", props, cache_for=12 * 3600, use_key=False)
    result = []
    for w in rows:
        if w.get("WarehouseStatus") not in (None, "", "Working"):
            continue
        result.append(
            {
                "ref": w["Ref"],
                "number": w.get("Number") or "",
                "name": (w.get("DescriptionRu") if lang == "ru" else w.get("Description"))
                or w.get("Description")
                or "",
                "kind": "postomat" if w.get("CategoryOfWarehouse") == "Postomat" else "branch",
                "max_weight": int(float(w.get("TotalMaxWeightAllowed") or w.get("PlaceMaxWeightAllowed") or 0)) or None,
            }
        )
    q = query.strip()
    if q.isdigit():  # «12» — сначала отделение №12, потом №120…, остальные совпадения
        result.sort(key=lambda w: (w["number"] != q, not w["number"].startswith(q)))
    return result


def estimate(city_ref: str, cost: float, weight: float = 1.0, sender_city_ref: str = "") -> dict | None:
    """Стоимость и дата доставки отделение → отделение (если задан город отправителя)."""
    if not sender_city_ref:
        return None
    common = {"CitySender": sender_city_ref, "CityRecipient": city_ref, "ServiceType": "WarehouseWarehouse"}
    price = call(
        "InternetDocument",
        "getDocumentPrice",
        {
            **common,
            "Weight": str(max(weight, 0.1)),
            "Cost": str(max(int(cost), 1)),
            "CargoType": "Cargo",
            "SeatsAmount": "1",
        },
        cache_for=3600,
        use_key=False,
    )
    when = call("InternetDocument", "getDocumentDeliveryDate", common, cache_for=3600, use_key=False)
    delivery = ((when[0] if when else {}).get("DeliveryDate") or {}).get("date", "")[:10] or None
    return {"cost": price[0].get("Cost") if price else None, "date": delivery}


def track(documents: list[tuple[str, str]]) -> list[dict]:
    """[(номер ТТН, телефон)] → статусы. С телефоном отправителя/получателя данных больше."""
    if not documents:
        return []
    rows = call(
        "TrackingDocument",
        "getStatusDocuments",
        {"Documents": [{"DocumentNumber": n, "Phone": p or ""} for n, p in documents[:100]]},
    )
    return [
        {
            "number": r.get("Number"),
            "status": r.get("Status") or "",
            "code": str(r.get("StatusCode") or ""),
            "scheduled": (r.get("ScheduledDeliveryDate") or "")[:10] or None,
            "warehouse": r.get("WarehouseRecipient") or "",
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Создание ТТН (нужен ключ API и отправитель в настройках магазина)
# ---------------------------------------------------------------------------


def _sender() -> tuple[str, str]:
    """Ref контрагента-отправителя и его контактного лица (из кабинета Новой Почты владельца ключа)."""
    cached = cache.get("np:sender")
    if cached:
        return cached
    senders = call("Counterparty", "getCounterparties", {"CounterpartyProperty": "Sender", "Page": "1"})
    if not senders:
        raise NovaPoshtaError(_("В кабинете Новой Почты нет отправителя"))
    sender_ref = senders[0]["Ref"]
    contacts = call("Counterparty", "getCounterpartyContactPersons", {"Ref": sender_ref, "Page": "1"})
    if not contacts:
        raise NovaPoshtaError(_("У отправителя нет контактного лица"))
    result = (sender_ref, contacts[0]["Ref"])
    cache.set("np:sender", result, 86400)
    return result


def _recipient(name: str, phone: str) -> tuple[str, str]:
    # в заказе имя записано «Имя Фамилия»
    parts = name.split()
    first, last = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (name, name)
    data = call(
        "Counterparty",
        "save",
        {
            "FirstName": first,
            "LastName": last,
            "MiddleName": "",
            "Phone": phone,
            "Email": "",
            "CounterpartyType": "PrivatePerson",
            "CounterpartyProperty": "Recipient",
        },
    )
    recipient = data[0]
    contact = ((recipient.get("ContactPerson") or {}).get("data") or [{}])[0].get("Ref")
    if not contact:
        raise NovaPoshtaError(_("Не удалось создать получателя"))
    return recipient["Ref"], contact


def create_document(
    *,
    city_ref: str,
    warehouse_ref: str,
    recipient_name: str,
    recipient_phone: str,
    sender_city_ref: str,
    sender_warehouse_ref: str,
    sender_phone: str,
    weight: float,
    seats: int,
    description: str,
    declared_cost: float,
    payer: str = "Recipient",
    cod_amount: float | None = None,
) -> dict:
    """→ {"number": ТТН, "ref": Ref, "cost": стоимость доставки, "date": ожидаемая дата}"""
    if not enabled_ttn():
        raise NovaPoshtaError(_("Не задан ключ API Новой Почты"))
    if not (sender_city_ref and sender_warehouse_ref and sender_phone):
        raise NovaPoshtaError(_("Укажите город, отделение и телефон отправителя в настройках магазина"))
    sender, contact_sender = _sender()
    recipient, contact_recipient = _recipient(recipient_name, recipient_phone)
    props = {
        "PayerType": payer,
        "PaymentMethod": "Cash",
        "DateTime": date.today().strftime("%d.%m.%Y"),
        "CargoType": "Parcel",
        "Weight": str(weight),
        "ServiceType": "WarehouseWarehouse",
        "SeatsAmount": str(seats),
        "Description": description[:100],
        "Cost": str(max(int(round(declared_cost)), 1)),
        "CitySender": sender_city_ref,
        "Sender": sender,
        "SenderAddress": sender_warehouse_ref,
        "ContactSender": contact_sender,
        "SendersPhone": sender_phone,
        "CityRecipient": city_ref,
        "Recipient": recipient,
        "RecipientAddress": warehouse_ref,
        "ContactRecipient": contact_recipient,
        "RecipientsPhone": recipient_phone,
    }
    if cod_amount:
        props["BackwardDeliveryData"] = [
            {"PayerType": "Recipient", "CargoType": "Money", "RedeliveryString": str(round(cod_amount, 2))}
        ]
    data = call("InternetDocument", "save", props)
    doc = data[0]
    return {
        "number": doc.get("IntDocNumber"),
        "ref": doc.get("Ref"),
        "cost": doc.get("CostOnSite"),
        "date": (doc.get("EstimatedDeliveryDate") or "")[:10] or None,
    }
