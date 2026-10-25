import { apiContext } from "~/lib/context.server";
import { config } from "~/lib/config.server";
import { buildSitemap, type SitemapData } from "~/lib/seo";

import type { Route } from "./+types/sitemap";

/** /sitemap.xml: главная, каталог, страницы, непустые категории и видимые товары — на украинском и русском */
export async function loader({ context }: Route.LoaderArgs) {
  if (config.noindex) return new Response("Not Found", { status: 404 }); // тестовый сервер — карты сайта нет
  const data = await context
    .get(apiContext)
    .get<SitemapData>("/seo/sitemap/")
    .catch(() => null);
  if (!data) return new Response("Service Unavailable", { status: 503, headers: { "Retry-After": "300" } });
  return new Response(buildSitemap(data, config.publicUrl), {
    headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
