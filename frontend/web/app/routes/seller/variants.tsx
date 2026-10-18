import { requireSeller } from "~/lib/seller.server";
import type { VariantLookup } from "~/lib/types";

import type { Route } from "./+types/variants";

/** Ресурсный маршрут: поиск товара для форм склада (JSON, без страницы) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams.get("q") ?? "";
  if (q.trim().length < 2) return [] as VariantLookup[];
  return api.get<VariantLookup[]>("/warehouse/variants/search/", { query: { q } });
}
