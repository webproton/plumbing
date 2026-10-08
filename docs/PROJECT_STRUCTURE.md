# PlumbingProject — структура и устройство проекта

Живой документ: описывает, **что есть**, **как работает** и **что менялось**.
Дополняется после каждого шага из [ROADMAP.md](ROADMAP.md).

---

## 1. Обзор

Интернет-магазин сантехники (B2C/B2B) со складским учётом, приёмкой товара по накладным
поставщиков (Excel/XML) и сканером штрихкодов.

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, Django 4.2, DRF 3.15, SimpleJWT, allauth + dj-rest-auth |
| БД / кэш | PostgreSQL 14, Redis (кэш Django) |
| Парсеры | openpyxl, pandas, rapidfuzz |
| Frontend | React (CRA, JS) — будет переписан на TS (шаг 7) |
| Infra | Docker Compose, nginx, gunicorn |

---

## 2. Дерево проекта

```
PlumbingProject/
├── config/                 # Django-проект: settings, urls, wsgi/asgi
├── app/
│   ├── manage.py
│   ├── core/               # общий код (middleware)
│   ├── apps/
│   │   ├── accounts/       # пользователи, профиль, регистрация/логин (allauth + dj-rest-auth)
│   │   ├── products/       # каталог: Category, Product, ProductVariant, Wishlist, справочники
│   │   ├── orders/         # Cart, CartItems, Order
│   │   ├── warehouse/      # склады, поставщики, журнал движений, накладные, сканер
│   │   ├── sellers/        # продавцы (Seller) и витрины (Shop)
│   │   ├── callback/       # заявка «перезвоните мне» → Telegram, настройки сайта
│   │   └── telemetry/      # антифрод/телеметрия — ОТКЛЮЧЕНО (нет в INSTALLED_APPS и urls)
│   ├── parsers/            # парсеры накладных поставщиков (см. §5)
│   ├── geoip/              # базы GeoLite2 (для telemetry)
│   └── fonts/
├── frontend/plumbreact/    # React SPA + nginx.conf для прод-контейнера
├── docs/                   # эта документация
├── Dockerfile, docker-compose.prod.yml
├── requirements.txt        # runtime-зависимости
├── requirements-dev.txt    # тесты, линтеры
├── pytest.ini, conftest.py # конфигурация тестов
└── .env.example            # все переменные окружения
```

---

## 3. Backend: приложения и ответственность

### accounts
- `User` (логин по email), `Profile` (контакты, создаётся сигналом при создании пользователя;
  для анонимных заказов создаётся профиль без пользователя).
- Эндпоинты `/api/dj-rest-auth/`: `login/`, `logout/`, `user/`, `profile/`, `password/*`,
  `token/refresh/`, `registration/`.
- Вход разрешён только с подтверждённым email (`ACCOUNT_EMAIL_VERIFICATION=mandatory`).

### products
- `Category` → `Product` → `ProductVariant` (цена, скидка, штрихкод, код, остаток `stock`/`reserved`,
  себестоимость `cost_price`, ~20 атрибутов мебели/сантехники).
- `ProductVariant.save()` генерирует slug, код, штрихкод и картинку штрихкода, пересчитывает скидку.
- Эндпоинты: `/api/products/`, `/api/category/`, `/api/new_products/`, `/api/wishlist/`.

### orders
- `Cart` (анонимная по `cart_uuid` или привязанная к пользователю) → `CartItems`.
- `Order` ссылается на корзину; итог считается по текущим ценам вариантов.
- Эндпоинты: `/api/orders/cart/`, `/api/orders/order-create/`, `/api/orders/history/`.
- ⚠️ Пока не резервирует и не списывает остаток — исправляется в шаге 2.

### warehouse
Модели:
- `Warehouse` (склад продавца), `Supplier` (общий справочник поставщиков);
- `StockMovement` — **журнал движений, единственный источник истины**. Типы: `in`, `out`, `return_in`,
  `return_out`, `adjustment` (излишек), `adjustment_out` (недостача), `transfer_in`, `transfer_out`.
  Количество всегда > 0 (ограничение в БД), направление задаёт тип. Записи не редактируются и не удаляются
  (API — только чтение и создание через сервис, admin — только чтение, FK с `PROTECT`);
- `StockBalance` — остаток пары (вариант, склад), кэш журнала;
- `InventoryDocument` — загруженная накладная + распознанные данные + отчёт проведения
  (`extracted_data.processing_report`);
- `ProductBarcode`, `VariantMatchMemory`, `CurrencyRate`.

**Остатки** (`ProductVariant`): `stock` — физический остаток по всем складам, `reserved` — резерв под заказы,
`available_stock = stock − reserved`. Все — `Decimal(12,3)` (метры, кг).

**Сервис `warehouse/stock.py`** — единственное место, меняющее остатки:

| Функция | Что делает |
|---|---|
| `receive` | приход от поставщика (`in`, поставщик обязателен) или возврат клиента (`return_in`) |
| `write_off` / `return_to_supplier` | ручной расход / возврат поставщику; не трогает зарезервированное |
| `transfer` | перемещение между складами (`transfer_out` + `transfer_in`) |
| `adjust` | инвентаризация: приводит склад к факту движением излишка/недостачи |
| `reserve` / `release` | резерв под заказ (всё или ничего) / снятие резерва |
| `write_off_reserved` | списание зарезервированного при выдаче заказа (сначала склад по умолчанию) |
| `rebuild_from_journal` | пересчёт кэшей по журналу (admin-действие «Сверить и пересчитать») |

Как защищено от гонок: каждая функция — `transaction.atomic()`, строки блокируются `select_for_update`
в фиксированном порядке (варианты по id → остатки по id склада), поэтому нет ни оверселла, ни deadlock'ов.
Нехватка товара → `InsufficientStockError` → API отвечает `400 {"detail", "code": "insufficient_stock", ...}`
(обработчик `app/core/exceptions.py`).

**Проведение накладной** (`services.process_inventory_document`): документ блокируется, повторное проведение
запрещено; каждая строка → `stock.receive`; некорректные строки не валят документ, а попадают в
`processing_report.skipped`; новые товары создаются скрытыми (`available=False`) с наценкой 40 %.

**Эндпоинты** (`/api/warehouse/`, доступ — суперпользователь или одобренный активный продавец, только свои склады):

| Метод и путь | Назначение |
|---|---|
| `GET/POST/PATCH warehouses/`, `GET warehouses/{id}/balances/` | склады и остатки |
| `GET/POST/... suppliers/` | поставщики (удаление = деактивация) |
| `GET stock-movements/`, `GET stock-movements/{id}/` | журнал (фильтры: тип, склад, вариант, документ) |
| `POST stock-movements/` | ручная операция `in/out/return_in/return_out` |
| `POST stock-movements/transfer/` · `return_supplier/` · `inventory/` | перемещение, возврат, инвентаризация |
| `GET/POST inventory-documents/` | накладные (xlsx/xls/xml/yml, ≤10 МБ) |
| `POST inventory-documents/{id}/process/` | провести накладную → отчёт `{received, skipped}` |
| `POST inventory-documents/{id}/scan/` | пик сканера = +1 шт. по документу |
| `GET inventory-documents/{id}/print/` | PDF (генерируется в памяти, не сохраняется в media) |
| `POST stock-movements/find_by_barcode_or_sku/` | сканер: поиск по штрихкоду/артикулу |
| `POST stock-movements/create_and_add/` | сканер: новый товар (+ приход, если указан документ) |
| `GET scanner-test/` | тестовая страница сканера (только staff) |

### sellers
- `Seller` (OneToOne с User), `Shop`. Эндпоинты `/api/sellers/`.

### callback
- `POST /api/callback/request/` → сообщение менеджеру в Telegram;
  `GET /api/callback/site-settings/`.

---

## 4. Конфигурация

Все настройки — в `config/settings.py`, значения из переменных окружения (`.env`, см. `.env.example`).

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `SECRET_KEY` | ключ Django | обязательна |
| `DEBUG` | режим отладки | `False` |
| `DJANGO_ALLOWED_HOSTS` | хосты через запятую | `localhost,127.0.0.1` |
| `FRONTEND_URL` | адрес SPA (ссылки в письмах) | `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | разрешённые источники | `FRONTEND_URL` |
| `TRUSTED_PROXY` | брать IP клиента из `X-Real-IP` (только за своим nginx) | `False` |
| `POSTGRES_*` | подключение к БД | — |
| `REDIS_URL` / `CACHE_URL` | кэш | `redis://localhost:6379/1` |
| `EMAIL_*` | SMTP; при `DEBUG=True` письма пишутся в консоль | — |
| `TOKEN_BOT`, `MANAGERS` | Telegram-бот и chat_id менеджеров | — |
| `THROTTLE_ANON`, `THROTTLE_USER` | лимиты запросов | `120/min`, `300/min` |

**IP клиента за прокси.** `app.core.middleware.RealIPMiddleware` при `TRUSTED_PROXY=True`
подставляет `X-Real-IP` (его ставит наш nginx) в `REMOTE_ADDR`. DRF (`NUM_PROXIES=0`), axes и
django-ratelimit смотрят только на `REMOTE_ADDR`, поэтому подделать IP через `X-Forwarded-For` нельзя.

---

## 5. Парсеры накладных (`app/parsers`)

```
load_rows(file)            core/loader.py   xlsx/xls/xml/yml → список строк
  → detect_supplier(rows)  detect.py        поставщик по ключевым словам в шапке
  → Parser.parse(rows)     suppliers/*.py   aquadom, presto, santan, default
  → normalize_item()       normalizer.py
  → {meta, items[], totals, warnings, detected_supplier}
```
Проведение результата на склад: `warehouse/services.py::process_inventory_document`.

---

## 6. Тесты

Тесты склада: `app/apps/warehouse/tests/` — сервис, API/права, конкурентные (10 потоков
резервируют товар с остатком 5 → ровно 5 успешных; без блокировки тест падает).


```bash
pip install -r requirements-dev.txt
# нужна PostgreSQL (ArrayField); параметры — POSTGRES_* в окружении
pytest
```
`conftest.py` подменяет кэш на locmem и почту на locmem, очищает кэш между тестами.

---

## 7. Миграции: обновление существующей БД

В репозитории миграции `warehouse` ссылались на серию миграций `products`, которой не было в git
(`0002_product_seller…`, `0003_category_barcode…`, `0004_productvariant_cost_price…`).
Цепочка исправлена: эти поля добавляет `products/0014_category_barcode_category_barcode_image_and_more`.

- **Новая БД:** `python app/manage.py migrate` — работает с нуля.
- **Существующая БД, где поля уже есть** (создавались «потерянными» миграциями):
  ```bash
  python app/manage.py showmigrations products warehouse   # посмотреть состояние
  python app/manage.py migrate products 0014 --fake        # поля уже есть — только отметить
  python app/manage.py migrate                             # остальное
  ```
  Перед этим — `pg_dump` резервная копия.

---

## 8. Журнал изменений

### 2026-10-08 — Шаг 0: восстановление работоспособности
**Было:** после коммита `5d0fac2` API висело в корне (`/products/products/…`), а `accounts.urls`
не подключались (логин, профиль, refresh-токен давали 404). Секреты, БД и Redis были захардкожены
в settings, `DEBUG=True`, CORS открыт для всех, `__init__.py` игнорировались git'ом (миграции
не применялись на чистом клоне), граф миграций ссылался на несуществующие файлы, половина
зависимостей отсутствовала в `requirements.txt`, 10 из 44 тестов падали.

**Стало:**
- все API под `/api/`, namespace'ы: `products`, `orders`, `callback`, `sellers`, `warehouse`, `dj-rest-auth`;
- settings на env, безопасные prod-дефолты, логи в stdout, `token_blacklist` для logout;
- корректный IP клиента за nginx (`RealIPMiddleware`), axes блокирует по паре email+IP;
- убран `django.contrib.gis` (GIS-полей нет; GDAL больше не нужен);
- исправлен граф миграций, добавлены `products/0014`, `accounts/0005`;
- `requirements.txt` — только реально используемые пакеты, `requirements-dev.txt` — тесты;
- удалено правило «нельзя входить, если в пароле есть слово password»;
- тесты: 42/42.

### 2026-10-08 — Чистка
Удалены: `warehouse/views copy.py`, `admin copy.py`, старые `warehouse/parsers.py` и `parsersb.py`
(заменены `app/parsers`), копии шаблонов сканера, старые версии команды импорта
(`etalon`, `get_col_norm`, `*_backup`, `*_origin`), пустой `app/plumbing`, `plumbing.conf`,
`.DS_Store`, TLS-ключ и сертификат из git.
⚠️ Ключ был в истории git — при использовании где-либо его нужно перевыпустить.

### 2026-10-08 — Шаг 1: склад
**Было:** приход по накладной считался дважды (сигнал пересчёта + ручной `stock += qty`); пересчёт учитывал только
`in/out`; проверка остатка в `clean()` никогда не вызывалась → остатки уходили в минус; ни одной блокировки строк;
`stock` — целое число (дробные метры обрезались); повторяющиеся строки накладной молча пропускались; журнал
редактировался и удалялся через API (`AllowAny`!) и admin; удаление продавца каскадно стирало историю; сканер
был открыт анонимам и писал розничную цену как закупочную; `Supplier.code` (несуществующее поле) валил проведение;
себестоимость округлялась до копеек; PDF складывались в публичный `/media/`.

**Стало:** сервис `warehouse/stock.py` + модель `StockBalance`; `Decimal(12,3)`; журнал неизменяемый, `PROTECT`;
индексы журнала; права «только одобренный продавец, только свои склады»; проведение накладной идемпотентно,
с отчётом о пропущенных строках; новые товары скрыты; сканер ищет по штрихкоду/артикулу без учёта регистра,
не создаёт мусорные карточки «NEW …», цену берёт из накладной или себестоимости; PDF отдаётся из памяти;
admin журнала — только чтение + действие «Сверить и пересчитать».

**Миграции:** `products/0015` (stock/reserved → Decimal), `warehouse/0012` (StockBalance, PROTECT, индексы),
`warehouse/0013` (data: удаляет нулевые движения, переворачивает отрицательные, строит остатки по журналу,
обнуляет `reserved`, печатает число отрицательных остатков — их нужно разобрать инвентаризацией),
`warehouse/0014` (ограничение `quantity > 0`).

**API-изменения для клиентов:** ошибки склада — `400 {"detail", "code"}` (было 500); `PUT/PATCH/DELETE`
движений → 405; эндпоинт `variants/create-from-scanner/` объединён с `stock-movements/create_and_add/`;
`accept` удалён (дублировал `process`); `print` возвращает PDF, а не путь на сервере.

Тесты: 72 (+30 склада).
