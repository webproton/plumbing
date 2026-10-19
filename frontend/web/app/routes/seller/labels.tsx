import { LONG_TIMEOUT } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/labels";

/** Ресурсный маршрут: PDF этикеток (?variants=…|products=…&size=thermal|a4&copies=N) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  for (const key of ["variants", "products", "size", "copies"]) {
    const value = q.get(key);
    if (value) query.set(key, value);
  }
  const upstream = await api.download(`/warehouse/labels/?${query}`, false, LONG_TIMEOUT);
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": upstream.headers.get("Content-Disposition") ?? 'inline; filename="labels.pdf"',
      "Cache-Control": "private, no-store",
    },
  });
}
