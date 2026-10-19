import { LOCALE, makeT, type Lang } from "~/i18n";

import { config } from "./config.server";
import type { AppSession } from "./session.server";
import type { FieldErrors } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    public lang: Lang = "uk",
  ) {
    super(`API ${status}`);
  }

  /** Ошибки DRF → {поле: "сообщение"}; общие ошибки — в ключе "form" */
  get fieldErrors(): FieldErrors {
    return toFieldErrors(this.body, makeT(this.lang)("error.generic"));
  }

  get code(): string | undefined {
    return isRecord(this.body) && typeof this.body.code === "string" ? this.body.code : undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function toFieldErrors(body: unknown, fallback = "Не вдалося виконати запит. Спробуйте ще раз."): FieldErrors {
  if (typeof body === "string") return { form: body };
  if (Array.isArray(body)) return { form: body.map(String).join(" ") };
  if (!isRecord(body)) return { form: fallback };
  const errors: FieldErrors = {};
  for (const [key, value] of Object.entries(body)) {
    if (key === "code") continue;
    const message = Array.isArray(value) ? value.map(String).join(" ") : String(value);
    const field = key === "detail" || key === "non_field_errors" ? "form" : key;
    errors[field] = errors[field] ? `${errors[field]} ${message}` : message;
  }
  return Object.keys(errors).length ? errors : { form: fallback };
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  query?: Record<string, string | number | undefined | null>;
  body?: unknown;
  auth?: boolean; // прикладывать токен пользователя (по умолчанию — если он есть)
  timeoutMs?: number; // по умолчанию 15 с; длинные операции (импорт, публикация) — до LONG_TIMEOUT
}

/** Для тяжёлых запросов (разбор файла импорта, создание сотен товаров). Меньше proxy_read_timeout nginx. */
export const LONG_TIMEOUT = 90_000;

/**
 * Клиент Django API для loaders/actions. Создаётся на каждый запрос (см. root middleware).
 * Если access-токен истёк, один раз обновляет его по refresh и сохраняет в сессию.
 */
export class Api {
  constructor(
    private session: AppSession,
    private clientIp: string | null,
    private lang: Lang = "uk",
  ) {}

  get isAuthenticated(): boolean {
    return this.session.has("access");
  }

  get<T>(path: string, opts: RequestOptions = {}) {
    return this.request<T>("GET", path, opts);
  }
  post<T>(path: string, body?: unknown, opts: RequestOptions = {}) {
    return this.request<T>("POST", path, { ...opts, body });
  }
  put<T>(path: string, body?: unknown, opts: RequestOptions = {}) {
    return this.request<T>("PUT", path, { ...opts, body });
  }
  patch<T>(path: string, body?: unknown, opts: RequestOptions = {}) {
    return this.request<T>("PATCH", path, { ...opts, body });
  }
  delete<T>(path: string, opts: RequestOptions = {}) {
    return this.request<T>("DELETE", path, opts);
  }

  async request<T>(method: Method, path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
    const url = new URL(`${config.apiUrl}/api${path}`);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
    // язык ответов API (тексты ошибок валидации)
    const headers: Record<string, string> = { Accept: "application/json", "Accept-Language": LOCALE[this.lang] };
    const isForm = opts.body instanceof FormData;
    // FormData: браузер/fetch сами выставят multipart с boundary
    if (opts.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
    if (this.clientIp) headers["X-Real-IP"] = this.clientIp;
    const token = this.session.get("access");
    if (token && opts.auth !== false) headers.Authorization = `Bearer ${token}`;

    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
        signal: AbortSignal.timeout(opts.timeoutMs ?? 15_000),
      });
    } catch {
      throw new ApiError(503, { detail: makeT(this.lang)("error.unavailable") }, this.lang);
    }

    if (response.status === 401 && token && opts.auth !== false && !retried) {
      // истёк access: обновляем; если сессия мертва — повторяем как гость (публичные страницы не ломаются)
      const refreshed = await this.refresh();
      return this.request<T>(method, path, refreshed ? opts : { ...opts, auth: false }, true);
    }
    if (response.status === 204) return undefined as T;

    const text = await response.text();
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      /* не JSON (например, HTML-страница ошибки) — оставляем текст */
    }
    if (!response.ok) throw new ApiError(response.status, body, this.lang);
    return body as T;
  }

  private async refresh(): Promise<boolean> {
    const refresh = this.session.get("refresh");
    if (!refresh) return false;
    try {
      const response = await fetch(`${config.apiUrl}/api/dj-rest-auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) {
        this.signOut();
        return false;
      }
      const data = (await response.json()) as { access: string; refresh?: string };
      this.session.set("access", data.access);
      if (data.refresh) this.session.set("refresh", data.refresh);
      return true;
    } catch {
      return false;
    }
  }

  /** Сырой ответ API (скачивание файлов). Токен подставляется на сервере витрины. */
  async download(path: string, retried = false, timeoutMs = 30_000): Promise<Response> {
    const token = this.session.get("access");
    const response = await fetch(`${config.apiUrl}/api${path}`, {
      headers: { "Accept-Language": LOCALE[this.lang], ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (response.status === 401 && token && !retried && (await this.refresh())) return this.download(path, true, timeoutMs);
    if (!response.ok) throw new ApiError(response.status, null, this.lang);
    return response;
  }

  signIn(tokens: { access: string; refresh: string }, user: { email: string; name: string; staff?: boolean }) {
    this.session.set("access", tokens.access);
    this.session.set("refresh", tokens.refresh);
    this.session.set("user", user);
  }

  signOut() {
    this.session.unset("access");
    this.session.unset("refresh");
    this.session.unset("user");
  }
}
