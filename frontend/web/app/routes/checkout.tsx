import { useState } from "react";
import { data, Form, redirect, useNavigation } from "react-router";

import { Alert, Button, Card, Field, Input, PageTitle, Textarea } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { cartTotal, getCart } from "~/lib/cart.server";
import { apiContext } from "~/lib/context.server";
import { formatPrice } from "~/lib/format";
import { sessionContext } from "~/lib/session.server";
import type { CreatedOrder, FieldErrors, UserProfile } from "~/lib/types";
import { checkoutSchema, formObject, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/checkout";

export const meta: Route.MetaFunction = () => [{ title: "Оформление заказа" }, { name: "robots", content: "noindex" }];

export async function loader({ context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const cart = await getCart(api, context.get(sessionContext));
  if (!cart?.cart_items.length) throw redirect("/cart");
  const profile = api.isAuthenticated
    ? await api.get<UserProfile>("/dj-rest-auth/profile/").catch(() => null)
    : null;
  return { items: cart.cart_items, total: cartTotal(cart), profile };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = context.get(apiContext);
  const session = context.get(sessionContext);
  const values = formObject(await request.formData());
  const parsed = checkoutSchema.safeParse(values);
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), values }, { status: 400 });

  const cart = await getCart(api, session);
  if (!cart?.cart_items.length) throw redirect("/cart");
  const f = parsed.data;
  const pickup = f.delivery === "pickup";
  try {
    const order = await api.post<CreatedOrder>("/orders/order-create/", {
      cart_uuid: cart.cart_uuid,
      customer_name: `${f.first_name} ${f.last_name}`,
      phone_number: f.phone_number,
      email: f.email,
      city: pickup ? "" : f.city,
      department_number: pickup ? "" : f.department_number,
      address: pickup ? "Самовывоз" : `Новая Почта, ${f.city}, отделение ${f.department_number}`,
      comment: f.comment,
      payment_type: f.payment_type,
    });
    session.unset("cartUuid");
    return redirect(`/order/${order.id}/success`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors: FieldErrors =
      e.code === "insufficient_stock"
        ? { form: "Часть товаров закончилась, пока вы оформляли заказ. Проверьте корзину." }
        : e.fieldErrors;
    return data({ errors, values }, { status: 400 });
  }
}

export default function Checkout({ loaderData, actionData }: Route.ComponentProps) {
  const { items, total, profile } = loaderData;
  const errors: FieldErrors = actionData?.errors ?? {};
  const values: Record<string, string> = actionData?.values ?? {};
  const [delivery, setDelivery] = useState(values.delivery ?? "nova_poshta");
  const submitting = useNavigation().state === "submitting";
  const v = (name: string, fallback = "") => values[name] ?? fallback;

  return (
    <div>
      <PageTitle>Оформление заказа</PageTitle>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Form method="post" className="space-y-6" noValidate>
          {errors.form && <Alert tone="danger">{errors.form}</Alert>}

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">Получатель</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Имя" error={errors.first_name}>
                {(p) => <Input {...p} name="first_name" autoComplete="given-name" defaultValue={v("first_name", profile?.first_name)} />}
              </Field>
              <Field label="Фамилия" error={errors.last_name}>
                {(p) => <Input {...p} name="last_name" autoComplete="family-name" defaultValue={v("last_name", profile?.last_name)} />}
              </Field>
              <Field label="Телефон" error={errors.phone_number} hint="Позвоним для подтверждения">
                {(p) => (
                  <Input {...p} name="phone_number" type="tel" inputMode="tel" autoComplete="tel" placeholder="+380 50 123 45 67" defaultValue={v("phone_number", profile?.phone_number ?? "")} />
                )}
              </Field>
              <Field label="Email (необязательно)" error={errors.email} hint="Пришлём подтверждение заказа">
                {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={v("email", profile?.email)} />}
              </Field>
            </div>
          </Card>

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">Доставка</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { value: "nova_poshta", title: "Новая Почта", text: "В отделение, 1–3 дня" },
                { value: "pickup", title: "Самовывоз", text: "Со склада, после звонка менеджера" },
              ].map((o) => (
                <label key={o.value} className={`flex cursor-pointer gap-3 rounded-xl border p-4 ${delivery === o.value ? "border-brand-500 bg-brand-50" : "border-line"}`}>
                  <input type="radio" name="delivery" value={o.value} checked={delivery === o.value} onChange={() => setDelivery(o.value)} className="mt-1 accent-brand-600" />
                  <span>
                    <span className="block font-medium">{o.title}</span>
                    <span className="text-sm text-muted">{o.text}</span>
                  </span>
                </label>
              ))}
            </div>
            {delivery === "nova_poshta" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Город" error={errors.city}>
                  {(p) => <Input {...p} name="city" autoComplete="address-level2" defaultValue={v("city", profile?.city ?? "")} />}
                </Field>
                <Field label="Номер отделения" error={errors.department_number}>
                  {(p) => <Input {...p} name="department_number" inputMode="numeric" defaultValue={v("department_number")} />}
                </Field>
              </div>
            )}
          </Card>

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">Оплата</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { value: "full", title: "Полная оплата" },
                { value: "partial", title: "Предоплата 50%" },
              ].map((o) => (
                <label key={o.value} className="flex cursor-pointer items-center gap-3 rounded-xl border border-line p-4 has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50">
                  <input type="radio" name="payment_type" value={o.value} defaultChecked={v("payment_type", "full") === o.value} className="accent-brand-600" />
                  <span className="font-medium">{o.title}</span>
                </label>
              ))}
            </div>
            <p className="text-sm text-muted">Реквизиты для оплаты менеджер пришлёт после подтверждения заказа.</p>
            <Field label="Комментарий" error={errors.comment}>
              {(p) => <Textarea {...p} name="comment" maxLength={500} defaultValue={v("comment")} />}
            </Field>
          </Card>

          <Button type="submit" size="lg" loading={submitting} className="w-full sm:w-auto">
            Подтвердить заказ на {formatPrice(total)}
          </Button>
        </Form>

        <Card className="space-y-3 self-start p-5 lg:sticky lg:top-24">
          <h2 className="font-semibold">Ваш заказ</h2>
          <ul className="divide-y divide-line text-sm">
            {items.map((i) => (
              <li key={i.id} className="flex justify-between gap-3 py-2">
                <span>
                  {i.product_name} <span className="text-muted">× {i.quantity}</span>
                </span>
                <span className="font-medium whitespace-nowrap">{formatPrice(Number(i.price ?? 0) * i.quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-between border-t border-line pt-3 text-lg font-bold">
            <span>Итого</span>
            <span>{formatPrice(total)}</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
