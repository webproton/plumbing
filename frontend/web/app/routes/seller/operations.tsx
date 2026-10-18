import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { data, Form, useNavigation, useSearchParams } from "react-router";

import { VariantPicker } from "~/components/seller/VariantPicker";
import { Alert, Button, Card, Field, Input, PageTitle, Select, Textarea } from "~/components/ui";
import { makeT, tFromMatches, type TKey } from "~/i18n";
import { langFromRequest } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { bad, requireSeller } from "~/lib/seller.server";
import type { Supplier } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/operations";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.operations") }];

const OPS = ["receive", "write_off", "return_supplier", "return_customer", "transfer", "inventory"] as const;
type Op = (typeof OPS)[number];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const suppliers = await api.get<Supplier[]>("/warehouse/suppliers/");
  return { suppliers: suppliers.filter((s) => s.is_active) };
}

const num = (v: string | undefined) => (v ?? "").replace(/\s/g, "").replace(",", ".");

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const v = formObject(await request.formData());
  const op = v.op as Op;
  const errors: Record<string, string> = {};
  const need = (field: string) => {
    if (!v[field]) errors[field] = t("wh.op.required");
  };
  need("variant");
  need("quantity");
  if (op === "transfer") {
    need("from_warehouse");
    need("to_warehouse");
  } else need("warehouse");
  if (op === "receive" || op === "return_supplier") need("supplier");
  if (Object.keys(errors).length) return bad(errors, v);

  const quantity = num(v.quantity);
  try {
    if (op === "transfer") {
      await api.post("/warehouse/stock-movements/transfer/", {
        variant: Number(v.variant),
        from_warehouse: Number(v.from_warehouse),
        to_warehouse: Number(v.to_warehouse),
        quantity,
      });
    } else if (op === "inventory") {
      await api.post("/warehouse/stock-movements/inventory/", {
        variant: Number(v.variant),
        warehouse: Number(v.warehouse),
        quantity,
      });
    } else {
      const type = { receive: "in", write_off: "out", return_supplier: "return_out", return_customer: "return_in" }[op];
      await api.post("/warehouse/stock-movements/", {
        variant: Number(v.variant),
        warehouse: Number(v.warehouse),
        movement_type: type,
        quantity,
        ...(v.supplier ? { supplier: Number(v.supplier) } : {}),
        ...(v.price ? { price_per_unit: num(v.price) } : {}),
        ...(v.document_number ? { document_number: v.document_number } : {}),
        comment: v.comment ?? "",
      });
    }
    return { ok: true as const, op, at: Date.now() };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ ok: false as const, errors: e.fieldErrors, values: v }, { status: 400 });
  }
}

export default function Operations({ loaderData, actionData }: Route.ComponentProps) {
  const { suppliers } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const [params, setParams] = useSearchParams();
  const op = (OPS.includes(params.get("op") as Op) ? params.get("op") : "receive") as Op;
  const submitting = useNavigation().state === "submitting";
  const formRef = useRef<HTMLFormElement>(null);
  const done = actionData?.ok ? actionData : null;
  const errors = (actionData && !actionData.ok ? actionData.errors : {}) as Record<string, string>;
  const values = (actionData && !actionData.ok ? actionData.values : {}) as Record<string, string>;
  const defaultWh = String(me.warehouses.find((w) => w.is_default)?.id ?? me.warehouses[0]?.id ?? "");

  // после успешной операции форма очищается (в том числе выбранный товар)
  useEffect(() => {
    if (done) formRef.current?.reset();
  }, [done?.at]); // eslint-disable-line react-hooks/exhaustive-deps

  const whSelect = (name: string, label: TKey, error?: string, initial?: string) => (
    <Field label={t(label)} error={error}>
      {(p) => (
        <Select {...p} name={name} defaultValue={initial ?? defaultWh}>
          {me.warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );

  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("wh.op.subtitle")}>{t("wh.nav.operations")}</PageTitle>

      <div role="tablist" aria-label={t("wh.nav.operations")} className="flex flex-wrap gap-2">
        {OPS.map((o) => (
          <button
            key={o}
            role="tab"
            aria-selected={o === op}
            type="button"
            onClick={() => setParams({ op: o }, { replace: true, preventScrollReset: true })}
            className={`rounded-xl border px-3.5 py-2 text-sm font-medium ${o === op ? "border-brand-500 bg-brand-50 text-brand-700" : "border-line bg-white hover:border-brand-500"}`}
          >
            {t(`wh.op.${o}` as TKey)}
          </button>
        ))}
      </div>

      {done && (
        <Alert tone="success">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="size-4" aria-hidden /> {t("wh.op.done")}{" "}
            <Link to="/seller/movements" className="font-semibold underline">
              {t("wh.nav.movements")}
            </Link>
          </span>
        </Alert>
      )}
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}

      <Card className="p-5">
        <Form method="post" ref={formRef} key={op} className="space-y-4" noValidate>
          <input type="hidden" name="op" value={op} />
          <p className="text-sm text-muted">{t(`wh.op.${op}.hint` as TKey)}</p>

          <Field label={t("wh.col.product")} error={errors.variant}>
            {() => <VariantPicker error={errors.variant} />}
          </Field>

          {op === "transfer" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {whSelect("from_warehouse", "wh.op.from", errors.from_warehouse, values.from_warehouse)}
              {whSelect("to_warehouse", "wh.op.to", errors.to_warehouse, values.to_warehouse ?? me.warehouses[1]?.id?.toString())}
            </div>
          ) : (
            whSelect("warehouse", "wh.col.warehouse", errors.warehouse, values.warehouse)
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={op === "inventory" ? t("wh.op.counted") : t("wh.col.qty")} error={errors.quantity} hint={t("wh.op.qtyHint")}>
              {(p) => <Input {...p} name="quantity" inputMode="decimal" defaultValue={values.quantity} autoComplete="off" />}
            </Field>
            {(op === "receive" || op === "return_supplier") && (
              <Field label={t("wh.col.supplier")} error={errors.supplier}>
                {(p) => (
                  <Select {...p} name="supplier" defaultValue={values.supplier ?? ""}>
                    <option value="">—</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>

          {(op === "receive" || op === "return_customer") && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("wh.op.purchasePrice")} error={errors.price_per_unit}>
                {(p) => <Input {...p} name="price" inputMode="decimal" defaultValue={values.price} autoComplete="off" />}
              </Field>
              <Field label={t("wh.op.docNumber")} error={errors.document_number}>
                {(p) => <Input {...p} name="document_number" maxLength={50} defaultValue={values.document_number} />}
              </Field>
            </div>
          )}

          {op !== "inventory" && op !== "transfer" && (
            <Field label={t("checkout.comment")} error={errors.comment}>
              {(p) => <Textarea {...p} name="comment" defaultValue={values.comment} className="min-h-20" />}
            </Field>
          )}

          <Button type="submit" size="lg" loading={submitting}>
            {t(`wh.op.${op}.submit` as TKey)}
          </Button>
        </Form>
      </Card>
    </div>
  );
}
