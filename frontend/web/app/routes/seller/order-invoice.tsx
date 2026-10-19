import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/order-invoice";

/** Ресурсный маршрут: счёт на оплату заказа (PDF) для менеджера */
export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const upstream = await api.download(`/orders/manage/${params.id}/invoice/`);
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="invoice-${params.id}.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}
