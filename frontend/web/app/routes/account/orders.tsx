import { Package } from "lucide-react";
import { Link } from "react-router";

import { Badge, ButtonLink, EmptyState, PageTitle } from "~/components/ui";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { formatDate, formatPrice, statusTone } from "~/lib/format";
import type { OrderListItem } from "~/lib/types";

import type { Route } from "./+types/orders";

export const meta: Route.MetaFunction = () => [{ title: "Мои заказы" }];

export async function loader({ request, context }: Route.LoaderArgs) {
  requireUser(request, context);
  return { orders: await context.get(apiContext).get<OrderListItem[]>("/orders/history/") };
}

export default function Orders({ loaderData }: Route.ComponentProps) {
  if (!loaderData.orders.length) {
    return (
      <EmptyState icon={Package} title="Заказов пока нет">
        <p className="mb-4">Здесь будет история ваших покупок.</p>
        <ButtonLink to="/catalog">В каталог</ButtonLink>
      </EmptyState>
    );
  }
  return (
    <div>
      <PageTitle>Мои заказы</PageTitle>
      <ul className="space-y-3">
        {loaderData.orders.map((o) => (
          <li key={o.id}>
            <Link to={`/account/orders/${o.id}`} className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-white p-4 hover:border-brand-500">
              <div className="flex -space-x-3">
                {o.list_of_product_images.slice(0, 3).map((img) => (
                  <img key={img.variant_id} src={img.photo} alt="" className="size-12 rounded-lg border-2 border-white bg-surface object-contain" />
                ))}
              </div>
              <div className="flex-1">
                <p className="font-semibold">Заказ №{o.id}</p>
                <p className="text-sm text-muted">{formatDate(o.creation_date)}</p>
              </div>
              <Badge tone={statusTone(o.status_order)}>{o.status_order_display}</Badge>
              <span className="font-semibold">{formatPrice(o.total_price)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
