# Карта проекта

Что где лежит, за что отвечает, какие ключевые функции, что удалено и что ушло в архив.
Устройство и бизнес-правила подробнее — в [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md), план — в [ROADMAP.md](ROADMAP.md).

> Обновлено: 2026-10-17 · ветка `refactor/production-readiness`

---

## 1. Корень репозитория

| Путь | Назначение |
|---|---|
| `config/settings.py` | Все настройки из env (`.env`), безопасные prod-дефолты |
| `config/settings_test.py` | Настройки тестов (locmem-кэш, почта в памяти, временный MEDIA) |
| `config/urls.py` | Маршруты: всё API под `/api/`, `/admin/`, `/account/` (allauth) |
| `Dockerfile` | Образ бэкенда: Python 3.12 slim, wheels в отдельной стадии, non-root, gunicorn |
| `gunicorn.conf.py` | Воркеры/таймауты gunicorn (через env) |
| `docker-compose.prod.yml` | Prod: `db`, `redis`, `migrate` (миграции+статика), `app` (Django), `frontend` (SSR), `nginx` |
| `deploy/nginx/default.conf` | Маршрутизация nginx между Django и SSR-фронтендом |
| `docker-compose.dev.yml` | Dev: только `db` и `redis` на localhost |
| `.dockerignore` | Что не попадает в образ (frontend, data, media, .env, …) |
| `requirements.txt` / `requirements-dev.txt` | Runtime / тесты и линтер |
| `pyproject.toml` | Настройки ruff (линтер + форматер) |
| `.pre-commit-config.yaml` | Хуки: ruff, ruff-format, поиск приватных ключей |
| `pytest.ini`, `conftest.py` | Тесты (`pytest` из корня) |
| `.env.example` | Все переменные окружения с пояснениями |
| `docs/` | Документация; `docs/archive/` — сохранённые патчи и материалы |

---

## 2. Backend — `app/`

### 2.1 `app/core/` — общий код

| Файл | Что внутри |
|---|---|
| `middleware.py` | `RealIPMiddleware` — реальный IP клиента из `X-Real-IP` за nginx (`TRUSTED_PROXY=True`) |
| `exceptions.py` | `api_exception_handler` — `StockError` и django `ValidationError` → `400 {"detail","code"}` |
| `telegram.py` | `send_message` (таймаут 5 с), `esc` (экранирование HTML), `next_manager_chat_id` (round-robin в Redis) |
| `storage.py` | `private_storage` — хранилище файлов вне публичного `/media/` (накладные) |
| `views.py` | `health` — `GET /api/health/`: проверка БД и кэша (healthcheck docker) |

### 2.2 `app/apps/products/` — каталог

| Файл | Что внутри |
|---|---|
| `utils/slugs.py` | `make_slug` / `unique_slug` — латинский slug из кириллицы (рус./укр.) |
| `models.py` | `Category`, `Product`, `ProductVariant` (цена, скидка, код, штрихкод, **`stock`/`reserved` Decimal**, `available_stock`, себестоимость), `Wishlist`, `ProductPhoto`, ~20 справочников атрибутов |
| `views.py` | `catalog_queryset()` — только товары с видимыми вариантами + `min_price`; `ProductListView` (список/карточка, сортировка `price/-price/name/-name/new`), `CategoryList`, `NewProducts`, `WishlistViewSet` |
| `serializers.py` | `ProductListSerializer` (цена «от», первый видимый вариант), `ProductDetailSerializer` (только видимые варианты), `ProductVariantSerializer` (+`in_stock`, `available_qty`), `WishlistSerializer` |
| `filters.py` | `ProductFilters`: категория (slug), цена, габариты, атрибуты, `search` (название, артикул, штрихкод) |
| `admin.py`, `actions.py` | Админка каталога, массовая скидка, генерация баннеров, подбор цвета по фото |
| `utils/color_utils.py` | Определение цвета по фото (k-means, ColorThief), парсинг размеров/булевых значений |
| `utils/banner_generator.py` | Генерация баннеров товаров |
| `management/commands/import_products.py` | Импорт каталога из папок с фото/описаниями (общие функции — из `color_utils`) |
| `management/commands/load_catalog_products.py` | Загрузка каталога из структуры папок |
| `management/commands/fix_product_slugs.py` | Пересоздание slug'ов |

API: `/api/products/`, `/api/products/{slug}/`, `/api/category/`, `/api/new_products/`, `/api/wishlist/` (+`bulk-update/`, `merge/`, `clear/`).

### 2.3 `app/apps/orders/` — корзина и заказы

| Файл | Что внутри |
|---|---|
| `models.py` | `Cart`, `CartItems`, `Order` (+`stock_state`), `OrderItem` (снимок названия/артикула/цены) |
| `services.py` | `create_order_from_cart` (блокировка корзины, резерв, позиции), `change_status` (отмена → снять резерв; доставлен/завершён → списать), `cancel_by_customer` |
| `serializers.py` | Корзина «заменить содержимое» (`CartCreateSerializer`), «установить количества» (`CartDetailSerializer`), оформление `OrderCreateSerializer` (только по `cart_uuid`), список/детали заказа |
| `notifications.py` | Письмо клиенту и сообщение менеджеру в Telegram после коммита |
| `validators.py` | `validate_phone_number` (+380…), `validate_person_name` (буквы, пробел, дефис, апостроф) |
| `permissions.py` | `IsCartOwnerOrAnonWithUUID` |
| `views.py`, `admin.py` | API и админка; смена статуса в админке идёт через `services.change_status` |

API: `/api/orders/cart/` (+`by-uuid/`), `/api/orders/order-create/`, `/api/orders/history/` (+`{id}/cancel/`).

### 2.4 `app/apps/warehouse/` — склад

| Файл | Что внутри |
|---|---|
| `models.py` | `Warehouse`, `Supplier` (+`code` для автоопределения), `StockMovement` (неизменяемый журнал), `StockBalance` (остаток по складу), `InventoryDocument` (накладная, приватный файл, SHA-256), `ProductBarcode`, `VariantMatchMemory`, `CurrencyRate` |
| `stock.py` | **Единственное место изменения остатков**: `receive`, `write_off`, `return_to_supplier`, `transfer`, `adjust`, `reserve`, `release`, `write_off_reserved`, `rebuild_from_journal`, `get_balance`, `journal_balance` |
| `services.py` | Приёмка накладной: `parse_document` → `set_line_variant` → `process_inventory_document`; `VariantMatcher` (память → штрихкод → артикул → fuzzy-подсказка); `suggest_variants` |
| `inventory/barcode_scanner.py` | `find_variant_by_code`, `scan_barcode` (пик = +1 шт. по документу) |
| `pdf.py` | PDF накладной в памяти |
| `permissions.py` | `get_active_seller`, `IsWarehouseStaff` (одобренный продавец / суперпользователь, только свои объекты) |
| `views.py`, `serializers.py`, `admin.py` | API склада, сканер, админка (журнал — только чтение, «Провести», «Сверить остатки») |
| `templates/warehouse/scanner_mock.html` | Тестовая страница сканера (только staff) |

API (`/api/warehouse/`): `warehouses/` (+`{id}/balances/`), `suppliers/`, `stock-movements/` (+`transfer/`, `return_supplier/`, `inventory/`, `summary/`), `inventory-documents/` (+`{id}/parse/`, `{id}/lines/{n}/`, `{id}/process/`, `{id}/scan/`, `{id}/print/`, `{id}/file/`, `variant-search/`), сканер: `stock-movements/find_by_barcode_or_sku/`, `stock-movements/create_and_add/`.

### 2.5 `app/parsers/` — парсеры накладных

| Файл | Что внутри |
|---|---|
| `core/loader.py` | `load_rows`: xlsx/xls (openpyxl → pandas/calamine), XML Spreadsheet, YML-прайс (без количеств); XML через `defusedxml` |
| `core/numbers.py` | `safe_float` (1 234,50 · 1.234,50 · NBSP · валюта; текст — не число) |
| `core/table_engine.py` | `TableEngine`: поиск заголовка, разбор строк по колонкам (позиция/артикул/штрихкод/название/кол-во/цена/сумма) |
| `detect.py` | `detect_supplier` — код поставщика по ключевым словам шапки |
| `registry.py` | `parse(rows)` — выбор парсера и нормализация |
| `normalizer.py` | Приведение строки к единому виду (регистр названия сохраняется) |
| `suppliers/` | `default`, `aquadom`, `presto`, `santan` (`ber` — не подключён) |
| `run.py` | Отладка из консоли: `python -m parsers.run файл.xlsx` |

### 2.6 Остальные приложения

| Приложение | Что внутри |
|---|---|
| `accounts` | `User` (вход по email), `Profile`, регистрация/логин (dj-rest-auth), `/api/dj-rest-auth/…` |
| `sellers` | `Seller` (комиссия — только админ, удаление через API запрещено), `Shop`, `/api/sellers/…` |
| `callback` | «Перезвоните мне» → Telegram, настройки сайта, `/api/callback/…` |

---

## 3. Frontend — `frontend/web/` (v2)

React Router 8 (SSR) · React 19 · TypeScript strict · Tailwind CSS 4 · zod · Vitest. Подробности — `frontend/web/README.md`.

| Путь | Назначение |
|---|---|
| `app/root.tsx` | Каркас документа, корневой middleware сессии, общий loader (пользователь, счётчик корзины, категории, контакты), страница ошибки |
| `app/routes.ts` | Карта маршрутов (включая 301 со старых адресов SPA) |
| `app/lib/api.server.ts` | `Api` — клиент Django: Bearer-токен, авто-refresh, откат к гостю, `X-Real-IP`, `ApiError.fieldErrors` |
| `app/lib/session.server.ts` | Подписанная HttpOnly-cookie сессия: токены, корзина гостя, пользователь |
| `app/lib/context.server.ts` | `sessionMiddleware`: сессия и API в `context`, запись cookie при изменении |
| `app/lib/cart.server.ts` | `getCart` / `saveCart` (корзина целиком), итоги |
| `app/lib/auth.server.ts` | `requireUser` (редирект на вход с возвратом), `safeNext` |
| `app/lib/validation.ts` | zod-схемы форм, `normalizePhone` (+380…) |
| `app/lib/format.ts` | Цены (₴), количества, даты, склонения, цвет статуса заказа |
| `app/lib/types.ts` | Типы ответов API |
| `app/components/` | UI-кит (`ui.tsx`), шапка, подвал, карточка товара, цена, пагинация, количество, «в корзину», заявка на звонок |
| `app/routes/` | Страницы: главная, каталог, товар, корзина, оформление, вход/регистрация/пароль, кабинет, избранное, доставка, контакты |
| `tests/` | Vitest: форматирование, валидация, API-клиент, компоненты |
| `Dockerfile` | Node 24 alpine, SSR-сервер `react-router-serve` на :3000 |

`deploy/nginx/default.conf` — nginx перед магазином: `/api`, `/admin`, `/account` → Django; `/django-static/`, `/media/` —
файлы; остальное → SSR-фронтенд.

## 4. Удалено (и почему)

Восстановить любой файл: `git show <коммит>^:<путь> > <путь>`.

| Что | Коммит | Причина |
|---|---|---|
| `warehouse/views copy.py`, `admin copy.py`, `scanner_mock copy*.html` | `a340bfe` | Копии файлов |
| `warehouse/parsers.py`, `parsersb.py` | `a340bfe` | Старые парсеры, заменены `app/parsers`, нигде не импортировались |
| Команды `etalon`, `get_col_norm`, `import_products_backup`, `import_products_origin` | `a340bfe` | Старые версии `import_products` |
| `app/plumbing/`, `app/plumbing.conf`, `.DS_Store` | `a340bfe` | Пустой пакет, неиспользуемый конфиг nginx |
| `frontend/plumbreact/key.pem`, `cert.pem` | `a340bfe` | Приватный ключ в git (сертификат истёк 29.09.2026) — **перевыпустить** |
| `warehouse/signals.py` | `5d076c1` | Пересчёт остатка сигналом давал двойной счёт |
| `warehouse/tests.py` | `5d076c1` | Пустой, заменён `warehouse/tests/` |
| `orders/utils.py` | `7baae29` | Разнесён в `validators.py` и `notifications.py` |
| Сервис `prerender`, `pgbouncer` в compose | `634af70` | Каталога prerender не было в репозитории; к pgbouncer Django не подключался |
| `products/paginations.py`, `products/signals.py`, `BrandList`, `ProductSetLikesSerializer` | `90f8e2d` | Не использовались / ссылались на несуществующие поля |
| Дубли функций в `import_products.py` (~550 строк) | `9c5c8f7` | Идентичные копии `utils/color_utils.py` |
| `.flake8`, `.pylintrc` | `9c5c8f7` | Заменены ruff (конфиг flake8 был невалиден) |
| `Profile.password` (миграция `accounts/0006`) | `26a93ce` | Хранил пароль открытым текстом и показывал его в админке |
| `frontend/plumbreact` (старый SPA) | после `595d25d` | Заменён `frontend/web`; в архиве (тег `archive/frontend-cra`) |
| `products/permission.py`, `sellers/tests.py` | `9aa1934` | Не использовались / пустой |
| Закомментированный код, отладочные `print` | разные | Мусор |

---

## 5. Архив

| Что | Где | Как восстановить |
|---|---|---|
| Приложение `telemetry` (антифрод/телеметрия) + базы GeoIP (78 МБ) | git-тег `archive/telemetry` | `git checkout archive/telemetry -- app/apps/telemetry app/geoip`, вернуть в `INSTALLED_APPS`, `geoip2` и `device-detector` в requirements. Перед этим исправить синтаксическую ошибку в `telemetry/serializers.py` (строка заметки в конце файла) |
| Старый SPA `frontend/plumbreact` (CRA, JS, class-компоненты) | git-тег `archive/frontend-cra` | `git checkout archive/frontend-cra -- frontend/plumbreact` |
| Незакоммиченные правки 2026-10-15 (settings/urls/docker/nginx до переделки) | `docs/archive/2026-10-15-user-wip.patch` | `git apply docs/archive/2026-10-15-user-wip.patch` (на соответствующую ревизию) |
