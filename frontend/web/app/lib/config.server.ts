// Конфигурация сервера фронтенда (только Node, в бандл браузера не попадает)

const isProd = process.env.NODE_ENV === "production";

function required(name: string, fallback: string): string {
  const value = process.env[name];
  if (value) return value;
  if (isProd && name === "SESSION_SECRET") {
    throw new Error("SESSION_SECRET must be set in production");
  }
  return fallback;
}

export const config = {
  apiUrl: (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, ""),
  sessionSecret: required("SESSION_SECRET", "dev-only-secret"),
  siteName: process.env.SITE_NAME ?? "LUXORA",
  publicUrl: (process.env.PUBLIC_URL ?? "http://localhost:3000").replace(/\/$/, ""),
  /** тестовый/промежуточный сервер: закрыть весь сайт от поисковиков */
  noindex: process.env.SEO_NOINDEX === "true",
  secureCookies: isProd && process.env.INSECURE_COOKIES !== "true",
};
