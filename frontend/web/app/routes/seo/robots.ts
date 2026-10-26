import { apiContext } from "~/lib/context.server";
import { config, originFor } from "~/lib/config.server";
import { robotsTxt } from "~/lib/seo";
import type { Storefront } from "~/lib/types";

import type { Route } from "./+types/robots";

/** /robots.txt: служебные страницы закрыты, ссылка на sitemap; SEO_NOINDEX=true — закрыто всё (тестовый сервер) */
export async function loader({ context }: Route.LoaderArgs) {
  const current = await context
    .get(apiContext)
    .get<{ storefront: Storefront | null }>("/storefronts/current/")
    .catch(() => ({ storefront: null }));
  return new Response(robotsTxt(originFor(current.storefront?.domain), config.noindex), {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
