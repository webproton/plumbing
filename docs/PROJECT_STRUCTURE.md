# PlumbingProject — структура и устройство проекта

Живой документ: описывает, **что есть**, **как работает** и **что менялось**.
Дополняется после каждого шага из [ROADMAP.md](ROADMAP.md). Пофайловая карта, удалённое и архив —
в [PROJECT_MAP.md](PROJECT_MAP.md).

---

## 1. Обзор

Интернет-магазин сантехники (B2C/B2B) со складским учётом, приёмкой товара по накладным
поставщиков (Excel/XML) и сканером штрихкодов.

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, Django 4.2, DRF 3.15, SimpleJWT, allauth + dj-rest-auth |
| БД / кэш | PostgreSQL 14, Redis (кэш Django) |
| Парсеры | openpyxl, pandas, rapidfuzz |
| Frontend | React Router 8 (SSR), React 19, TypeScript, Tailwind CSS 4 — `frontend/web` |
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
│   │   └── callback/       # заявка «перезвоните мне» → Telegram, настройки сайта
│   ├── parsers/            # парсеры накладных поставщиков (см. §5)
│   └── fonts/
├── frontend/web/           # витрина: SSR на React Router 8 (TS)
├── deploy/nginx/           # конфиг nginx перед Django и фронтендом
├── docs/                   # эта документация
├── Dockerfile, docker-compose.prod.yml
├── requirements.txt        # runtime-зависимости
├── requirements-dev.txt    # тесты, линтеры
├── pytest.ini, conftest.py # конфигурация тестов
└── .env.example            # все переменные окружения
```

---

## 3. Backend: приложения и ответственность

### Витрина (`frontend/web`)
SSR на React Router 8: страницы рендерятся на сервере и гидрируются в браузере (поисковики видят готовый HTML,
JSON-LD и OG-теги товара). Все обращения к Django — из `loader`/`action` на сервере витрины. JWT пользователя
хранятся в подписанной HttpOnly-cookie сессии витрины (схема BFF): JavaScript в браузере токенов не видит,
истёкший токен обновляется автоматически. Корзина гостя — по `cart_uuid` в сессии, после входа переходит к
пользователю (`GET /api/orders/cart/current/`). Формы работают и без JavaScript. Старые адреса SPA
(`/products/…`) отвечают 301 на новые (`/product/…`, `/catalog`).

### accounts
- `User` (логин по email), `Profile` (контакты, создаётся сигналом при создании пользователя;
  для анонимных заказов создаётся профиль без пользователя).
- Эндпоинты `/api/dj-rest-auth/`: `login/`, `logout/`, `user/`, `profile/`, `password/*`,
  `token/refresh/`, `registration/`.
- Вход разрешён только с подтверждённым email (`ACCOUNT_EMAIL_VERIFICATION=mandatory`).

### products
- `Category` → `Product` → `ProductVariant` (цена, скидка, штрихкод, код, остаток `stock`/`reserved`,
  себестоимость `cost_price`, ~20 атрибутов мебели/сантехники). `available=False` — вариант скрыт из каталога.
- `ProductVariant.save()` генерирует slug, код, штрихкод и картинку штрихкода, пересчитывает скидку.
- **Каталог показывает только товары, у которых есть видимый вариант**; цена в списке — минимальная среди
  видимых вариантов («от …»); в карточке — только видимые варианты, у каждого `in_stock` и `available_qty`.
- Сортировка `?ordering=price|-price|name|-name|new` (другие значения игнорируются), поиск `?search=` — по
  названию, артикулу и штрихкоду. Число SQL-запросов не зависит от количества товаров на странице.
- Эндпоинты: `/api/products/`, `/api/category/`, `/api/new_products/`, `/api/wishlist/`.

### orders
Модели: `Cart` (анонимная по `cart_uuid` или пользователя) → `CartItems`; `Order` → `OrderItem`
(снимок названия, артикула, цены и количества на момент оформления); `Order.stock_state` —
`none` (старые заказы) / `reserved` / `written_off` / `released`.

**Сервис `orders/services.py`:**
- `create_order_from_cart` — блокирует корзину (двойной клик не создаст второй заказ), фиксирует позиции
  и цены, **резервирует товар** (всё или ничего; при нехватке — `400 insufficient_stock`), уведомления
  отправляются после коммита;
- `change_status` — единая точка смены статуса (API отмены и Django admin):
  `canceled` → снять резерв; `delivered`/`completed` → списать со склада (`write_off_reserved`);
  отменить уже списанный заказ нельзя (нужен возврат);
- `cancel_by_customer` — клиент может отменить только свой заказ «в обработке» и до оплаты.

**Корзина:** `POST /api/orders/cart/` — «заменить содержимое» (клиент присылает корзину целиком; раньше
количества прибавлялись и росли при каждой синхронизации); `PUT/PATCH /cart/{id}/` — установить количества
(0 — удалить); позиция обязана иметь вариант (если у товара один вариант — подставляется сам);
в ответе по каждой позиции `price` выбранного варианта и `available` (доступно к заказу).

**Заказ:** `POST /api/orders/order-create/` — только по `cart_uuid` (поле `cart` с числовым id удалено —
по нему можно было оформить чужую корзину). Имя: буквы, пробел, дефис, апостроф. Телефон нормализуется к
`+380…`. История `GET /api/orders/history/` — только для авторизованных.

**Уведомления** (`orders/notifications.py`, `app/core/telegram.py`): письмо клиенту + сообщение менеджеру,
таймаут 5 с, экранирование HTML, round-robin менеджеров через счётчик в Redis.

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

**Приёмка накладной** (`services.py`) — три шага:
1. **Загрузка** (`POST inventory-documents/`): проверка расширения/размера, SHA-256 (тот же файл второй раз не
   загрузить), файл кладётся в приватное хранилище, сразу выполняется разбор. Каждая строка получает статус:
   `matched` (память сопоставлений / штрихкод / артикул), `needs_review` (найден только похожий по названию —
   fuzzy ≥ 80 %), `new` (будет создан скрытый товар), `invalid` (нет названия/количества/цены).
2. **Проверка**: `POST inventory-documents/{id}/lines/{n}/` с `{"variant": id}` или `{"create_new": true}`;
   подбор товара — `GET inventory-documents/variant-search/?q=…`.
3. **Проведение** (`POST …/process/`): запрещено, пока есть `needs_review` (или `accept_suggestions=true`) и если
   накладная с тем же номером этого поставщика уже проведена (или `allow_duplicate_number=true`). Одинаковые новые
   позиции в одной накладной создают один товар. Подтверждённые сопоставления запоминаются для поставщика —
   следующая накладная сопоставится автоматически. Отчёт: `{received, created, skipped}`.

Поставщик определяется по шапке накладной, если у `Supplier.code` указан код парсера (`aquadom`, `presto`, `santan`).

**Эндпоинты** (`/api/warehouse/`, доступ — суперпользователь или одобренный активный продавец, только свои склады):

| Метод и путь | Назначение |
|---|---|
| `GET/POST/PATCH warehouses/`, `GET warehouses/{id}/balances/` | склады и остатки |
| `GET/POST/... suppliers/` | поставщики (удаление = деактивация) |
| `GET stock-movements/`, `GET stock-movements/{id}/` | журнал (фильтры: тип, склад, вариант, документ) |
| `POST stock-movements/` | ручная операция `in/out/return_in/return_out` |
| `POST stock-movements/transfer/` · `return_supplier/` · `inventory/` | перемещение, возврат, инвентаризация |
| `GET/POST inventory-documents/` | накладные (xlsx/xls/xml/yml, ≤10 МБ) |
| `POST inventory-documents/{id}/parse/` | разобрать файл заново (например, после выбора поставщика) |
| `POST inventory-documents/{id}/lines/{n}/` | сопоставить строку: `{"variant": id}` / `{"create_new": true}` |
| `GET inventory-documents/variant-search/?q=` | подбор товара для строки |
| `POST inventory-documents/{id}/process/` | провести накладную → отчёт `{received, created, skipped}` |
| `GET inventory-documents/{id}/file/` | скачать исходный файл (накладные не раздаются через `/media/`) |
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
Тесты используют `config/settings_test.py` (locmem-кэш и почта, временный MEDIA) и не зависят от `.env`.
Линтер и форматер: `ruff check app config && ruff format app config` (также в pre-commit).

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

## 8. Запуск

**Production (Docker):**
```bash
cp .env.example .env            # заполнить SECRET_KEY, POSTGRES_*, DJANGO_ALLOWED_HOSTS, EMAIL_*, TOKEN_BOT…
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec app python app/manage.py createsuperuser
```
Сервисы: `db` (PostgreSQL 14, данные в `./data/db`), `redis`, `migrate` (одноразово: миграции + статика),
`app` (Django + gunicorn, healthcheck `/api/health/`), `frontend` (SSR-витрина, Node), `nginx` (порт
`HTTP_PORT`, по умолчанию 80: `/api`, `/admin`, `/account` → Django, остальное → витрина). Хосты БД/Redis задаёт
compose — в `.env` их менять не нужно. Обязательно задать `SESSION_SECRET` (`openssl rand -hex 32`);
без HTTPS — `INSECURE_COOKIES=true`, иначе браузер не вернёт cookie сессии.
TLS: терминировать перед `web` (Cloudflare / certbot / балансировщик), в `.env` — `TRUSTED_PROXY=True`.

**Существующая БД** (`./data/db` с прошлых версий) — перед первым запуском сделать бэкап и пометить миграцию:
```bash
docker compose -f docker-compose.prod.yml run --rm migrate python app/manage.py migrate products 0014 --fake
```

**Локальная разработка:** `docker compose -f docker-compose.dev.yml up -d` (БД и Redis), в `.env`:
`DEBUG=True`, `POSTGRES_HOST=localhost`, `REDIS_URL=redis://localhost:6379/1`; затем
`python app/manage.py migrate && python app/manage.py runserver`; витрина — `cd frontend/web && npm install &&
npm run dev` (http://localhost:3000, ходит в Django на :8000). Переключать «dev/боевой» правкой кода не нужно —
всё задаётся переменными окружения.

---

## 9. Журнал изменений

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

### 2026-10-08 — Шаг 2: заказы и корзина
**Было:** заказ не проверял и не резервировал остаток, отмена/выдача не влияли на склад; позиций заказа не было —
история показывала текущие цены; позиции без варианта стоили 0 ₴; корзина при каждой синхронизации
прибавляла количества (сумма заказа росла); через поле `cart` можно было оформить чужую корзину;
аноним не мог открыть свою корзину (UUID сравнивался со строкой); `/history/` для анонима падал с 500;
двойной клик создавал два заказа; письмо и Telegram отправлялись синхронно без таймаутов, round-robin
менеджеров жил в памяти процесса; на каждый гостевой заказ создавался пустой `Profile`;
имена с апострофом/дефисом отклонялись.

**Стало:** см. раздел «orders». Миграции: `orders/0009` (OrderItem, stock_state, индексы),
`orders/0010` (позиции для старых заказов по текущим ценам — исторических цен не было; итог заказа не меняется).
Удалён `orders/utils.py` (валидаторы → `orders/validators.py`, письма → `orders/notifications.py`).
Callback: общий модуль Telegram, chat_id менеджера больше не отдаётся клиенту.

**API-изменения:** ответ `POST /cart/` всегда содержит корзину целиком; поле `cart` в оформлении заказа
игнорируется; `list_of_products` в деталях заказа берётся из `OrderItem`; тексты ошибок валидации на русском.

Тесты: 84 (+12 сценариев заказа, включая параллельный двойной сабмит).

### 2026-10-15 — Инфраструктура, каталог, парсеры, чистка
**Инфраструктура.** Prerender убран (каталога сервиса не было в репозитории, compose падал). Compose переписан:
healthchecks (у Postgres — по TCP, иначе при первой инициализации «здоров» раньше времени), одноразовый
`migrate`, nginx-образ со сборкой SPA, `/api/health/`, удалён неиспользуемый pgbouncer с открытым портом.
Dockerfile — Python 3.12, non-root, gunicorn.conf.py. Стек проверен с нуля: все миграции применяются,
`/`, `/api/…`, `/admin/`, статика отвечают. Старый SPA: база API — тот же домен (было `/api/api/…`).
Ручные dev-заглушки в settings (`DEBUG=True` по умолчанию, `localhost`, `postgres:postgres`) не нужны —
см. §8; сами правки сохранены в `docs/archive/2026-10-15-user-wip.patch`.

**Каталог.** Только видимые товары/варианты, цена «от», наличие, белый список сортировки, поиск по артикулу,
без кэширования целых queryset в Redis, без N+1.

**Парсеры и приёмка.** Числа (`1 234,50`, NBSP, валюта), колонка «№» больше не артикул, название/артикул/
штрихкод — из своих колонок, дробные количества (0.5 м) не теряются, регистр названий сохраняется, YML-прайс не
приходуется, `defusedxml`. Приёмка: разбор → проверка fuzzy-совпадений → проведение; SHA-256 от повторной
загрузки; защита от повторного номера накладной; файлы накладных — в приватном хранилище (миграция переносит
существующие). Новый товар, встречающийся в накладной дважды, создаётся один раз.

**Продавцы.** Регистрация продавца работает (ждёт одобрения), комиссию меняет только админ, удаление через
API запрещено.

**Чистка.** ruff (линт + формат) вместо невалидного flake8; удалены закомментированный код, `print`, `import *`,
дубли (~550 строк в команде импорта); приложение `telemetry` и GeoIP (78 МБ) — в архиве (тег `archive/telemetry`).

Тесты: 116.

### 2026-10-17 — Новая витрина, безопасность паролей
**Безопасность.** Регистрация сохраняла пароль **открытым текстом** в `Profile.password`, а админка показывала его
в списке. Поле удалено (миграция `accounts/0006` дропает колонку вместе с сохранёнными паролями), добавлен
регрессионный тест. Белый список почтовых доменов при регистрации дополнен украинскими сервисами (ukr.net, i.ua,
meta.ua, bigmir.net…), которые раньше отклонялись.

**Витрина v2** (`frontend/web`) вместо старого SPA (CRA): SSR, TypeScript, Tailwind 4, BFF-авторизация, все
сценарии покупки и кабинета (см. раздел «Витрина»). Проверено вживую против Django: гость — каталог по
категории → товар → корзина → оформление (резерв 2 шт., остаток на сайте 5 → 3); пользователь — вход, профиль,
избранное, заказ, отмена (резерв снят), выход; 404 и 301 со старых адресов. Тесты витрины: 20, типы и ESLint чистые.
Старый SPA — в архиве (тег `archive/frontend-cra`).

**Docker.** Вместо `web` (nginx + CRA) — `frontend` (Node SSR) + `nginx` (`deploy/nginx/default.conf`).
⚠️ Сборка образов не прогнана: Docker-демон на машине разработки завис; compose проверен (`docker compose config`).

**Каталог.** Кириллические категории получали пустой slug (`slugify` без транслитерации) — ссылки
`?category=` не работали. Общий хелпер `make_slug`, data-миграция `products/0016`.

**API.** `GET /api/orders/cart/current/` — текущая корзина (гостевая переходит к пользователю после входа).

Тесты: backend 119, frontend 20.
