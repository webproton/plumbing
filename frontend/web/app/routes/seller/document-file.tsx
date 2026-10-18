import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/document-file";

/** Ресурсный маршрут: скачать исходный файл накладной (хранится в приватном хранилище Django) */
export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const upstream = await api.download(`/warehouse/inventory-documents/${params.id}/file/`);
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("Content-Disposition") ?? `attachment; filename="invoice-${params.id}"`,
      "Cache-Control": "private, no-store",
    },
  });
}
