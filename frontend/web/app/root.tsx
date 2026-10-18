import { Lock, SearchX, ServerCrash } from "lucide-react";
import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLocation,
  useNavigation,
  useRouteLoaderData,
} from "react-router";

import type { Route } from "./+types/root";
import "./app.css";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { ButtonLink, EmptyState } from "./components/ui";
import { LANGS, langFromRequest, localizePath, stripLang } from "./i18n";
import { useT } from "./i18n/react";
import { cartCount, getCart } from "./lib/cart.server";
import { config } from "./lib/config.server";
import { apiContext, sessionMiddleware } from "./lib/context.server";
import { sessionContext } from "./lib/session.server";
import type { Category, SiteSettings } from "./lib/types";

export const middleware: Route.MiddlewareFunction[] = [sessionMiddleware];

export const links: Route.LinksFunction = () => [
  { rel: "preconnect", href: "https://fonts.googleapis.com" },
  { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
  {
    rel: "stylesheet",
    href: "https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap",
  },
];

async function safe<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const session = context.get(sessionContext);
  const [cart, categories, settings] = await Promise.all([
    safe(getCart(api, session), null),
    safe(api.get<Category[]>("/category/"), [] as Category[]),
    safe(api.get<SiteSettings>("/callback/site-settings/"), null),
  ]);
  return {
    lang: langFromRequest(request),
    siteName: config.siteName,
    publicUrl: config.publicUrl,
    user: session.get("user") ?? null,
    cartCount: cartCount(cart),
    categories,
    settings,
  };
}

export type RootData = Awaited<ReturnType<typeof loader>>;

export function useRootData() {
  return useRouteLoaderData<typeof loader>("root");
}

export function Layout({ children }: { children: React.ReactNode }) {
  const data = useRouteLoaderData<typeof loader>("root");
  const { pathname, search } = useLocation();
  const lang = data?.lang ?? "uk";
  const base = stripLang(pathname);
  const origin = data?.publicUrl ?? "";
  return (
    <html lang={lang}>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#1d6fa5" />
        <Meta />
        <link rel="canonical" href={`${origin}${localizePath(lang, base)}${search}`} />
        {LANGS.map((l) => (
          <link key={l} rel="alternate" hrefLang={l} href={`${origin}${localizePath(l, base)}${search}`} />
        ))}
        <link rel="alternate" hrefLang="x-default" href={`${origin}${base}${search}`} />
        <Links />
      </head>
      <body className="flex min-h-dvh flex-col">
        <Header
          siteName={data?.siteName ?? "LUXORA"}
          user={data?.user ?? null}
          cartCount={data?.cartCount ?? 0}
          categories={data?.categories ?? []}
          phone={data?.settings?.phone ?? null}
        />
        <NavigationProgress />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:py-8">{children}</main>
        <Footer siteName={data?.siteName ?? "LUXORA"} settings={data?.settings ?? null} />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

/** Тонкая полоска загрузки при переходах между страницами */
function NavigationProgress() {
  const navigation = useNavigation();
  return (
    <div
      aria-hidden
      className={`fixed inset-x-0 top-0 z-50 h-0.5 bg-brand-500 transition-opacity duration-300 ${
        navigation.state === "idle" ? "opacity-0" : "animate-pulse opacity-100"
      }`}
    />
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const t = useT();
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <EmptyState icon={SearchX} title={t("error.notFound.title")}>
        <p className="mb-4">{t("error.notFound.text")}</p>
        <ButtonLink to="/catalog">{t("common.toCatalog")}</ButtonLink>
      </EmptyState>
    );
  }
  if (isRouteErrorResponse(error) && error.status === 403) {
    // кабинет склада: нет роли продавца (или заявка ещё на одобрении)
    const pending = Boolean((error.data as { pending?: boolean } | null)?.pending);
    return (
      <EmptyState icon={Lock} title={t(pending ? "wh.pending.title" : "wh.noAccess.title")}>
        {t(pending ? "wh.pending.text" : "wh.noAccess.text")}
      </EmptyState>
    );
  }
  return (
    <EmptyState icon={ServerCrash} title={t("error.server.title")}>
      <p className="mb-4">{t("error.server.text")}</p>
      {import.meta.env.DEV && error instanceof Error && (
        <pre className="mb-4 max-w-full overflow-x-auto rounded-lg bg-surface p-3 text-left text-xs">{error.stack}</pre>
      )}
      <ButtonLink to="/">{t("common.toHome")}</ButtonLink>
    </EmptyState>
  );
}
