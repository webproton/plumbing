import { useEffect, useState } from "react";
import { data, Form, useFetcher, useNavigation } from "react-router";

import { NpPicker } from "~/components/NpPicker";
import { Alert, Button, Card, Field, Input, PageTitle, Textarea } from "~/components/ui";
import { langFromRequest, makeT } from "~/i18n";
import { useLang, useLocalPath, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { trackEvent } from "~/lib/analytics";
import { ApiError } from "~/lib/api.server";
import { cartTotal, getCart } from "~/lib/cart.server";
import { apiContext } from "~/lib/context.server";
import { formatDate, formatPrice } from "~/lib/format";
import { sessionContext } from "~/lib/session.server";
import type { CreatedOrder, FieldErrors, NpEstimate, UserProfile } from "~/lib/types";
import { formObject, schemas, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/checkout";

export const meta: Route.MetaFunction = ({ matches }) => {
  const lang = (matches[0]?.loaderData as { lang?: "uk" | "ru" } | undefined)?.lang ?? "uk";
  return [{ title: makeT(lang)("checkout.title") }, { name: "robots", content: "noindex" }];
};

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const cart = await getCart(api, context.get(sessionContext));
  if (!cart?.cart_items.length) throw localRedirect(request, "/cart");
  const profile = api.isAuthenticated
    ? await api.get<UserProfile>("/dj-rest-auth/profile/").catch(() => null)
    : null;
  return { items: cart.cart_items, total: cartTotal(cart), profile };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = context.get(apiContext);
  const session = context.get(sessionContext);
  const t = makeT(langFromRequest(request));
  const values = formObject(await request.formData());
  const parsed = schemas(t).checkout.safeParse(values);
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), values }, { status: 400 });

  const cart = await getCart(api, session);
  if (!cart?.cart_items.length) throw localRedirect(request, "/cart");
  const f = parsed.data;
  const pickup = f.delivery === "pickup";
  // город и отделение, выбранные из справочника Новой Почты (без JS — только текстовые поля)
  const npCity = pickup ? "" : (values.np_city_ref ?? "");
  const npWarehouse = pickup || !npCity ? "" : (values.np_warehouse_ref ?? "");
  const warehouseName = npWarehouse ? (values.np_warehouse_name ?? "") : "";
  try {
    const order = await api.post<CreatedOrder>("/orders/order-create/", {
      cart_uuid: cart.cart_uuid,
      customer_name: `${f.first_name} ${f.last_name}`,
      phone_number: f.phone_number,
      email: f.email,
      city: pickup ? "" : f.city,
      department_number: pickup ? "" : f.department_number,
      address: pickup
        ? t("checkout.addressPickup")
        : warehouseName
          ? t("checkout.addressNpFull", { city: f.city, warehouse: warehouseName }).slice(0, 200)
          : t("checkout.addressNp", { city: f.city, department: f.department_number }),
      np_city_ref: npCity,
      np_warehouse_ref: npWarehouse,
      comment: f.comment,
      payment_type: f.payment_type,
    });
    session.unset("cartUuid");
    session.flash("purchase", {
      id: order.id,
      value: Number(order.total_price),
      items: cart.cart_items.slice(0, 20).map((i) => ({
        id: i.variant ?? i.product,
        name: (i.product_name ?? "").slice(0, 60),
        price: Number(i.price ?? 0),
        quantity: i.quantity,
      })),
    });
    return localRedirect(request, `/order/${order.id}/success`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors: FieldErrors =
      e.code === "insufficient_stock"
        ? { form: t("checkout.outOfStock") }
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
  const t = useT();
  const lang = useLang();
  const local = useLocalPath();
  const estimate = useFetcher<NpEstimate>();
  const onCity = (ref: string) => {
    if (ref) estimate.load(local(`/np/estimate?city=${ref}&cost=${Math.round(total)}`));
  };
  const est = estimate.data?.cost ? estimate.data : null;
  useEffect(() => {
    trackEvent("begin_checkout", {
      value: total,
      items: items.map((i) => ({ id: i.variant ?? i.product, name: i.product_name ?? "", price: Number(i.price ?? 0), quantity: i.quantity })),
    });
  }, [items, total]);
  const v = (name: string, fallback = "") => values[name] ?? fallback;

  return (
    <div>
      <PageTitle>{t("checkout.title")}</PageTitle>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Form method="post" className="space-y-6" noValidate>
          {errors.form && <Alert tone="danger">{errors.form}</Alert>}

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">{t("checkout.recipient")}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("checkout.firstName")} error={errors.first_name}>
                {(p) => <Input {...p} name="first_name" autoComplete="given-name" defaultValue={v("first_name", profile?.first_name)} />}
              </Field>
              <Field label={t("checkout.lastName")} error={errors.last_name}>
                {(p) => <Input {...p} name="last_name" autoComplete="family-name" defaultValue={v("last_name", profile?.last_name)} />}
              </Field>
              <Field label={t("checkout.phone")} error={errors.phone_number} hint={t("checkout.phoneHint")}>
                {(p) => (
                  <Input {...p} name="phone_number" type="tel" inputMode="tel" autoComplete="tel" placeholder="+380 50 123 45 67" defaultValue={v("phone_number", profile?.phone_number ?? "")} />
                )}
              </Field>
              <Field label={t("checkout.email")} error={errors.email} hint={t("checkout.emailHint")}>
                {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={v("email", profile?.email)} />}
              </Field>
            </div>
          </Card>

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">{t("checkout.delivery")}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { value: "nova_poshta", title: t("checkout.np"), text: t("checkout.npText") },
                { value: "pickup", title: t("checkout.pickup"), text: t("checkout.pickupText") },
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
              <>
                <NpPicker
                  names={{ city: "city", department: "department_number", cityRef: "np_city_ref", warehouseRef: "np_warehouse_ref", warehouseName: "np_warehouse_name" }}
                  initial={{
                    cityName: v("city", profile?.city ?? ""),
                    cityRef: v("np_city_ref"),
                    department: v("department_number"),
                    warehouseRef: v("np_warehouse_ref"),
                    warehouseName: v("np_warehouse_name"),
                  }}
                  errors={{ city: errors.city, department: errors.department_number }}
                  onCity={onCity}
                />
                {est && (
                  <p className="text-sm text-muted">
                    {t("checkout.npEstimate", { cost: formatPrice(est.cost), date: est.date ? formatDate(est.date, lang) : "—" })}
                  </p>
                )}
              </>
            )}
          </Card>

          <Card className="space-y-4 p-5">
            <h2 className="text-lg font-semibold">{t("checkout.payment")}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { value: "full", title: t("checkout.payFull") },
                { value: "partial", title: t("checkout.payPartial") },
              ].map((o) => (
                <label key={o.value} className="flex cursor-pointer items-center gap-3 rounded-xl border border-line p-4 has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50">
                  <input type="radio" name="payment_type" value={o.value} defaultChecked={v("payment_type", "full") === o.value} className="accent-brand-600" />
                  <span className="font-medium">{o.title}</span>
                </label>
              ))}
            </div>
            <p className="text-sm text-muted">{t("checkout.paymentNote")}</p>
            <Field label={t("checkout.comment")} error={errors.comment}>
              {(p) => <Textarea {...p} name="comment" maxLength={500} defaultValue={v("comment")} />}
            </Field>
          </Card>

          <Button type="submit" size="lg" loading={submitting} className="w-full sm:w-auto">
            {t("checkout.submit", { total: formatPrice(total) })}
          </Button>
        </Form>

        <Card className="space-y-3 self-start p-5 lg:sticky lg:top-24">
          <h2 className="font-semibold">{t("checkout.summary")}</h2>
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
            <span>{t("cart.total")}</span>
            <span>{formatPrice(total)}</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
