# Витрина магазина (frontend v2)

React Router 8 (framework mode, SSR) · React 19 · TypeScript strict · Tailwind CSS 4 · zod · Vitest.

## Запуск для разработки
```bash
cp .env.example .env          # API_INTERNAL_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:3000 (Django должен работать на :8000)
```

## Проверки
```bash
npm run check                 # типы (react-router typegen + tsc), ESLint, тесты
npm run build && npm start    # production-сборка и SSR-сервер
```

## Как устроено
- **SSR**: каждая страница рендерится на сервере (SEO без prerender), затем гидрируется.
- **Данные**: `loader`/`action` маршрутов ходят в Django по внутренней сети (`app/lib/api.server.ts`).
- **Авторизация (BFF)**: JWT Django хранятся в подписанной HttpOnly-cookie сессии (`app/lib/session.server.ts`);
  браузер токенов не видит. Истёкший access обновляется автоматически, корневой middleware
  (`app/lib/context.server.ts`) сохраняет cookie, только если сессия изменилась.
- **Корзина**: гостевая — по `cart_uuid` в сессии; после входа переходит к пользователю.
- **Формы**: работают и без JavaScript; валидация zod (`app/lib/validation.ts`) + ошибки DRF.

| Путь | Страница |
|---|---|
| `/` | Главная: категории, новинки, заявка на звонок |
| `/catalog` | Каталог: поиск (название/артикул), категория, цена, сортировка, пагинация — всё в URL |
| `/product/:slug` | Товар: фото, варианты (`?v=`), наличие, количество, в корзину, избранное, JSON-LD |
| `/cart`, `/checkout`, `/order/:id/success` | Корзина (оптимистичные обновления), оформление, подтверждение |
| `/login`, `/register`, `/confirm-email/:key`, `/reset-password[/confirm]`, `/logout` | Аккаунт |
| `/account`, `/account/orders[/:id]`, `/wishlist` | Кабинет: профиль, заказы (отмена), избранное |
| `/delivery`, `/contacts` | Информация |
| `/products/…`, `/category` | 301-редиректы со старых адресов SPA |
