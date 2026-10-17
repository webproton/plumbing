import { data, Form, Link, useNavigation } from "react-router";

import { Alert, Badge, Button, Card, PageTitle } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { formatDate, formatPrice, formatQty, statusTone } from "~/lib/format";
import type { OrderDetail, OrderListItem } from "~/lib/types";

import type { Route } from "./+types/order";

export const meta: Route.MetaFunction = ({ params }) => [{ title: `Заказ №${params.id}` }];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  requireUser(request, context);
  const api = context.get(apiContext);
  try {
    const [order, list] = await Promise.all([
      api.get<OrderDetail>(`/orders/history/${params.id}/`),
      api.get<OrderListItem[]>("/orders/history/"),
    ]);
    const canCancel = list.find((o) => String(o.id) === params.id)?.can_be_canceled ?? false;
    return { order, canCancel };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Заказ не найден", { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  requireUser(request, context);
  try {
    await context.get(apiContext).post(`/orders/history/${params.id}/cancel/`);
    return { error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ error: e.fieldErrors.form ?? "Не удалось отменить заказ" }, { status: 400 });
  }
}

export default function Order({ loaderData, actionData }: Route.ComponentProps) {
  const { order, canCancel } = loaderData;
  const canceling = useNavigation().state === "submitting";
  return (
    <div className="space-y-4">
      <Link to="/account/orders" className="text-sm text-brand-600 hover:underline">← Все заказы</Link>
      <PageTitle subtitle={formatDate(order.creation_date)}>Заказ №{order.number_order}</PageTitle>
      {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}
      <div className="flex flex-wrap gap-2">
        <Badge tone={statusTone(order.status_order)}>{order.status_order_display}</Badge>
        <Badge tone="muted">{order.payment_type_display}</Badge>
      </div>
      <Card className="divide-y divide-line">
        {order.list_of_products.map((line) => (
          <div key={line.variant.id} className="flex items-center gap-4 p-4">
            {line.photo && <img src={line.photo} alt="" className="size-14 rounded-lg bg-surface object-contain" />}
            <div className="flex-1">
              <p className="font-medium">{line.name}</p>
              <p className="text-sm text-muted">
                {formatQty(line.quantity)} × {formatPrice(line.price)}
                {line.sku && ` · арт. ${line.sku}`}
              </p>
            </div>
            <span className="font-semibold">{formatPrice(line.total)}</span>
          </div>
        ))}
        <div className="flex justify-between p-4 text-lg font-bold">
          <span>Итого</span>
          <span>{formatPrice(order.total_price)}</span>
        </div>
      </Card>
      <Card className="space-y-1 p-4 text-sm">
        <p><span className="text-muted">Получатель:</span> {order.customer_name}</p>
        <p><span className="text-muted">Доставка:</span> {order.address}</p>
        {order.comment && <p><span className="text-muted">Комментарий:</span> {order.comment}</p>}
      </Card>
      {canCancel && (
        <Form method="post" onSubmit={(e) => !confirm("Отменить заказ? Товар вернётся в продажу.") && e.preventDefault()}>
          <Button type="submit" variant="secondary" loading={canceling}>Отменить заказ</Button>
        </Form>
      )}
    </div>
  );
}
