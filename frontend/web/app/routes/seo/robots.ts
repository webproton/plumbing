import { config } from "~/lib/config.server";
import { robotsTxt } from "~/lib/seo";

/** /robots.txt: служебные страницы закрыты, ссылка на sitemap; SEO_NOINDEX=true — закрыто всё (тестовый сервер) */
export function loader() {
  return new Response(robotsTxt(config.publicUrl, config.noindex), {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
