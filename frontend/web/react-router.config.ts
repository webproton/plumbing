import type { Config } from "@react-router/dev/config";

export default {
  // SSR: страницы каталога и товара отдаются готовым HTML (SEO без prerender-сервиса)
  ssr: true,
} satisfies Config;
