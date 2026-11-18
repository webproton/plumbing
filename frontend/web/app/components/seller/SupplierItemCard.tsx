import { EyeOff, ExternalLink, ImageOff, Link2, Package, Plus, X } from "lucide-react";
import { useState } from "react";
import { Form, useNavigation } from "react-router";

import { VariantPicker } from "~/components/seller/VariantPicker";
import { Badge, Button, ButtonLink } from "~/components/ui";
import { Link, useLang, useT } from "~/i18n/react";
import { formatDateTime, formatPrice, formatQty } from "~/lib/format";
import type { SupplierItemRow } from "~/lib/types";

export interface SupplierItemDetail extends SupplierItemRow {
  description: string;
  photos: string[];
  our_cost: string | null;
  product: number | null;
  first_seen_at: string;
  last_seen_at: string;
}

/**
 * Карточка позиции поставщика (что пришло в прайсе): все фото, описание, характеристики, цены, остаток.
 * Действия — те же, что в списке: «Створити товар», «Зв'язати з наявним», «Пропустити»; уже товар — «Відкрити товар».
 */
export function SupplierItemCard({ item, closeTo }: { item: SupplierItemDetail; closeTo: string }) {
  const t = useT();
  const lang = useLang();
  const busy = useNavigation().state === "submitting";
  const [photo, setPhoto] = useState(0);
  const [linking, setLinking] = useState(false);
  const photos = item.photos ?? [];
  const params = Object.entries(item.params ?? {});
  const foreign = item.currency && item.currency !== "UAH" ? ` ${item.currency}` : "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-3 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-label={item.name}
    >
      <div className="w-full max-w-4xl space-y-5 rounded-2xl bg-white p-4 shadow-xl sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold break-words">{item.name || item.external_id}</h2>
            <p className="text-muted text-sm">
              {[item.sku && `${t("itm.sku")}: ${item.sku}`, item.barcode, item.brand, item.category_name]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              {item.status === "linked" && <Badge tone="success">{t("search.sources.inCatalog")}</Badge>}
              {item.status === "ignored" && <Badge>{t("search.sources.ignored")}</Badge>}
              {item.missing && <Badge tone="danger">{t("src.item.missing")}</Badge>}
            </div>
          </div>
          <ButtonLink to={closeTo} preventScrollReset variant="ghost" aria-label={t("itm.close")}>
            <X className="size-5" aria-hidden />
          </ButtonLink>
        </div>

        <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-2">
            {photos.length ? (
              <>
                <img
                  src={photos[photo]}
                  alt={item.name}
                  referrerPolicy="no-referrer"
                  className="border-line aspect-square w-full rounded-xl border object-contain"
                />
                {photos.length > 1 && (
                  <div className="flex flex-wrap gap-2">
                    {photos.map((url, i) => (
                      <button
                        key={url}
                        type="button"
                        onClick={() => setPhoto(i)}
                        aria-label={t("itm.photo", { n: i + 1 })}
                        className={`size-16 overflow-hidden rounded-lg border-2 ${i === photo ? "border-brand-500" : "border-line"}`}
                      >
                        <img
                          src={url}
                          alt=""
                          loading="lazy"
                          referrerPolicy="no-referrer"
                          className="size-full object-contain"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="bg-surface text-muted grid aspect-square w-full place-items-center rounded-xl">
                <ImageOff className="size-10" aria-hidden />
              </div>
            )}
          </div>

          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-3 text-base">
              <div className="bg-surface rounded-xl p-3">
                <dt className="text-muted text-sm">{t("itm.cost")}</dt>
                <dd className="text-lg font-semibold">{item.our_cost ? formatPrice(item.our_cost) : "—"}</dd>
              </div>
              <div className="bg-surface rounded-xl p-3">
                <dt className="text-muted text-sm">{t("itm.sale")}</dt>
                <dd className="text-lg font-semibold">
                  {item.our_price ? formatPrice(item.our_price) : "—"}
                </dd>
              </div>
              <div className="bg-surface rounded-xl p-3">
                <dt className="text-muted text-sm">{t("itm.rrp")}</dt>
                <dd className="font-semibold">{item.price ? `${formatPrice(item.price)}${foreign}` : "—"}</dd>
              </div>
              <div className="bg-surface rounded-xl p-3">
                <dt className="text-muted text-sm">{t("itm.stock")}</dt>
                <dd className="font-semibold">
                  {item.quantity != null
                    ? formatQty(item.quantity)
                    : item.available === true
                      ? t("src.item.inStock")
                      : item.available === false
                        ? t("src.item.outOfStock")
                        : "—"}
                </dd>
              </div>
            </dl>
            <p className="text-muted text-xs">
              {t("itm.updated", { date: formatDateTime(item.last_seen_at, lang) })}
            </p>

            <div className="flex flex-wrap gap-2">
              {item.product ? (
                <ButtonLink to={`/seller/products/${item.product}`}>
                  <Package className="size-4" aria-hidden /> {t("search.sources.openProduct")}
                </ButtonLink>
              ) : (
                <>
                  <Form method="post" preventScrollReset>
                    <input type="hidden" name="intent" value="publish" />
                    <input type="hidden" name="ids" value={item.id} />
                    <Button type="submit" loading={busy}>
                      <Plus className="size-4" aria-hidden /> {t("prod.suppliers.create")}
                    </Button>
                  </Form>
                  <Button type="button" variant="secondary" onClick={() => setLinking(!linking)}>
                    <Link2 className="size-4" aria-hidden /> {t("itm.link")}
                  </Button>
                  {item.status !== "ignored" && (
                    <Form method="post" preventScrollReset>
                      <input type="hidden" name="intent" value="ignored" />
                      <input type="hidden" name="ids" value={item.id} />
                      <Button type="submit" variant="ghost">
                        <EyeOff className="size-4" aria-hidden /> {t("itm.skip")}
                      </Button>
                    </Form>
                  )}
                </>
              )}
              {item.url && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-brand-600 inline-flex items-center gap-1 self-center text-sm hover:underline"
                >
                  <ExternalLink className="size-4" aria-hidden /> {t("itm.onSupplierSite")}
                </a>
              )}
            </div>
            {linking && (
              <Form method="post" preventScrollReset className="bg-brand-50/60 space-y-2 rounded-xl p-3">
                <input type="hidden" name="intent" value="link" />
                <input type="hidden" name="item" value={item.id} />
                <p className="text-sm font-medium">{t("src.link.title", { name: item.name })}</p>
                <VariantPicker name="variant" />
                <Button type="submit" size="sm" loading={busy}>
                  <Link2 className="size-3.5" aria-hidden /> {t("src.link")}
                </Button>
              </Form>
            )}
          </div>
        </div>

        {item.description && (
          <section className="space-y-2">
            <h3 className="font-semibold">{t("itm.description")}</h3>
            <p className="text-base whitespace-pre-line">{item.description}</p>
          </section>
        )}
        {params.length > 0 && (
          <section className="space-y-2">
            <h3 className="font-semibold">{t("itm.params")}</h3>
            <dl className="divide-line border-line divide-y rounded-xl border">
              {params.map(([name, value]) => (
                <div
                  key={name}
                  className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 px-3 py-2 text-sm"
                >
                  <dt className="text-muted">{name}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
        <div className="text-right">
          <Link to={closeTo} preventScrollReset className="text-brand-600 text-sm hover:underline">
            {t("itm.close")}
          </Link>
        </div>
      </div>
    </div>
  );
}
