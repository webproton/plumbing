"""
Складской сервис — единственная точка изменения остатков.

Правила:
- каждая операция выполняется в transaction.atomic();
- строки блокируются select_for_update в фиксированном порядке:
  сначала ProductVariant (по возрастанию id), затем StockBalance (по возрастанию warehouse_id) —
  это исключает взаимные блокировки и гонки (оверселл, потерянные обновления);
- движение журнала, StockBalance и кэш ProductVariant.stock/reserved меняются в одной транзакции;
- кэши обновляются через queryset.update(), без ProductVariant.save() (у save() тяжёлые побочные эффекты).

Понятия:
- stock     — физический остаток по всем складам;
- reserved  — зарезервировано под незавершённые заказы;
- available = stock − reserved — доступно к продаже.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils.translation import gettext as _

from app.apps.products.models import ProductVariant
from app.apps.warehouse.models import StockBalance, StockMovement, Warehouse

logger = logging.getLogger(__name__)

QTY_PRECISION = Decimal("0.001")
ZERO = Decimal("0")


class StockError(Exception):
    """Ошибка складской операции (отдаётся клиенту как 400)."""

    code = "stock_error"

    def __init__(self, message, **context):
        super().__init__(message)
        self.message = message
        self.context = context


class InsufficientStockError(StockError):
    code = "insufficient_stock"


def to_quantity(value) -> Decimal:
    """Приводит количество к Decimal(…, 3). Допускаются только положительные значения."""
    try:
        qty = Decimal(str(value)).quantize(QTY_PRECISION, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise StockError(_("Некорректное количество: {value!r}").format(value=value))
    if qty <= ZERO:
        raise StockError(_("Количество должно быть больше нуля, получено {qty}").format(qty=qty))
    return qty


# ---------------------------------------------------------------------------
# Блокировки
# ---------------------------------------------------------------------------


def _lock_variant(variant) -> ProductVariant:
    variant_id = variant.pk if isinstance(variant, ProductVariant) else variant
    return ProductVariant.objects.select_for_update().only("id", "stock", "reserved").get(pk=variant_id)


def _lock_balance(variant_id, warehouse_id) -> StockBalance:
    StockBalance.objects.get_or_create(variant_id=variant_id, warehouse_id=warehouse_id)
    return StockBalance.objects.select_for_update().get(variant_id=variant_id, warehouse_id=warehouse_id)


def _change_cache(variant_id, *, stock_delta=ZERO, reserved_delta=ZERO):
    updates = {}
    if stock_delta:
        updates["stock"] = F("stock") + stock_delta
    if reserved_delta:
        updates["reserved"] = F("reserved") + reserved_delta
    if updates:
        ProductVariant.objects.filter(pk=variant_id).update(**updates)


def _create_movement(*, variant_id, warehouse, movement_type, quantity, user=None, **fields) -> StockMovement:
    return StockMovement.objects.create(
        variant_id=variant_id,
        seller_id=warehouse.seller_id,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        **fields,
    )


# ---------------------------------------------------------------------------
# Приход
# ---------------------------------------------------------------------------


@transaction.atomic
def receive(
    variant, warehouse: Warehouse, quantity, *, user=None, movement_type=StockMovement.IN, **fields
) -> StockMovement:
    """Поступление на склад: приход от поставщика (in) или возврат от клиента (return_in)."""
    if movement_type not in (StockMovement.IN, StockMovement.RETURN_IN):
        raise StockError(_("receive() не поддерживает тип {movement_type}").format(movement_type=movement_type))
    if movement_type == StockMovement.IN and not fields.get("supplier"):
        raise StockError(_("Для прихода необходимо указать поставщика"))

    qty = to_quantity(quantity)
    locked = _lock_variant(variant)
    balance = _lock_balance(locked.pk, warehouse.pk)

    movement = _create_movement(
        variant_id=locked.pk,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=qty,
        user=user,
        **fields,
    )
    StockBalance.objects.filter(pk=balance.pk).update(quantity=F("quantity") + qty)
    _change_cache(locked.pk, stock_delta=qty)
    return movement


# ---------------------------------------------------------------------------
# Расход
# ---------------------------------------------------------------------------


def _write_off_locked(
    locked: ProductVariant,
    warehouse: Warehouse,
    qty: Decimal,
    *,
    movement_type,
    user=None,
    consume_reserved=ZERO,
    **fields,
) -> StockMovement:
    balance = _lock_balance(locked.pk, warehouse.pk)
    if balance.quantity < qty:
        raise InsufficientStockError(
            _("На складе «{name}» недостаточно товара: доступно {quantity}, требуется {qty}").format(
                name=warehouse.name, quantity=balance.quantity, qty=qty
            ),
            variant_id=locked.pk,
            warehouse_id=warehouse.pk,
            available=balance.quantity,
            requested=qty,
        )
    # Свободный (не зарезервированный) остаток не может уйти в минус из-за ручного расхода.
    free_after = (locked.stock - qty) - (locked.reserved - consume_reserved)
    if free_after < ZERO:
        raise InsufficientStockError(
            _("Товар зарезервирован под заказы: свободно {value}, требуется {qty}").format(
                value=locked.stock - locked.reserved, qty=qty
            ),
            variant_id=locked.pk,
            available=locked.stock - locked.reserved,
            requested=qty,
        )

    movement = _create_movement(
        variant_id=locked.pk,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=qty,
        user=user,
        **fields,
    )
    StockBalance.objects.filter(pk=balance.pk).update(quantity=F("quantity") - qty)
    _change_cache(locked.pk, stock_delta=-qty, reserved_delta=-consume_reserved)
    locked.stock -= qty
    locked.reserved -= consume_reserved
    return movement


@transaction.atomic
def write_off(
    variant, warehouse: Warehouse, quantity, *, user=None, movement_type=StockMovement.OUT, **fields
) -> StockMovement:
    """Ручной расход (продажа вне сайта, списание брака) или возврат поставщику."""
    if movement_type not in (StockMovement.OUT, StockMovement.RETURN_OUT):
        raise StockError(_("write_off() не поддерживает тип {movement_type}").format(movement_type=movement_type))
    if movement_type == StockMovement.RETURN_OUT and not fields.get("supplier"):
        raise StockError(_("Для возврата поставщику необходимо указать поставщика"))
    qty = to_quantity(quantity)
    locked = _lock_variant(variant)
    return _write_off_locked(locked, warehouse, qty, movement_type=movement_type, user=user, **fields)


def return_to_supplier(variant, warehouse, supplier, quantity, user=None, comment=_("Возврат поставщику")):
    return write_off(
        variant,
        warehouse,
        quantity,
        user=user,
        movement_type=StockMovement.RETURN_OUT,
        supplier=supplier,
        comment=comment,
    )


@transaction.atomic
def reverse_receipts(lines, *, user=None, **fields) -> list[StockMovement]:
    """
    Сторно приходов — отмена ошибочно проведённой накладной (дубль, не тот склад, не те количества).
    lines: [(variant_id, warehouse, qty, price_per_unit)]. Всё или ничего: проданный и зарезервированный
    под заказы товар не трогается; если чего-то не хватает — InsufficientStockError со списком shortages.
    """
    grouped = {}
    for variant_id, warehouse, qty, price in lines:
        key = (variant_id, warehouse.pk)
        prev = grouped.get(key)
        grouped[key] = (warehouse, (prev[1] if prev else ZERO) + to_quantity(qty), price)

    movements, shortages = [], []
    for variant_id in sorted({key[0] for key in grouped}):
        locked = _lock_variant(variant_id)
        items = [(wh_id, *grouped[(variant_id, wh_id)]) for vid, wh_id in sorted(grouped) if vid == variant_id]
        balances = {wh_id: _lock_balance(variant_id, wh_id).quantity for wh_id, *_ in items}
        need = sum(qty for _, _, qty, _ in items)
        on_hand = sum(min(balances[wh_id], qty) for wh_id, _, qty, _ in items)  # есть на тех же складах
        available = max(min(locked.stock - locked.reserved, on_hand), ZERO)  # и не в резерве
        if available < need:
            shortages.append({"variant_id": variant_id, "required": need, "available": available})
            continue
        for _wh_id, warehouse, qty, price in items:
            movements.append(
                _write_off_locked(
                    locked,
                    warehouse,
                    qty,
                    movement_type=StockMovement.IN_REVERSAL,
                    user=user,
                    price_per_unit=price,
                    **fields,
                )
            )
    if shortages:
        raise InsufficientStockError(
            _("Часть товара уже продана или зарезервирована — отменить приход нельзя"), shortages=shortages
        )
    return movements


# ---------------------------------------------------------------------------
# Перемещение и инвентаризация
# ---------------------------------------------------------------------------


@transaction.atomic
def transfer(variant, from_warehouse: Warehouse, to_warehouse: Warehouse, quantity, *, user=None):
    """Перемещение между складами. Общий остаток не меняется."""
    if from_warehouse.pk == to_warehouse.pk:
        raise StockError(_("Склад-отправитель и склад-получатель совпадают"))
    qty = to_quantity(quantity)
    locked = _lock_variant(variant)

    # блокируем оба остатка в порядке id склада
    for wh_id in sorted((from_warehouse.pk, to_warehouse.pk)):
        _lock_balance(locked.pk, wh_id)
    source = StockBalance.objects.get(variant_id=locked.pk, warehouse_id=from_warehouse.pk)
    if source.quantity < qty:
        raise InsufficientStockError(
            _("На складе «{name}» недостаточно товара: доступно {quantity}, требуется {qty}").format(
                name=from_warehouse.name, quantity=source.quantity, qty=qty
            ),
            variant_id=locked.pk,
            warehouse_id=from_warehouse.pk,
            available=source.quantity,
            requested=qty,
        )

    out_mv = _create_movement(
        variant_id=locked.pk,
        warehouse=from_warehouse,
        movement_type=StockMovement.TRANSFER_OUT,
        quantity=qty,
        user=user,
        comment=f"Перемещение → {to_warehouse.name}",
    )
    in_mv = _create_movement(
        variant_id=locked.pk,
        warehouse=to_warehouse,
        movement_type=StockMovement.TRANSFER_IN,
        quantity=qty,
        user=user,
        comment=f"Перемещение ← {from_warehouse.name}",
    )
    StockBalance.objects.filter(variant_id=locked.pk, warehouse_id=from_warehouse.pk).update(
        quantity=F("quantity") - qty
    )
    StockBalance.objects.filter(variant_id=locked.pk, warehouse_id=to_warehouse.pk).update(quantity=F("quantity") + qty)
    return out_mv, in_mv


@transaction.atomic
def adjust(variant, warehouse: Warehouse, real_quantity, *, user=None, comment=""):
    """
    Инвентаризация: приводит остаток склада к фактическому, создавая движение излишка/недостачи.
    Фактический остаток может оказаться меньше резерва — это реальность склада, операция разрешена,
    но пишется предупреждение (заказы с таким товаром нужно разбирать вручную).
    """
    try:
        real = Decimal(str(real_quantity)).quantize(QTY_PRECISION, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise StockError(_("Некорректное количество: {real_quantity!r}").format(real_quantity=real_quantity))
    if real < ZERO:
        raise StockError(_("Фактический остаток не может быть отрицательным"))

    locked = _lock_variant(variant)
    balance = _lock_balance(locked.pk, warehouse.pk)
    diff = real - balance.quantity
    if diff == ZERO:
        return None

    movement_type = StockMovement.ADJUSTMENT if diff > ZERO else StockMovement.ADJUSTMENT_OUT
    movement = _create_movement(
        variant_id=locked.pk,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=abs(diff),
        user=user,
        comment=comment or f"Инвентаризация: было {balance.quantity}, стало {real}",
    )
    StockBalance.objects.filter(pk=balance.pk).update(quantity=real)
    _change_cache(locked.pk, stock_delta=diff)
    if locked.stock + diff < locked.reserved:
        logger.warning(
            "Инвентаризация: остаток варианта %s (%s) меньше резерва (%s)",
            locked.pk,
            locked.stock + diff,
            locked.reserved,
        )
    return movement


# ---------------------------------------------------------------------------
# Резервы под заказы
# ---------------------------------------------------------------------------


def _sorted_lines(lines):
    """lines: iterable[(variant_or_id, qty)] → [(variant_id, Decimal)] по возрастанию id, дубли суммируются."""
    merged = {}
    for variant, qty in lines:
        vid = variant.pk if isinstance(variant, ProductVariant) else variant
        merged[vid] = merged.get(vid, ZERO) + to_quantity(qty)
    return sorted(merged.items())


@transaction.atomic
def reserve(lines):
    """
    Резервирует товар под заказ. Всё или ничего: если хотя бы одной позиции не хватает —
    InsufficientStockError, ни один резерв не создаётся.
    """
    for variant_id, qty in _sorted_lines(lines):
        locked = _lock_variant(variant_id)
        available = locked.stock - locked.reserved
        if available < qty:
            raise InsufficientStockError(
                _("Недостаточно товара (id {variant_id}): доступно {value}, требуется {qty}").format(
                    variant_id=variant_id, value=max(available, ZERO), qty=qty
                ),
                variant_id=variant_id,
                available=max(available, ZERO),
                requested=qty,
            )
        _change_cache(variant_id, reserved_delta=qty)


@transaction.atomic
def release(lines):
    """Снимает резерв (отмена заказа)."""
    for variant_id, qty in _sorted_lines(lines):
        locked = _lock_variant(variant_id)
        release_qty = min(qty, locked.reserved)
        if release_qty != qty:
            logger.warning(
                "Снятие резерва варианта %s: резерв %s меньше снимаемого %s", variant_id, locked.reserved, qty
            )
        if release_qty > ZERO:
            _change_cache(variant_id, reserved_delta=-release_qty)


@transaction.atomic
def write_off_reserved(lines, *, user=None, comment="", from_reserve=True, **fields):
    """
    Списывает товар по заказу (выдача/отгрузка).
    from_reserve=True — товар был зарезервирован этим заказом, резерв уменьшается вместе с остатком;
    from_reserve=False — заказ не резервировал товар (старые заказы), чужие резервы не трогаются.
    Склады выбираются автоматически: сначала склад по умолчанию, затем с наибольшим остатком.
    """
    movements = []
    for variant_id, qty in _sorted_lines(lines):
        locked = _lock_variant(variant_id)
        consume = min(qty, locked.reserved) if from_reserve else ZERO
        remaining = qty
        balances = (
            StockBalance.objects.select_for_update(of=("self",))
            .filter(variant_id=variant_id, quantity__gt=0)
            .select_related("warehouse")
            .order_by("warehouse_id")
        )
        candidates = sorted(balances, key=lambda b: (not b.warehouse.is_default, -b.quantity))
        for bal in candidates:
            if remaining <= ZERO:
                break
            take = min(bal.quantity, remaining)
            take_reserved = min(take, consume)
            movements.append(
                _write_off_locked(
                    locked,
                    bal.warehouse,
                    take,
                    movement_type=StockMovement.OUT,
                    user=user,
                    consume_reserved=take_reserved,
                    comment=comment,
                    **fields,
                )
            )
            consume -= take_reserved
            remaining -= take
        if remaining > ZERO:
            raise InsufficientStockError(
                _("Недостаточно товара на складах для списания (id {variant_id}): не хватает {remaining}").format(
                    variant_id=variant_id, remaining=remaining
                ),
                variant_id=variant_id,
                requested=qty,
                missing=remaining,
            )
    return movements


# ---------------------------------------------------------------------------
# Чтение и пересчёт
# ---------------------------------------------------------------------------


def get_balance(variant, warehouse=None) -> Decimal:
    qs = StockBalance.objects.filter(variant=variant)
    if warehouse is not None:
        qs = qs.filter(warehouse=warehouse)
    return qs.aggregate(total=Sum("quantity"))["total"] or ZERO


def journal_balance(variant_id, warehouse_id=None) -> Decimal:
    """Остаток, посчитанный напрямую по журналу (для сверки)."""
    qs = StockMovement.objects.filter(variant_id=variant_id)
    if warehouse_id is not None:
        qs = qs.filter(warehouse_id=warehouse_id)
    agg = qs.aggregate(
        inc=Sum("quantity", filter=Q(movement_type__in=StockMovement.INCOMING_TYPES)),
        out=Sum("quantity", filter=Q(movement_type__in=StockMovement.OUTGOING_TYPES)),
    )
    return (agg["inc"] or ZERO) - (agg["out"] or ZERO)


@transaction.atomic
def rebuild_from_journal(variant) -> Decimal:
    """Пересчитывает StockBalance и ProductVariant.stock по журналу. Резерв не трогает."""
    locked = _lock_variant(variant)
    warehouse_ids = set(
        StockMovement.objects.filter(variant_id=locked.pk).values_list("warehouse_id", flat=True)
    ) | set(StockBalance.objects.filter(variant_id=locked.pk).values_list("warehouse_id", flat=True))
    total = ZERO
    for wh_id in sorted(warehouse_ids):
        qty = journal_balance(locked.pk, wh_id)
        StockBalance.objects.update_or_create(variant_id=locked.pk, warehouse_id=wh_id, defaults={"quantity": qty})
        total += qty
    ProductVariant.objects.filter(pk=locked.pk).update(stock=total)
    return total
