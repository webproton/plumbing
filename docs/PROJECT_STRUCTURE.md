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
- `Warehouse` (принадлежит `Seller`), `Supplier`, `StockMovement` (журнал: in / out / return_in /
  return_out / adjustment / transfer_in / transfer_out), `InventoryDocument` (загруженная накладная
  + распознанные данные), `ProductBarcode`, `VariantMatchMemory` (память сопоставлений
  «строка поставщика → наш вариант»), `CurrencyRate`.
- `services.py` — проведение накладной, перемещение, возврат, инвентаризация.
- Эндпоинты под `/api/warehouse/`.
- ⚠️ Известные ошибки учёта — исправляются в шаге 1 (см. ROADMAP).

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
