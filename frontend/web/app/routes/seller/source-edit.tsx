import { Save, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { data, Form, useNavigation } from "react-router";

import { INTERVALS } from "~/components/seller/imports";
import { Alert, Button, Card, Field, Input, PageTitle, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";
import type { AuthType, Category, ImportSource, SiteAdapterInfo, SourceKind, Supplier } from "~/lib/types";

import type { Route } from "./+types/source-edit";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("src.nav") }];

const MAP_FIELDS = [
  "sku", "name", "price", "cost", "quantity", "available", "barcode", "old_price",
  "category", "brand", "photos", "description", "currency", "external_id",
] as const; // prettier-ignore
const FILE_OPTIONS = ["delimiter", "encoding", "sheet", "items_tag"] as const;
const AUTH_TYPES: Exclude<AuthType, "login">[] = ["none", "basic", "bearer", "header", "query"];
const ROUNDING = [
  ["0.01", "src.round.cents"],
  ["1", "src.round.1"],
  ["5", "src.round.5"],
  ["10", "src.round.10"],
] as const;

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  try {
    const [source, suppliers, categories, adapters] = await Promise.all([
      params.id ? api.get<ImportSource>(`/imports/sources/${params.id}/`) : Promise.resolve(null),
      api.get<Supplier[]>("/warehouse/suppliers/"),
      api.get<Category[]>("/category/"),
      api.get<SiteAdapterInfo[]>("/imports/adapters/"),
    ]);
    return { source, suppliers: suppliers.filter((s) => s.is_active), categories, adapters };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

function collect(form: FormData, prefix: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of form.entries()) {
    if (key.startsWith(prefix) && typeof value === "string" && value.trim())
      out[key.slice(prefix.length)] = value.trim();
  }
  return out;
}

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const v = (name: string) => String(form.get(name) ?? "").trim();

  try {
    if (v("intent") === "delete" && params.id) {
      await api.delete(`/imports/sources/${params.id}/`);
      return localRedirect(request, "/seller/sources");
    }
    const kind = v("kind") as SourceKind;
    const options: Record<string, string | number> = collect(form, "opt.");
    if (options.max_pages) options.max_pages = Number(options.max_pages) || 1;
    const payload: Record<string, unknown> = {
      name: v("name"),
      kind,
      url: v("url"),
      format: v("format") || "auto",
      auth_type: kind === "web" ? "login" : v("auth_type") || "none",
      auth_login: v("auth_login"),
      adapter: kind === "web" ? v("adapter") : "",
      secret: String(form.get("secret") ?? ""),
      clear_secret: form.get("clear_secret") === "1",
      currency: v("currency") || "UAH",
      price_mode: v("price_mode") || "rrp",
      markup_percent: v("markup_percent") || "0",
      price_rounding: v("price_rounding") || "1",
      category: Number(v("category")) || null,
      supplier: Number(v("supplier")) || null,
      publish_new: form.get("publish_new") === "1",
      update_prices: form.get("update_prices") === "1",
      hide_when_unavailable: form.get("hide_when_unavailable") === "1",
      is_active: form.get("is_active") === "1",
      sync_interval_minutes: Number(v("sync_interval_minutes")) || 0,
      field_map: collect(form, "map."),
      options,
    };

    const file = form.get("file");
    let body: unknown = payload;
    if (file instanceof File && file.size > 0) {
      const multipart = new FormData();
      for (const [key, value] of Object.entries(payload)) {
        multipart.set(
          key,
          value === null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value),
        );
      }
      multipart.set("file", file);
      body = multipart;
    }

    if (params.id) {
      await api.patch(`/imports/sources/${params.id}/`, body, { timeoutMs: LONG_TIMEOUT });
      return localRedirect(request, `/seller/sources/${params.id}`);
    }
    const created = await api.post<ImportSource>("/imports/sources/", body, { timeoutMs: LONG_TIMEOUT });
    try {
      await api.post(`/imports/sources/${created.id}/sync/`);
    } catch (e) {
      if (!(e instanceof ApiError)) throw e; // источник создан; синхронизацию можно запустить со страницы
    }
    return localRedirect(request, `/seller/sources/${created.id}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors = e.fieldErrors;
    return data(
      { errors: Object.keys(errors).length ? errors : { form: t("error.generic") } },
      { status: 400 },
    );
  }
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="space-y-4 p-5">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </Card>
  );
}

function Check({ name, label, defaultChecked }: { name: string; label: string; defaultChecked: boolean }) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <input
        type="checkbox"
        name={name}
        value="1"
        defaultChecked={defaultChecked}
        className="accent-brand-600 mt-0.5 size-4"
      />
      {label}
    </label>
  );
}

export default function SourceEdit({ loaderData, actionData }: Route.ComponentProps) {
  const { source, suppliers, categories, adapters } = loaderData;
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const errors: Record<string, string> = actionData?.errors ?? {};
  const [kind, setKind] = useState<SourceKind>(source?.kind ?? "feed");
  const [auth, setAuth] = useState<AuthType>(source?.auth_type ?? "none");
  const [priceMode, setPriceMode] = useState(source?.price_mode ?? "rrp");
  const [adapterCode, setAdapterCode] = useState(source?.adapter || adapters[0]?.code || "");
  const adapter = adapters.find((a) => a.code === adapterCode);
  const opt = (name: string) => String(source?.options?.[name] ?? "");
  const otherErrors = Object.entries(errors).filter(
    ([k]) =>
      ![
        "name",
        "url",
        "file",
        "adapter",
        "markup_percent",
        "price_rounding",
        "sync_interval_minutes",
      ].includes(k),
  );

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <Link
          to={source ? `/seller/sources/${source.id}` : "/seller/sources"}
          className="text-brand-700 text-sm hover:underline"
        >
          ← {source?.name ?? t("src.nav")}
        </Link>
        <div className="mt-2">
          <PageTitle>
            {source ? t("src.form.editTitle", { name: source.name }) : t("src.form.newTitle")}
          </PageTitle>
        </div>
      </div>

      <Form method="post" encType="multipart/form-data" className="space-y-5">
        {otherErrors.length > 0 && (
          <Alert tone="danger">
            {otherErrors.map(([k, m]) => (
              <p key={k}>{k === "form" ? m : `${k}: ${m}`}</p>
            ))}
          </Alert>
        )}

        <Section title={t("src.form.main")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("src.form.name")} error={errors.name}>
              {(p) => <Input {...p} name="name" defaultValue={source?.name} required maxLength={150} />}
            </Field>
            <Field label={t("src.form.supplier")}>
              {(p) => (
                <Select {...p} name="supplier" defaultValue={source?.supplier ?? ""}>
                  <option value="">{t("src.form.noSupplier")}</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">{t("src.form.kind")}</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {(["feed", "api", "web"] as const).map((k) => (
                <label
                  key={k}
                  className={`cursor-pointer rounded-xl border p-3 text-sm ${kind === k ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-500"}`}
                >
                  <input
                    type="radio"
                    name="kind"
                    value={k}
                    checked={kind === k}
                    onChange={() => setKind(k)}
                    className="sr-only"
                  />
                  <span className="font-medium">{t(`src.kind.${k}` as TKey)}</span>
                  <span className="text-muted mt-1 block">{t(`src.kind.${k}Hint` as TKey)}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </Section>

        <Section title={t("src.form.where")}>
          {kind === "web" && (
            <Field label={t("src.form.adapter")} error={errors.adapter} hint={adapter?.description}>
              {(p) => (
                <Select
                  {...p}
                  name="adapter"
                  value={adapterCode}
                  onChange={(e) => setAdapterCode(e.target.value)}
                >
                  {adapters.map((a) => (
                    <option key={a.code} value={a.code}>
                      {a.title}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-[1fr_12rem]">
            <Field
              label={t(
                kind === "api" ? "src.form.apiUrl" : kind === "web" ? "src.form.siteUrl" : "src.form.url",
              )}
              error={errors.url}
            >
              {(p) => (
                <Input
                  {...p}
                  name="url"
                  type="url"
                  defaultValue={source?.url}
                  placeholder="https://"
                  required={kind === "api"}
                />
              )}
            </Field>
            {kind !== "api" && (
              <Field label={t("src.form.format")}>
                {(p) => (
                  <Select {...p} name="format" defaultValue={source?.format ?? "auto"}>
                    <option value="auto">{t("src.format.auto")}</option>
                    {["yml", "xml", "csv", "xlsx", "json"].map((f) => (
                      <option key={f} value={f}>
                        {f.toUpperCase()}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>
          {kind === "feed" && (
            <Field
              label={t("src.form.file")}
              error={errors.file}
              hint={source?.has_file ? t("src.form.currentFile", { name: source.file_name }) : undefined}
            >
              {(p) => (
                <Input
                  {...p}
                  name="file"
                  type="file"
                  accept=".xml,.yml,.csv,.xlsx,.xls,.json,.txt"
                  className="py-2"
                />
              )}
            </Field>
          )}
          {kind === "api" && (
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t("src.form.itemsPath")} hint={t("src.form.itemsPathHint")}>
                {(p) => <Input {...p} name="opt.items_path" defaultValue={opt("items_path")} />}
              </Field>
              <Field label={t("src.form.pageParam")} hint={t("src.form.pageParamHint")}>
                {(p) => <Input {...p} name="opt.page_param" defaultValue={opt("page_param")} />}
              </Field>
              <Field label={t("src.form.maxPages")}>
                {(p) => (
                  <Input
                    {...p}
                    name="opt.max_pages"
                    type="number"
                    min={1}
                    max={500}
                    defaultValue={opt("max_pages") || "100"}
                  />
                )}
              </Field>
            </div>
          )}
          {kind === "web" && adapter && (
            <div className="grid gap-4 sm:grid-cols-2">
              {Object.entries(adapter.options).map(([name, hint]) => (
                <Field key={name} label={hint}>
                  {(p) => <Input {...p} name={`opt.${name}`} defaultValue={opt(name)} />}
                </Field>
              ))}
            </div>
          )}
        </Section>

        <Section title={t("src.form.access")}>
          <div className="grid gap-4 sm:grid-cols-3">
            {kind !== "web" && (
              <Field label={t("src.form.authType")}>
                {(p) => (
                  <Select
                    {...p}
                    name="auth_type"
                    value={auth === "login" ? "none" : auth}
                    onChange={(e) => setAuth(e.target.value as AuthType)}
                  >
                    {AUTH_TYPES.map((a) => (
                      <option key={a} value={a}>
                        {t(`src.auth.${a}` as TKey)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {(kind === "web" || auth !== "none") && (
              <>
                {(kind === "web" || auth !== "bearer") && (
                  <Field
                    label={kind === "web" || auth === "basic" ? t("src.form.login") : t("src.form.keyName")}
                  >
                    {(p) => (
                      <Input {...p} name="auth_login" defaultValue={source?.auth_login} autoComplete="off" />
                    )}
                  </Field>
                )}
                <Field
                  label={t("src.form.secret")}
                  hint={source?.has_secret ? t("src.form.secretSaved") : undefined}
                >
                  {(p) => <Input {...p} name="secret" type="password" autoComplete="new-password" />}
                </Field>
              </>
            )}
          </div>
          {source?.has_secret && (
            <Check name="clear_secret" label={t("src.form.clearSecret")} defaultChecked={false} />
          )}
          <p className="text-muted text-xs">{t("src.form.secretNote")}</p>
        </Section>

        <Section title={t("src.form.prices")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("src.form.priceMode")}>
              {(p) => (
                <Select
                  {...p}
                  name="price_mode"
                  value={priceMode}
                  onChange={(e) => setPriceMode(e.target.value as "rrp" | "markup")}
                >
                  <option value="rrp">{t("src.price.rrp")}</option>
                  <option value="markup">{t("src.price.markup")}</option>
                </Select>
              )}
            </Field>
            <Field
              label={t("src.form.markup")}
              error={errors.markup_percent}
              hint={priceMode === "rrp" ? t("src.form.markupHint") : undefined}
            >
              {(p) => (
                <Input
                  {...p}
                  name="markup_percent"
                  type="number"
                  min={0}
                  max={1000}
                  step="0.01"
                  defaultValue={source?.markup_percent ?? "30"}
                />
              )}
            </Field>
            <Field label={t("src.form.rounding")} error={errors.price_rounding}>
              {(p) => (
                <Select
                  {...p}
                  name="price_rounding"
                  defaultValue={String(Number(source?.price_rounding ?? 1))}
                >
                  {ROUNDING.map(([value, label]) => (
                    <option key={value} value={value}>
                      {t(label)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("src.form.currency")} hint={t("src.form.currencyHint")}>
              {(p) => (
                <Select {...p} name="currency" defaultValue={source?.currency ?? "UAH"}>
                  {["UAH", "USD", "EUR"].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </Section>

        <Section title={t("src.form.behaviour")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("src.form.category")}>
              {(p) => (
                <Select {...p} name="category" defaultValue={source?.category ?? ""}>
                  <option value="">{t("src.form.noCategory")}</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("src.form.interval")} error={errors.sync_interval_minutes}>
              {(p) => (
                <Select {...p} name="sync_interval_minutes" defaultValue={source?.sync_interval_minutes ?? 0}>
                  {INTERVALS.map((m) => (
                    <option key={m} value={m}>
                      {t(`src.interval.${m}` as TKey)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="space-y-2">
            <Check
              name="publish_new"
              label={t("src.form.publishNew")}
              defaultChecked={source?.publish_new ?? false}
            />
            <Check
              name="update_prices"
              label={t("src.form.updatePrices")}
              defaultChecked={source?.update_prices ?? true}
            />
            <Check
              name="hide_when_unavailable"
              label={t("src.form.hide")}
              defaultChecked={source?.hide_when_unavailable ?? false}
            />
            <Check name="is_active" label={t("src.form.active")} defaultChecked={source?.is_active ?? true} />
          </div>
        </Section>

        <details className="border-line rounded-[var(--radius-card)] border bg-white p-5">
          <summary className="cursor-pointer font-semibold">{t("src.form.mapping")}</summary>
          <p className="text-muted mt-2 text-sm">{t("src.form.mappingHint")}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {MAP_FIELDS.map((f) => (
              <Field key={f} label={t(`src.field.${f}` as TKey)}>
                {(p) => <Input {...p} name={`map.${f}`} defaultValue={source?.field_map?.[f] ?? ""} />}
              </Field>
            ))}
          </div>
          {kind === "feed" && (
            <>
              <h3 className="mt-5 text-sm font-semibold">{t("src.form.advanced")}</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-4">
                {FILE_OPTIONS.map((o) => (
                  <Field key={o} label={t(`src.opt.${o}` as TKey)}>
                    {(p) => <Input {...p} name={`opt.${o}`} defaultValue={opt(o)} />}
                  </Field>
                ))}
              </div>
            </>
          )}
        </details>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button type="submit" loading={busy}>
            <Save className="size-4" aria-hidden /> {source ? t("src.form.save") : t("src.form.createSync")}
          </Button>
        </div>
      </Form>

      {source && (
        <Form method="post" onSubmit={(e) => !confirm(t("src.form.deleteConfirm")) && e.preventDefault()}>
          <input type="hidden" name="intent" value="delete" />
          <Button type="submit" variant="ghost" className="text-danger">
            <Trash2 className="size-4" aria-hidden /> {t("src.form.delete")}
          </Button>
        </Form>
      )}
    </div>
  );
}
