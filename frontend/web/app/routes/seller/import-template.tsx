import { LONG_TIMEOUT } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/import-template";

/** Ресурсный маршрут: шаблон загрузки товаров (?type=xlsx|csv, &products=1 — с товарами продавца) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const query = new URLSearchParams({ type: q.get("type") === "csv" ? "csv" : "xlsx" });
  if (q.get("products") === "1") query.set("products", "1");
  const upstream = await api.download(`/imports/template/?${query}`, false, LONG_TIMEOUT);
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition":
        upstream.headers.get("Content-Disposition") ?? 'attachment; filename="products-template.xlsx"',
      "Cache-Control": "private, no-store",
    },
  });
}
