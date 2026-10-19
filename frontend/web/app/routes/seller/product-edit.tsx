import { ExternalLink, ImagePlus, Plus, Save, Star, Trash2 } from "lucide-react";
import { data, Form, useFetcher, useNavigation } from "react-router";

import { VariantFields, variantPayload } from "~/components/seller/VariantFields";
import { Alert, Badge, Button, Card, Field, Input, PageTitle, Select, Textarea } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { Category, ManageProduct, ManageVariant } from "~/lib/types";

import type { Route } from "./+types/product-edit";

export const meta: Route.MetaFunction = ({ loaderData, matches }) => [
  { title: loaderData?.product.name ?? tFromMatches(matches)("prod.nav") },
];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  try {
    const [product, categories, brands] = await Promise.all([
      api.get<ManageProduct>(`/manage/products/${params.id}/`),
      api.get<Category[]>("/category/"),
      api.get<string[]>("/manage/brands/"),
    ]);
    return { product, categories, brands };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

type Result = { ok: boolean; intent: string; id?: number; errors?: Record<string, string> };

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const id = Number(form.get("id")) || undefined;
  const base = `/manage/products/${params.id}`;
  try {
    switch (intent) {
      case "product":
        await api.patch(`${base}/`, {
          name: String(form.get("name") ?? "").trim(),
          category: Number(form.get("category")) || null,
          description: String(form.get("description") ?? "").trim() || null,
        });
        break;
      case "variant":
        await api.patch(`/manage/variants/${id}/`, variantPayload(form));
        break;
      case "add_variant":
        await api.post(`${base}/variants/`, variantPayload(form));
        break;
      case "delete_variant":
        await api.delete(`/manage/variants/${id}/`);
        break;
      case "photos": {
        const body = new FormData();
        for (const f of form.getAll("photo")) if (f instanceof File && f.size > 0) body.append("photo", f);
        await api.post(`${base}/photos/`, body, { timeoutMs: LONG_TIMEOUT });
        break;
      }
      case "photo_op":
        await api.post(`${base}/photos/${String(form.get("photo"))}/${String(form.get("op"))}/`);
        break;
      case "delete":
        await api.delete(`${base}/`);
        return localRedirect(request, "/seller/products");
    }
    return { ok: true, intent, id } satisfies Result;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors = Object.keys(e.fieldErrors).length ? e.fieldErrors : { form: t("error.generic") };
    return data({ ok: false, intent, id, errors } satisfies Result, { status: 400 });
  }
}

function VariantCard({
  variant,
  brands,
  index,
}: {
  variant: ManageVariant;
  brands: string[];
  index: number;
}) {
  const t = useT();
  const fetcher = useFetcher<Result>();
  const errors = fetcher.data && !fetcher.data.ok ? (fetcher.data.errors ?? {}) : {};
  const saved = fetcher.state === "idle" && fetcher.data?.ok && fetcher.data.intent === "variant";
  return (
    <div className="border-line space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">
          {variant.variant_name || `#${variant.id}`}
          {variant.discount > 0 && (
            <Badge tone="info">{t("prod.variant.discount", { n: variant.discount })}</Badge>
          )}
        </p>
        <p className="text-muted text-sm">
          {t("prod.variant.stock", {
            stock: formatQty(variant.stock),
            reserved: formatQty(variant.reserved),
          })}{" "}
          ·{" "}
          <Link to={`/seller/movements?variant=${variant.id}`} className="text-brand-700 hover:underline">
            {t("prod.variant.movements")}
          </Link>
        </p>
      </div>
      <fetcher.Form method="post" className="space-y-3">
        <input type="hidden" name="intent" value="variant" />
        <input type="hidden" name="id" value={variant.id} />
        <VariantFields variant={variant} brands={brands} errors={errors} listId={`brands-${index}`} />
        {(errors.form || errors.detail) && <Alert tone="danger">{errors.form ?? errors.detail}</Alert>}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="submit"
            size="sm"
            loading={fetcher.state !== "idle" && fetcher.formData?.get("intent") === "variant"}
          >
            <Save className="size-3.5" aria-hidden /> {t("prod.save")}
          </Button>
          {saved && <span className="text-success text-sm">{t("prod.saved")}</span>}
        </div>
      </fetcher.Form>
      <fetcher.Form
        method="post"
        onSubmit={(e) => !confirm(t("prod.variant.deleteConfirm")) && e.preventDefault()}
      >
        <input type="hidden" name="intent" value="delete_variant" />
        <input type="hidden" name="id" value={variant.id} />
        <Button type="submit" size="sm" variant="ghost" className="text-danger">
          <Trash2 className="size-3.5" aria-hidden /> {t("prod.variant.delete")}
        </Button>
      </fetcher.Form>
    </div>
  );
}

function PhotoButton({
  photo,
  op,
  label,
  icon: Icon,
}: {
  photo: string;
  op: string;
  label: string;
  icon: typeof Star;
}) {
  const fetcher = useFetcher();
  return (
    <fetcher.Form method="post">
      <input type="hidden" name="intent" value="photo_op" />
      <input type="hidden" name="photo" value={photo} />
      <input type="hidden" name="op" value={op} />
      <button
        type="submit"
        disabled={fetcher.state !== "idle"}
        className="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2 py-1 text-xs shadow hover:bg-white"
      >
        <Icon className="size-3" aria-hidden /> {label}
      </button>
    </fetcher.Form>
  );
}

export default function ProductEdit({ loaderData, actionData }: Route.ComponentProps) {
  const { product, categories, brands } = loaderData;
  const t = useT();
  const nav = useNavigation();
  const busy = (intent: string) => nav.state !== "idle" && nav.formData?.get("intent") === intent;
  const failed = actionData && !actionData.ok ? actionData : null;
  const errorsFor = (intent: string) => (failed?.intent === intent ? (failed.errors ?? {}) : {});
  const visible = product.variants.some((v) => v.available);

  return (
    <div className="max-w-5xl space-y-5">
      <Link to="/seller/products" className="text-brand-600 text-sm hover:underline">
        {t("prod.edit.back")}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <PageTitle subtitle={product.seller_name ?? undefined}>{product.name}</PageTitle>
          {visible ? (
            <Badge tone="success">{t("prod.visible")}</Badge>
          ) : (
            <Badge tone="muted">{t("prod.hidden")}</Badge>
          )}
        </div>
        {visible && product.slug && (
          <a
            href={`/product/${product.slug}`}
            target="_blank"
            rel="noreferrer"
            className="text-brand-700 inline-flex items-center gap-1.5 text-sm hover:underline"
          >
            <ExternalLink className="size-4" aria-hidden /> {t("prod.openOnSite")}
          </a>
        )}
      </div>

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">{t("prod.main")}</h2>
        <Form method="post" className="space-y-4">
          <input type="hidden" name="intent" value="product" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("prod.field.name")} error={errorsFor("product").name}>
              {(p) => <Input {...p} name="name" defaultValue={product.name} required maxLength={255} />}
            </Field>
            <Field label={t("prod.field.category")} error={errorsFor("product").category}>
              {(p) => (
                <Select {...p} name="category" defaultValue={product.category ?? ""}>
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
          <Field label={t("prod.field.description")}>
            {(p) => <Textarea {...p} name="description" rows={4} defaultValue={product.description ?? ""} />}
          </Field>
          <div className="flex items-center gap-2">
            <Button type="submit" loading={busy("product")}>
              <Save className="size-4" aria-hidden /> {t("prod.save")}
            </Button>
            {actionData?.ok && actionData.intent === "product" && (
              <span className="text-success text-sm">{t("prod.saved")}</span>
            )}
          </div>
        </Form>
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="font-semibold">{t("prod.photos")}</h2>
        {!product.photo && product.photos.length === 0 && (
          <p className="text-muted text-sm">{t("prod.photo.none")}</p>
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          {product.photo && (
            <figure className="border-brand-500 relative overflow-hidden rounded-xl border-2">
              <img src={product.photo} alt="" className="aspect-square w-full bg-white object-contain" />
              <figcaption className="absolute inset-x-1 bottom-1 flex flex-wrap items-center justify-between gap-1">
                <Badge>{t("prod.photo.main")}</Badge>
                <PhotoButton photo="main" op="delete" label={t("prod.photo.delete")} icon={Trash2} />
              </figcaption>
            </figure>
          )}
          {product.photos.map((ph) => (
            <figure key={ph.id} className="border-line relative overflow-hidden rounded-xl border">
              {ph.url && (
                <img
                  src={ph.url}
                  alt=""
                  loading="lazy"
                  className="aspect-square w-full bg-white object-contain"
                />
              )}
              <figcaption className="absolute inset-x-1 bottom-1 flex flex-wrap justify-between gap-1">
                <PhotoButton photo={String(ph.id)} op="main" label={t("prod.photo.makeMain")} icon={Star} />
                <PhotoButton photo={String(ph.id)} op="delete" label={t("prod.photo.delete")} icon={Trash2} />
              </figcaption>
            </figure>
          ))}
        </div>
        <Form method="post" encType="multipart/form-data" className="flex flex-wrap items-end gap-3">
          <input type="hidden" name="intent" value="photos" />
          <Field
            label={t("prod.field.photos")}
            hint={t("prod.field.photosHint")}
            error={errorsFor("photos").photo}
          >
            {(p) => (
              <Input
                {...p}
                name="photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                required
                className="py-2"
              />
            )}
          </Field>
          <Button type="submit" variant="secondary" loading={busy("photos")}>
            <ImagePlus className="size-4" aria-hidden /> {t("prod.photo.upload")}
          </Button>
        </Form>
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="font-semibold">{t("prod.variants.title")}</h2>
        {product.variants.map((v, i) => (
          <VariantCard key={v.id} variant={v} brands={brands} index={i} />
        ))}
        <details
          className="border-line rounded-xl border border-dashed p-4"
          open={failed?.intent === "add_variant"}
        >
          <summary className="cursor-pointer font-medium">{t("prod.variant.add")}</summary>
          <Form method="post" className="mt-4 space-y-3">
            <input type="hidden" name="intent" value="add_variant" />
            <VariantFields brands={brands} errors={errorsFor("add_variant")} listId="brands-new" />
            <Button type="submit" size="sm" loading={busy("add_variant")}>
              <Plus className="size-3.5" aria-hidden /> {t("prod.variant.add")}
            </Button>
          </Form>
        </details>
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">{t("prod.danger")}</h2>
        {failed?.intent === "delete" && (
          <Alert tone="danger">{failed.errors?.form ?? failed.errors?.detail}</Alert>
        )}
        <Form method="post" onSubmit={(e) => !confirm(t("prod.deleteConfirm")) && e.preventDefault()}>
          <input type="hidden" name="intent" value="delete" />
          <Button type="submit" variant="ghost" className="text-danger" loading={busy("delete")}>
            <Trash2 className="size-4" aria-hidden /> {t("prod.delete")}
          </Button>
        </Form>
      </Card>
    </div>
  );
}
