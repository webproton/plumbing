import { createContext, type MiddlewareFunction } from "react-router";

import { langFromRequest } from "~/i18n";

import { Api } from "./api.server";
import { sessionContext, sessionStorage, type AppSession } from "./session.server";

/** API-клиент текущего запроса */
export const apiContext = createContext<Api>();

/**
 * Витрина запроса: ?store=<slug> запоминается в сессии (?store=all — снова общий магазин).
 * Если ссылки нет, Django определит витрину по домену (заголовок X-Storefront-Host).
 */
function storefrontOf(request: Request, session: AppSession): string | null {
  const params = new URL(request.url).searchParams;
  if (params.has("store")) {
    const value = (params.get("store") ?? "").trim().toLowerCase();
    if (!value || value === "all") session.unset("store");
    else session.set("store", value);
  }
  return session.get("store") ?? null;
}

function clientIp(request: Request): string | null {
  // X-Real-IP выставляет nginx; в dev заголовка нет
  return request.headers.get("X-Real-IP") ?? request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ?? null;
}

/**
 * Корневой middleware: сессия + API-клиент в context для всех loaders/actions;
 * после ответа сохраняет cookie, если сессия изменилась (вход, выход, обновление токена, корзина).
 */
export const sessionMiddleware: MiddlewareFunction<Response> = async ({ request, context }, next) => {
  const session = await sessionStorage.getSession(request.headers.get("Cookie"));
  const before = JSON.stringify(session.data);
  context.set(sessionContext, session);
  const host = request.headers.get("X-Forwarded-Host") ?? request.headers.get("Host");
  const storefront = { slug: storefrontOf(request, session), host };
  context.set(apiContext, new Api(session, clientIp(request), langFromRequest(request), storefront));

  const response = await next();

  if (JSON.stringify(session.data) === before) return response;
  const cookie = await sessionStorage.commitSession(session);
  try {
    response.headers.append("Set-Cookie", cookie);
    return response;
  } catch {
    // у некоторых Response заголовки неизменяемы — пересоздаём
    const copy = new Response(response.body, response);
    copy.headers.append("Set-Cookie", cookie);
    return copy;
  }
};
