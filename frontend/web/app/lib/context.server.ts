import { createContext, type MiddlewareFunction } from "react-router";

import { Api } from "./api.server";
import { sessionContext, sessionStorage } from "./session.server";

/** API-клиент текущего запроса */
export const apiContext = createContext<Api>();

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
  context.set(apiContext, new Api(session, clientIp(request)));

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
