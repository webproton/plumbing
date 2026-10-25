# Карта проекта

Что где лежит, за что отвечает, какие ключевые функции, что удалено и что ушло в архив.
Устройство и бизнес-правила подробнее — в [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md), план — в [ROADMAP.md](ROADMAP.md).

> Обновлено: 2026-10-18 · ветка `refactor/production-readiness`

---

## 1. Корень репозитория

| Путь | Назначение |
|---|---|
| `config/settings.py` | Все настройки из env (`.env`), безопасные prod-дефолты |
| `config/settings_test.py` | Настройки тестов (locmem-кэш, почта в памяти, временный MEDIA) |
| `config/urls.py` | Маршруты: всё API под `/api/`, `/admin/`, `/account/` (allauth) |
| `Dockerfile` | Образ бэкенда: Python 3.12 slim, wheels в отдельной стадии, non-root, gunicorn |
| `gunicorn.conf.py` | Воркеры/таймауты gunicorn (через env) |
| `docker-compose.prod.yml` | Prod: `db`, `redis`, `migrate` (миграции+статика), `app` (Django), `worker` + `beat` (Celery), `frontend` (SSR), `nginx` |
| `config/celery.py` | Приложение Celery (`celery -A config worker` / `beat`), задачи ищутся в `tasks.py` приложений |
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
| `http.py` | `fetch` / `check_url` — загрузка по пользовательским ссылкам с защитой от SSRF, проверкой редиректов и лимитом размера |
| `crypto.py` | `encrypt` / `decrypt` — шифрование секретов в БД (Fernet, `CREDENTIALS_KEY`) |
| `tasks.py` | `enqueue` — постановка задачи Celery; при недоступном Redis — выполнить сразу или `QueueUnavailable` |
| `pagination.py` | `StandardPagination` (`?page=`, `?page_size=` ≤ 100) |

### 2.2 `app/apps/products/` — каталог

| Файл | Что внутри |
|---|---|
| `utils/slugs.py` | `make_slug` / `unique_slug` — латинский slug из кириллицы (рус./укр.) |
| `models.py` | `Category`, `Product`, `ProductVariant` (цена, скидка, код, штрихкод, **`stock`/`reserved` Decimal**, `available_stock`, себестоимость), `Wishlist`, `ProductPhoto`, ~20 справочников атрибутов |
| `views.py` | `catalog_queryset()` — только товары с видимыми вариантами + `min_price`; `ProductListView` (список/карточка, сортировка `price/-price/name/-name/new`), `CategoryList`, `NewProducts`, `WishlistViewSet` |
| `serializers.py` | `ProductListSerializer` (цена «от», первый видимый вариант), `ProductDetailSerializer` (только видимые варианты), `ProductVariantSerializer` (+`in_stock`, `available_qty`), `WishlistSerializer` |
| `manage.py` | Редактор кабинета `/api/manage/products|variants|brands`: список со сводкой, CRUD, варианты, фото, массовые действия |
| `services.py` | `discount_fields` (цена + старая цена → скидка), `editable_products` / `editable_variants` (права), `brand_by_name` |
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
| `models.py` | `Cart`, `CartItems`, `Order` (+`stock_state`, `language`), `OrderItem` (снимок названия/артикула/цены), `CustomerNotification` (журнал писем покупателю, ключ события уникален в заказе) |
| `services.py` | `create_order_from_cart` (блокировка корзины, резерв, позиции), `change_status` (отмена → снять резерв; доставлен/завершён → списать), `cancel_by_customer` |
| `serializers.py` | Корзина «заменить содержимое» (`CartCreateSerializer`), «установить количества» (`CartDetailSerializer`), оформление `OrderCreateSerializer` (только по `cart_uuid`), список/детали заказа |
| `notifications.py` | Новый заказ: письмо покупателю (через `customer_notifications`) и сообщение менеджеру в Telegram |
| `customer_notifications.py` | Письма покупателю (uk/ru): `schedule` (после коммита, в фоне), `notify` (событие — один раз), `resend`; тексты `TEXTS` |
| `templates/orders/email/customer.{txt,html}` | Письмо покупателю: текст и HTML |
| `tasks.py` | `notify_order_created_task`, `notify_customer_task` — уведомления в фоне |
| `manage.py` | Заказы в кабинете `/api/orders/manage/`: список, карточка, статус, оплата, заметка, менеджер, счётчики, ТТН, счёт PDF и email, журнал писем покупателю (`notifications/{id}/resend/`) |
| `invoice.py` | Счёт на оплату PDF, `amount_in_words` (сумма прописью по-украински) |
| `validators.py` | `validate_phone_number` (+380…), `validate_person_name` (буквы, пробел, дефис, апостроф) |
| `permissions.py` | `IsCartOwnerOrAnonWithUUID` |
| `views.py`, `admin.py` | API и админка; смена статуса в админке идёт через `services.change_status` |

API: `/api/orders/cart/` (+`by-uuid/`), `/api/orders/order-create/`, `/api/orders/history/` (+`{id}/cancel/`).

### 2.4 `app/apps/warehouse/` — склад

| Файл | Что внутри |
|---|---|
| `models.py` | `Warehouse`, `Supplier` (+`code` для автоопределения), `StockMovement` (неизменяемый журнал), `StockBalance` (остаток по складу), `InventoryDocument` (накладная, приватный файл, SHA-256, ручные колонки `column_map`, ИИ-разбор `ai_status/ai_result`), `InvoiceColumnProfile` (запомненные раскладки колонок поставщика), `ProductBarcode`, `VariantMatchMemory`, `CurrencyRate` |
| `stock.py` | **Единственное место изменения остатков**: `receive`, `write_off`, `return_to_supplier`, `transfer`, `adjust`, `reserve`, `release`, `write_off_reserved`, `rebuild_from_journal`, `reverse_receipts` (сторно), `get_balance`, `journal_balance` |
| `duplicates.py` | Поиск дублей накладной: `number_key`, `line_keys`/`fingerprint`/`lines_total`, `find_duplicates` (номер / строки / похожие) |
| `services.py` | Приёмка накладной: `parse_document` (через `parsers.pipeline`) → `set_line_variant` → `process_inventory_document` (дубли, вычет принятого сканером) → `reverse_inventory_document` (сторно); `set_document_columns` / `reset_document_columns` (ручные колонки, профили), `request_ai_parse`; `VariantMatcher` (память → штрихкод → артикул → fuzzy; устойчив к «двойникам» букв); `suggest_variants` |
| `inventory/barcode_scanner.py` | `find_variant_by_code`, `scan_barcode` (пик = +1 шт. по документу) |
| `pdf.py` | PDF накладной в памяти |
| `labels.py` | PDF этикеток (58×40 / A4 3×8), EAN-13 или Code128 |
| `tasks.py` | `parse_document_ai_task` — разбор накладной через ИИ в фоне |
| `permissions.py` | `get_active_seller`, `IsWarehouseStaff` (одобренный продавец / суперпользователь, только свои объекты) |
| `views.py`, `serializers.py`, `admin.py` | API склада, сканер, админка (журнал — только чтение, «Провести», «Сверить остатки») |
| `templates/warehouse/scanner_mock.html` | Тестовая страница сканера (только staff) |
| `management/commands/seed_demo.py` | Демо-данные для ручной проверки: приход остатков от «Демо-постачальника» по товарам без остатка, пустой каталог — 10 демо-вариантов сантехники; при `DEBUG=False` только с `--force` |

API (`/api/warehouse/`): `me/`, `dashboard/`, `balances/`, `variants/search/`, `warehouses/` (+`{id}/balances/`), `suppliers/`, `stock-movements/` (+`transfer/`, `return_supplier/`, `inventory/`, `summary/`), `inventory-documents/` (+`{id}/parse/`, `{id}/lines/{n}/`, `{id}/process/`, `{id}/scan/`, `{id}/print/`, `{id}/file/`, `variant-search/`), сканер: `stock-movements/find_by_barcode_or_sku/`, `stock-movements/create_and_add/`.

### 2.5 `app/parsers/` — парсеры накладных

| Файл | Что внутри |
|---|---|
| `core/loader.py` | `load_rows`: xlsx/xls (openpyxl → pandas/calamine), XML Spreadsheet, YML-прайс (без количеств), PDF (pdfplumber: таблицы с линиями и по выравниванию текста); фото/скан → `NeedsAI`; XML через `defusedxml` |
| `core/text_utils.py` | `row_text`, `normalize_text`, `fold_lookalikes` (латинская i → і в словах с кириллицей), `code_key` (кириллические С/Т/Н → латиница в артикулах) |
| `pipeline.py` | **Точка входа склада**: ручные колонки → основной парсер → проверка → профили / разбор по содержимому / ИИ, выбор лучшего |
| `quality.py` | `assess`: кол-во × цена = сумма, сумма строк = итог (± ПДВ) → `ok / warning / bad / empty` |
| `universal.py` | Разбор по содержимому колонок (`detect_columns`, `extract_items`) — без доверия к заголовкам |
| `ai.py` | Разбор через Claude: таблица текстом или PDF/фото, ответ по схеме `record_invoice` |
| `regress.py` | Эталон: `snapshot` / `compare` реальных файлов, `record` обезличенных кейсов тестов |
| `core/numbers.py` | `safe_float` (1 234,50 · 1.234,50 · NBSP · валюта; текст — не число) |
| `core/table_engine.py` | `TableEngine`: поиск заголовка, разбор строк по колонкам (позиция/артикул/штрихкод/название/кол-во/цена/сумма) |
| `detect.py` | `detect_supplier` — код поставщика по ключевым словам шапки |
| `registry.py` | `parse(rows)` — выбор парсера поставщика и нормализация (основной парсер внутри `pipeline`) |
| `normalizer.py` | Приведение строки к единому виду (регистр названия сохраняется) |
| `suppliers/` | `default`, `aquadom`, `presto`, `santan` (`ber` — не подключён) |
| `run.py` | Отладка из консоли: `python -m parsers.run файл.xlsx` |

### 2.6 `app/apps/imports/` — импорт товаров

| Файл | Что внутри |
|---|---|
| `models.py` | `ImportSource` (источник, зашифрованный `secret`), `SupplierItem` (каталог поставщика), `ImportRun` (запуск, строки предпросмотра) |
| `fields.py` | Синонимы колонок/тегов (`FIELD_SYNONYMS`), `detect_columns`, разбор чисел, количеств («>10»), да/нет, ссылок на фото |
| `formats.py` | `parse_items`: YML, XML (тег товара определяется сам), CSV (кодировка/разделитель), Excel (строка заголовков среди первых 30), JSON (путь к списку, вложенные поля) → `SourceItem` |
| `connectors/` | `feed.py` (ссылка/файл), `api.py` (JSON, страницы), `web.py` (`SiteAdapter`, `@register`, `FormLoginAdapter`, `WebConnector`), `base.py` (авторизация запросов) |
| `services.py` | `sync_source`, `upsert_items`, `auto_link`, `apply_updates`, `Pricing` (РРЦ / наценка, курс, округление), `link_item`, `publish_items`, `set_status`, `editable_variants` |
| `template.py` | Шаблон: `build_template`, `read_rows`, `plan` (создать/обновить/ошибка), `apply` (группы → варианты, остатки инвентаризацией) |
| `photos.py` | Загрузка фото товара по ссылкам (проверка Pillow, только если у товара нет фото) |
| `tasks.py` | Celery: `sync_source_task` (с блокировкой), `sync_due_sources` (beat), `apply_template_task`, `download_photos_task` |
| `permissions.py` | `IsImportStaff` — продавец работает только со своими источниками и загрузками |
| `views.py`, `serializers.py`, `urls.py`, `admin.py` | API `/api/imports/`, админка (секреты не показываются) |

### 2.7 `app/apps/delivery/` — Новая Почта

| Файл | Что внутри |
|---|---|
| `novaposhta.py` | Клиент API: `search_cities`, `warehouses`, `estimate`, `track`, `create_document` (+ отправитель из кабинета НП, получатель), кэш справочников |
| `services.py` | `set_ttn`, `create_ttn`, `refresh_statuses` (отримано → «Доставлен»), `orders_to_track` |
| `views.py`, `urls.py` | Публичный справочник `/api/delivery/np/cities|warehouses|estimate/` |
| `tasks.py` | Celery beat: `delivery.refresh_ttn_statuses` |

### 2.8 `app/apps/marketing/` — фиды, пиксели, Telegram

| Файл | Что внутри |
|---|---|
| `feeds.py` | `offers()` и форматы `yml("prom"|"rozetka")`, `google()` |
| `telegram.py` | `caption`, `post_product` (sendPhoto / sendMessage) |
| `services.py` | `ensure_feeds_token`, `publish`, `announce` (автопубликация новинок) |
| `views.py`, `urls.py` | `/api/feeds/<секрет>/<файл>`, `/api/marketing/telegram/products/<id>/`, `/api/seo/sitemap/` |
| `seo.py` | Данные для sitemap.xml: видимые товары (до 45 000) и непустые категории, кэш 15 минут |
| `validators.py` | Строгий формат ID пикселей и канала Telegram |
| `models.py`, `tasks.py` | `TelegramPost`; задача `marketing.announce_product` |

### 2.9 Остальные приложения

| Приложение | Что внутри |
|---|---|
| `accounts` | `User` (вход по email), `Profile`, регистрация/логин (dj-rest-auth), `/api/dj-rest-auth/…` |
| `sellers` | `Seller` (комиссия — только админ, удаление через API запрещено), `Shop`, `/api/sellers/…` |
| `callback` | «Перезвоните мне» → Telegram, настройки сайта и магазина (`SiteSettings`: контакты, реквизиты, отправитель НП), `/api/callback/…` |

---

## 3. Frontend — `frontend/web/` (v2)

React Router 8 (SSR) · React 19 · TypeScript strict · Tailwind CSS 4 · zod · Vitest. Подробности — `frontend/web/README.md`.

| Путь | Назначение |
|---|---|
| `app/root.tsx` | Каркас документа, корневой middleware сессии, общий loader (пользователь, счётчик корзины, категории, контакты), страница ошибки |
| `app/routes.ts` | Карта маршрутов (включая 301 со старых адресов SPA) |
| `app/lib/api.server.ts` | `Api` — клиент Django: Bearer-токен, авто-refresh, откат к гостю, `X-Real-IP`, `ApiError.fieldErrors`; `download()` для PDF/файлов — ошибка бэкенда уходит пользователю с его статусом |
| `app/lib/session.server.ts` | Подписанная HttpOnly-cookie сессия: токены, корзина гостя, пользователь |
| `app/lib/context.server.ts` | `sessionMiddleware`: сессия и API в `context`, запись cookie при изменении |
| `app/lib/cart.server.ts` | `getCart` / `saveCart` (корзина целиком), итоги |
| `app/lib/auth.server.ts` | `requireUser` (редирект на вход с возвратом), `safeNext` |
| `app/lib/validation.ts` | zod-схемы форм, `normalizePhone` (+380…) |
| `app/lib/analytics.ts` | `trackEvent` (GA4/GTM, Meta, TikTok), `trackPageView`, строгий формат ID |
| `app/lib/format.ts` | Цены (₴), количества, даты, склонения, цвет статуса заказа |
| `app/lib/types.ts` | Типы ответов API |
| `app/lib/seo.ts` | SEO: `robotsFor` (noindex), `canonicalSearch`, `robotsTxt`, `buildSitemap` (uk/ru, hreflang, фото), разметка `shopJsonLd`, `breadcrumbJsonLd`, `plainText` |
| `app/routes/seo/robots.ts`, `app/routes/seo/sitemap.ts` | Ресурсные маршруты `/robots.txt` и `/sitemap.xml` (в корне, без языкового префикса) |
| `app/components/` | `Analytics` (скрипты пикселей, просмотры страниц), `NpPicker` (город и отделение Новой Почты с автодополнением), UI-кит (`ui.tsx`), шапка, подвал, карточка товара, цена, пагинация, количество, «в корзину», заявка на звонок |
| `app/routes/` | Страницы: главная, каталог, товар, корзина, оформление (Новая Почта), ресурсные `np/*` (справочник НП), `account/order-invoice` (счёт), вход/регистрация/пароль, кабинет, избранное, доставка, контакты |
| `app/routes/seller/` | Кабинет склада/продавца: `layout` (роль, навигация), `index` (обзор), `products` + `product-new` + `product-edit` (товары), `orders` + `order` + `order-invoice` (заказы, ТТН, счёт), `labels` (PDF этикеток), `settings` (настройки магазина), `stock`, `documents` + `document` (накладные, «Перевірка розбору», ИИ) + `document-columns` (ручной выбор колонок), `operations`, `scanner`, `movements`, `warehouses`, `suppliers`, импорт — `import` (шаблон, загрузка, история), `import-run` (предпросмотр/применение), `sources` (источники), `source` (позиции поставщика), `source-edit` (создание/настройки); ресурсные маршруты `variants` (поиск товара), `document-file`, `import-template` (скачивание) |
| `app/components/seller/` | `Table` (таблицы, карточки-метрики), `VariantPicker` (поиск товара), `CameraScanner` (камера телефона), `imports.tsx` (статусы запусков/источников, `usePolling` — автообновление во время фоновой задачи), `VariantFields` (поля варианта товара) |
| `app/i18n/` | Словари: `uk.ts` (еталон), `ru.ts`, кабинет — `seller.uk.ts`/`seller.ru.ts`, импорт — `import.uk.ts`/`import.ru.ts`, товары и заказы — `cabinet.uk.ts`/`cabinet.ru.ts`; `react.tsx` (useT, Link с языком), `server.ts` |
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
