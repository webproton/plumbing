import { Plus } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { VariantFields, variantPayload } from "~/components/seller/VariantFields";
import { Alert, Button, Card, Field, Input, PageTitle, Select, Textarea } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";
import type { Category, ManageProduct } from "~/lib/types";

import type { Route } from "./+types/product-new";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("prod.new.title") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const [categories, brands] = await Promise.all([
    api.get<Category[]>("/category/"),
    api.get<string[]>("/manage/brands/"),
  ]);
  return { categories, brands };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  let product: ManageProduct;
  try {
    product = await api.post<ManageProduct>("/manage/products/", {
      name: String(form.get("name") ?? "").trim(),
      category: Number(form.get("category")) || null,
      description: String(form.get("description") ?? "").trim() || null,
      variant: variantPayload(form, false),
    });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const body = (e.body ?? {}) as { variant?: Record<string, string[]> };
    // ошибки вложенного варианта приходят как {variant: {price: [...]}}
    const nested = Object.fromEntries(Object.entries(body.variant ?? {}).map(([k, v]) => [k, v.join(" ")]));
    const errors = { ...e.fieldErrors, ...nested };
    delete errors.variant;
    return data(
      { errors: Object.keys(errors).length ? errors : { form: t("error.generic") } },
      { status: 400 },
    );
  }
  const photos = form.getAll("photo").filter((f): f is File => f instanceof File && f.size > 0);
  if (photos.length) {
    const body = new FormData();
    for (const f of photos) body.append("photo", f);
    try {
      await api.post(`/manage/products/${product.id}/photos/`, body, { timeoutMs: LONG_TIMEOUT });
    } catch (e) {
      if (!(e instanceof ApiError)) throw e; // товар создан; фото можно добавить на его странице
    }
  }
  return localRedirect(request, `/seller/products/${product.id}`);
}

export default function ProductNew({ loaderData, actionData }: Route.ComponentProps) {
  const { categories, brands } = loaderData;
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const errors: Record<string, string> = actionData?.errors ?? {};

  return (
    <div className="max-w-4xl space-y-5">
      <Link to="/seller/products" className="text-brand-600 text-sm hover:underline">
        {t("prod.edit.back")}
      </Link>
      <PageTitle>{t("prod.new.title")}</PageTitle>
      <Form method="post" encType="multipart/form-data" className="space-y-5">
        {errors.form && <Alert tone="danger">{errors.form}</Alert>}
        <Card className="space-y-4 p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("prod.field.name")} error={errors.name}>
              {(p) => <Input {...p} name="name" required maxLength={255} autoFocus />}
            </Field>
            <Field label={t("prod.field.category")} error={errors.category}>
              {(p) => (
                <Select {...p} name="category" defaultValue="">
                  <option value="">{t("prod.noCategory")}</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t("prod.field.description")} error={errors.description}>
            {(p) => <Textarea {...p} name="description" rows={4} />}
          </Field>
        </Card>
        <Card className="p-5">
          <VariantFields brands={brands} errors={errors} withName={false} />
        </Card>
        <Card className="p-5">
          <Field label={t("prod.field.photos")} hint={t("prod.field.photosHint")}>
            {(p) => (
              <Input
                {...p}
                name="photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="py-2"
              />
            )}
          </Field>
        </Card>
        <Button type="submit" size="lg" loading={busy}>
          <Plus className="size-4" aria-hidden /> {t("prod.create")}
        </Button>
      </Form>
    </div>
  );
}
