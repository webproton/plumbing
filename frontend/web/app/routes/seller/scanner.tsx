import { CheckCircle2, Link2, Minus, PackagePlus, Plus, ScanBarcode, Store, TriangleAlert, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { data, Link, useFetcher, useSearchParams } from "react-router";

import { CameraScanner } from "~/components/seller/CameraScanner";
import { VariantPicker } from "~/components/seller/VariantPicker";
import { Alert, Badge, Button, Card, Field, Input, PageTitle, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatPrice, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { InvoiceDoc, ManageOrder, Money, Paginated, ScanCard } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/scanner";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.scanner") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const docs = await api
    .get<Paginated<InvoiceDoc>>("/warehouse/inventory-documents/", { query: { page_size: 100 } })
    .catch(() => null);
  return { openDocs: (docs?.results ?? []).filter((d) => !d.processed) };
}

type ScanResult =
  | { ts: number; intent: "find"; found: true; card: ScanCard }
  | { ts: number; intent: "find" | "receive"; found: false; code: string }
  | { ts: number; intent: "receive"; found: true; name: string; sku: string | null; docQty: string; code: string }
  | { ts: number; intent: "create"; found: true; card: ScanCard }
  | { ts: number; intent: "attach"; found: true; card: ScanCard; code: string; docQty: string | null }
  | { ts: number; intent: "count"; found: true; changed: boolean; name: string }
  | { ts: number; intent: "sell"; found: true; orderId: number; total: Money | null };

const num = (v: string | undefined) => (v ?? "").replace(/\s/g, "").replace(",", ".");

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const v = formObject(await request.formData());
  const ts = Date.now();
  const code = (v.code ?? "").trim();
  try {
    if (v.intent === "find") {
      const card = await api.post<ScanCard>("/warehouse/stock-movements/find_by_barcode_or_sku/", {
        query: code,
        warehouse: Number(v.warehouse) || undefined,
      });
      return { ts, intent: "find", found: true, card } satisfies ScanResult;
    }
    if (v.intent === "receive") {
      const r = await api.post<{ name: string; sku: string | null; current_doc_qty: string }>(
        `/warehouse/inventory-documents/${Number(v.document)}/scan/`,
        { barcode: code, warehouse: Number(v.warehouse) },
      );
      return { ts, intent: "receive", found: true, name: r.name, sku: r.sku, docQty: r.current_doc_qty, code } satisfies ScanResult;
    }
    if (v.intent === "attach") {
      // заводской штрихкод → к товару из базы; в «Приёмке» товар сразу добавляется в накладную
      const card = await api.post<ScanCard>("/warehouse/stock-movements/attach_barcode/", {
        variant: Number(v.variant),
        code,
      });
      let docQty: string | null = null;
      if (v.document) {
        const r = await api.post<{ current_doc_qty: string }>(`/warehouse/inventory-documents/${Number(v.document)}/scan/`, {
          barcode: code,
          warehouse: Number(v.warehouse),
        });
        docQty = r.current_doc_qty;
      }
      return { ts, intent: "attach", found: true, card, code, docQty } satisfies ScanResult;
    }
    if (v.intent === "create") {
      const card = await api.post<ScanCard>("/warehouse/stock-movements/create_and_add/", {
        barcode: code,
        name: v.name,
        price: num(v.price) || 0,
        cost_price: num(v.cost_price) || 0,
        quantity: num(v.quantity) || 1,
        document: Number(v.document) || undefined,
        warehouse: Number(v.warehouse) || undefined,
      });
      return { ts, intent: "create", found: true, card } satisfies ScanResult;
    }
    if (v.intent === "sell") {
      // касса на точке: продажа без покупателя — оплачено, завершено, товар списан со склада
      const order = await api.post<ManageOrder>("/orders/manage/pos-sale/", {
        lines: JSON.parse(v.lines || "[]"),
        payment_method: v.payment_method,
        discount_percent: Number(v.discount) || 0,
      });
      return { ts, intent: "sell", found: true, orderId: order.id, total: order.total_price } satisfies ScanResult;
    }
    if (v.intent === "count") {
      const r = await api.post<{ changed: boolean }>("/warehouse/stock-movements/inventory/", {
        variant: Number(v.variant),
        warehouse: Number(v.warehouse),
        quantity: num(v.counted),
      });
      return { ts, intent: "count", found: true, changed: r.changed, name: v.name ?? "" } satisfies ScanResult;
    }
  } catch (e) {
    if (e instanceof ApiError && e.status === 404 && (v.intent === "find" || v.intent === "receive")) {
      return { ts, intent: v.intent, found: false, code } satisfies ScanResult;
    }
    if (e instanceof ApiError) return data({ ts, error: Object.values(e.fieldErrors)[0] ?? t("error.generic") }, { status: 400 });
    throw e;
  }
  return data({ ts, error: t("error.generic") }, { status: 400 });
}

const MODES = ["find", "sell", "receive", "count"] as const;
type Mode = (typeof MODES)[number];

const DISCOUNTS = [0, 1, 2, 3, 4, 5] as const;
const PAYMENTS = ["cash", "card", "iban"] as const;
type Payment = (typeof PAYMENTS)[number];

interface SaleLine {
  variant_id: number;
  name: string;
  sku: string | null;
  price: Money;
  qty: number;
  available: Money;
}

/** Цена со скидкой — как на сервере: скидка в цене каждой позиции, копейки округляются */
const unitCents = (price: Money, discount: number) => Math.round((Number(price) * 100 * (100 - discount)) / 100);
const saleTotal = (lines: SaleLine[], discount: number) =>
  lines.reduce((sum, l) => sum + unitCents(l.price, discount) * l.qty, 0) / 100;

interface LogEntry {
  ts: number;
  tone: "success" | "danger" | "info";
  text: string;
}

export default function Scanner({ loaderData }: Route.ComponentProps) {
  const { openDocs } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const [params, setParams] = useSearchParams();
  const mode = (MODES.includes(params.get("mode") as Mode) ? params.get("mode") : "find") as Mode;
  const fetcher = useFetcher<ScanResult | { ts: number; error: string }>();
  const inputRef = useRef<HTMLInputElement>(null);
  const [warehouse, setWarehouse] = useState(String(me.warehouses.find((w) => w.is_default)?.id ?? me.warehouses[0]?.id ?? ""));
  const [documentId, setDocumentId] = useState(String(openDocs[0]?.id ?? ""));
  const [code, setCode] = useState("");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [unknown, setUnknown] = useState<string | null>(null); // штрихкод, которого нет в базе
  const [card, setCard] = useState<ScanCard | null>(null);
  const [seenTs, setSeenTs] = useState(0);
  const [sale, setSale] = useState<SaleLine[]>([]);
  const [discount, setDiscount] = useState(0);
  const [payment, setPayment] = useState<Payment | "">("");
  const [lastSale, setLastSale] = useState<{ id: number; total: Money | null } | null>(null);

  const submitCode = (value: string) => {
    const c = value.trim();
    if (!c) return;
    setUnknown(null);
    // «Приёмка» добавляет в накладную, «Поиск» и «Инвентаризация» сначала находят товар
    fetcher.submit({ intent: mode === "receive" ? "receive" : "find", code: c, warehouse, document: documentId }, { method: "post" });
    setCode("");
  };

  // Применяем новый ответ сервера к состоянию (паттерн «состояние из предыдущего рендера»: без эффекта)
  const result = fetcher.data;
  if (result && result.ts !== seenTs) {
    setSeenTs(result.ts);
    const push = (tone: LogEntry["tone"], text: string) => setLog((l) => [{ ts: result.ts, tone, text }, ...l].slice(0, 30));
    const addToSale = (found: ScanCard) => {
      if (found.price == null) {
        push("danger", t("wh.sale.noPrice", { name: found.name }));
        return;
      }
      const price = found.price;
      setLastSale(null);
      setSale((lines) =>
        lines.some((l) => l.variant_id === found.variant_id)
          ? lines.map((l) => (l.variant_id === found.variant_id ? { ...l, qty: l.qty + 1 } : l))
          : [...lines, { variant_id: found.variant_id, name: found.name, sku: found.sku, price, qty: 1, available: found.available }],
      );
      push("success", t("wh.sale.added", { name: found.name }));
    };
    if ("error" in result) {
      push("danger", result.error);
    } else if (result.intent === "find" && mode === "sell") {
      setUnknown(result.found ? null : result.code);
      if (result.found) addToSale(result.card);
      else push("danger", t("wh.scan.notFound", { code: result.code }));
    } else if (result.intent === "sell") {
      setSale([]);
      setDiscount(0);
      setPayment("");
      setLastSale({ id: result.orderId, total: result.total });
      push("success", t("wh.sale.done", { id: result.orderId, total: formatPrice(result.total) }));
    } else if (result.intent === "find") {
      setCard(result.found ? result.card : null);
      setUnknown(result.found ? null : result.code);
      if (!result.found) push("danger", t("wh.scan.notFound", { code: result.code }));
    } else if (result.intent === "receive") {
      if (result.found) push("success", t("wh.scan.received", { name: result.name, qty: formatQty(result.docQty) }));
      else {
        setUnknown(result.code);
        push("danger", t("wh.scan.notFound", { code: result.code }));
      }
    } else if (result.intent === "attach") {
      setUnknown(null);
      if (mode === "find") setCard(result.card);
      push("success", t("wh.scan.attached", { code: result.code, name: result.card.name }));
      if (mode === "sell") addToSale(result.card);
      if (result.docQty) push("success", t("wh.scan.received", { name: result.card.name, qty: formatQty(result.docQty) }));
    } else if (result.intent === "create") {
      setUnknown(null);
      push("success", t("wh.scan.created", { name: result.card.name }));
      if (mode === "sell") addToSale(result.card);
    } else if (result.intent === "count") {
      setCard(null);
      push("success", `${result.name}: ${result.changed ? t("wh.scan.countFixed") : t("wh.scan.countSame")}`);
    }
  }

  // после каждого ответа возвращаем фокус в поле — следующий скан без мыши
  useEffect(() => {
    if (fetcher.state === "idle") inputRef.current?.focus();
  }, [fetcher.state, seenTs]);

  const busy = fetcher.state !== "idle";

  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("wh.scan.subtitle")} help="scanner">{t("wh.nav.scanner")}</PageTitle>

      <div role="tablist" className="flex flex-wrap gap-2">
        {MODES.map((m) => (
          <button
            key={m}
            role="tab"
            type="button"
            aria-selected={m === mode}
            onClick={() => {
              setCard(null);
              setUnknown(null);
              setParams({ mode: m }, { replace: true, preventScrollReset: true });
            }}
            className={`rounded-xl border px-3.5 py-2 text-sm font-medium ${m === mode ? "border-brand-500 bg-brand-50 text-brand-700" : "border-line bg-white hover:border-brand-500"}`}
          >
            {t(`wh.scan.mode.${m}` as TKey)}
          </button>
        ))}
      </div>

      <Card className="space-y-4 p-5">
        <p className="text-sm text-muted">{t(`wh.scan.mode.${mode}.hint` as TKey)}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("wh.col.warehouse")}>
            {(p) => (
              <Select {...p} value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
                {me.warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {mode === "receive" && (
            <Field label={t("wh.scan.document")} error={openDocs.length === 0 ? t("wh.scan.noDocs") : undefined}>
              {(p) => (
                <Select {...p} value={documentId} onChange={(e) => setDocumentId(e.target.value)}>
                  {openDocs.map((d) => (
                    <option key={d.id} value={d.id}>
                      #{d.id} {d.document_number ? `№${d.document_number}` : ""} {d.supplier_name ?? ""}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitCode(code);
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <ScanBarcode className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-muted" aria-hidden />
            <Input
              ref={inputRef}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={t("wh.scan.placeholder")}
              aria-label={t("wh.col.barcode")}
              autoFocus
              autoComplete="off"
              inputMode="text"
              className="h-12 pl-10 text-lg"
            />
          </div>
          <Button type="submit" size="lg" loading={busy} disabled={mode === "receive" && !documentId}>
            OK
          </Button>
        </form>

        <CameraScanner onScan={(c) => submitCode(c)} />
      </Card>

      {unknown && mode !== "count" && (
        <AttachBarcode
          code={unknown}
          busy={busy}
          onSubmit={(variant) =>
            fetcher.submit(
              { intent: "attach", variant, code: unknown, warehouse, document: mode === "receive" ? documentId : "" },
              { method: "post" },
            )
          }
        />
      )}
      {unknown && mode !== "count" && (
        <CreateProduct
          code={unknown}
          warehouse={warehouse}
          documentId={mode === "receive" ? documentId : ""}
          onSubmit={(fields) => fetcher.submit({ intent: "create", ...fields }, { method: "post" })}
          busy={busy}
        />
      )}

      {mode === "sell" && (
        <SaleCard
          lines={sale}
          discount={discount}
          payment={payment}
          lastSale={lastSale}
          busy={busy}
          onQty={(id, qty) => setSale((lines) => lines.map((l) => (l.variant_id === id ? { ...l, qty: Math.max(1, qty) } : l)))}
          onRemove={(id) => setSale((lines) => lines.filter((l) => l.variant_id !== id))}
          onClear={() => setSale([])}
          onDiscount={setDiscount}
          onPayment={setPayment}
          onSubmit={() =>
            fetcher.submit(
              {
                intent: "sell",
                lines: JSON.stringify(sale.map((l) => ({ variant: l.variant_id, quantity: l.qty }))),
                payment_method: payment,
                discount: String(discount),
              },
              { method: "post" },
            )
          }
        />
      )}

      {card && mode === "find" && <ProductCard card={card} />}
      {card && mode === "count" && (
        <CountForm
          card={card}
          busy={busy}
          onSubmit={(counted) =>
            fetcher.submit({ intent: "count", variant: String(card.variant_id), warehouse, counted, name: card.name }, { method: "post" })
          }
        />
      )}

      {log.length > 0 && (
        <ul className="space-y-1.5" aria-live="polite">
          {log.map((l) => (
            <li key={l.ts} className={`flex items-start gap-2 rounded-xl px-3 py-2 text-sm ${l.tone === "success" ? "bg-success/10 text-success" : "bg-danger/10 text-danger"}`}>
              {l.tone === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /> : <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />}
              {l.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SaleCard(props: {
  lines: SaleLine[];
  discount: number;
  payment: Payment | "";
  lastSale: { id: number; total: Money | null } | null;
  busy: boolean;
  onQty: (variantId: number, qty: number) => void;
  onRemove: (variantId: number) => void;
  onClear: () => void;
  onDiscount: (discount: number) => void;
  onPayment: (payment: Payment) => void;
  onSubmit: () => void;
}) {
  const { lines, discount, payment, lastSale, busy } = props;
  const t = useT();
  const chip = (active: boolean) =>
    `rounded-xl border px-3.5 py-2 text-sm font-medium ${active ? "border-brand-500 bg-brand-50 text-brand-700" : "border-line bg-white hover:border-brand-500"}`;
  const full = lines.reduce((sum, l) => sum + Number(l.price) * l.qty, 0);
  const total = saleTotal(lines, discount);
  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Store className="size-5" aria-hidden />
          {t("wh.sale.title")}
        </h2>
        {lines.length > 0 && (
          <Button variant="ghost" size="sm" onClick={props.onClear}>
            {t("wh.sale.clear")}
          </Button>
        )}
      </div>

      {lastSale && lines.length === 0 && (
        <Alert tone="success">
          {t("wh.sale.done", { id: lastSale.id, total: formatPrice(lastSale.total) })}{" "}
          <Link to={`/seller/orders/${lastSale.id}`} className="font-medium underline">
            {t("wh.sale.openOrder")}
          </Link>
        </Alert>
      )}

      {lines.length === 0 ? (
        <p className="text-muted text-sm">{t("wh.sale.empty")}</p>
      ) : (
        <ul className="divide-line divide-y">
          {lines.map((l) => (
            <li key={l.variant_id} className="flex flex-wrap items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{l.name}</p>
                <p className="text-muted text-xs">
                  {[l.sku, formatPrice(l.price)].filter(Boolean).join(" · ")}
                  {Number(l.available) < l.qty && (
                    <span className="text-danger"> · {t("wh.sale.stockLow", { qty: formatQty(l.available) })}</span>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Button variant="secondary" size="sm" aria-label="−1" onClick={() => props.onQty(l.variant_id, l.qty - 1)}>
                  <Minus className="size-4" aria-hidden />
                </Button>
                <Input
                  value={String(l.qty)}
                  onChange={(e) => props.onQty(l.variant_id, Number(e.target.value.replace(/\D/g, "")) || 1)}
                  inputMode="numeric"
                  aria-label={t("wh.col.qty")}
                  className="w-16 text-center"
                />
                <Button variant="secondary" size="sm" aria-label="+1" onClick={() => props.onQty(l.variant_id, l.qty + 1)}>
                  <Plus className="size-4" aria-hidden />
                </Button>
              </div>
              <p className="w-24 text-right font-medium whitespace-nowrap">{formatPrice(String((unitCents(l.price, discount) * l.qty) / 100))}</p>
              <Button variant="ghost" size="sm" aria-label={t("wh.sale.remove")} onClick={() => props.onRemove(l.variant_id)}>
                <X className="size-4" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2">
        <p className="text-sm font-medium">{t("wh.sale.discount")}</p>
        <div className="flex flex-wrap gap-2">
          {DISCOUNTS.map((d) => (
            <button key={d} type="button" aria-pressed={d === discount} className={chip(d === discount)} onClick={() => props.onDiscount(d)}>
              {d === 0 ? t("wh.sale.noDiscount") : `−${d} %`}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">{t("wh.sale.payment")}</p>
        <div className="flex flex-wrap gap-2">
          {PAYMENTS.map((p) => (
            <button key={p} type="button" aria-pressed={p === payment} className={chip(p === payment)} onClick={() => props.onPayment(p)}>
              {t(`wh.sale.pay.${p}` as TKey)}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <div>
          <p className="text-muted text-sm">{t("wh.sale.total")}</p>
          <p className="text-2xl font-semibold">{formatPrice(String(total))}</p>
          {discount > 0 && lines.length > 0 && (
            <p className="text-muted text-xs line-through">{formatPrice(String(full))}</p>
          )}
        </div>
        <Button size="lg" loading={busy} disabled={lines.length === 0 || !payment} onClick={props.onSubmit}>
          {payment ? t("wh.sale.submit") : t("wh.sale.choosePayment")}
        </Button>
      </div>
    </Card>
  );
}

function ProductCard({ card }: { card: ScanCard }) {
  const t = useT();
  return (
    <Card className="flex gap-4 p-5">
      {card.photo && <img src={card.photo} alt="" className="size-24 rounded-xl bg-surface object-contain" />}
      <div className="flex-1 space-y-2">
        <h2 className="text-lg font-semibold">{card.name}</h2>
        <p className="text-sm text-muted">{[card.sku, card.barcode].filter(Boolean).join(" · ")}</p>
        <div className="flex flex-wrap gap-2">
          <Badge tone="success">{t("wh.scan.onWarehouse", { qty: formatQty(card.stock_current ?? card.stock_total) })}</Badge>
          <Badge tone="muted">{t("wh.scan.total", { qty: formatQty(card.stock_total) })}</Badge>
          {Number(card.reserved) > 0 && <Badge tone="info">{t("wh.scan.reservedQty", { qty: formatQty(card.reserved) })}</Badge>}
        </div>
        <p className="text-sm">
          {t("wh.col.cost")}: <b>{formatPrice(card.cost_price)}</b> · {t("wh.col.price")}: <b>{formatPrice(card.price)}</b>
        </p>
      </div>
    </Card>
  );
}

function CountForm({ card, onSubmit, busy }: { card: ScanCard; onSubmit: (counted: string) => void; busy: boolean }) {
  const t = useT();
  const [counted, setCounted] = useState("");
  return (
    <Card className="space-y-3 p-5">
      <ProductCardInline card={card} />
      <form
        className="flex items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (counted.trim()) onSubmit(counted);
        }}
      >
        <Field label={t("wh.op.counted")}>
          {(p) => <Input {...p} value={counted} onChange={(e) => setCounted(e.target.value)} inputMode="decimal" autoFocus className="w-40" />}
        </Field>
        <Button type="submit" loading={busy}>
          {t("wh.op.inventory.submit")}
        </Button>
      </form>
    </Card>
  );
}

function ProductCardInline({ card }: { card: ScanCard }) {
  const t = useT();
  return (
    <div>
      <p className="font-semibold">{card.name}</p>
      <p className="text-sm text-muted">
        {t("wh.scan.onWarehouse", { qty: formatQty(card.stock_current ?? card.stock_total) })} · {[card.sku, card.barcode].filter(Boolean).join(" · ")}
      </p>
    </div>
  );
}

function AttachBarcode({ code, busy, onSubmit }: { code: string; busy: boolean; onSubmit: (variant: string) => void }) {
  const t = useT();
  const [variant, setVariant] = useState<string>("");
  return (
    <Alert tone="info">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (variant) onSubmit(variant);
        }}
      >
        <p className="flex items-center gap-2 font-semibold">
          <Link2 className="size-4" aria-hidden /> {t("wh.scan.attachTitle", { code })}
        </p>
        <p className="text-sm text-muted">{t("wh.scan.attachHint")}</p>
        <div className="flex flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">
            <VariantPicker name="variant" onSelect={(v) => setVariant(v ? String(v.id) : "")} />
          </div>
          <Button type="submit" size="sm" loading={busy} disabled={!variant}>
            {t("wh.scan.attach")}
          </Button>
        </div>
        <p className="text-sm text-muted">{t("wh.scan.orCreate")}</p>
      </form>
    </Alert>
  );
}

function CreateProduct({
  code,
  warehouse,
  documentId,
  onSubmit,
  busy,
}: {
  code: string;
  warehouse: string;
  documentId: string;
  onSubmit: (fields: Record<string, string>) => void;
  busy: boolean;
}) {
  const t = useT();
  return (
    <Alert tone="info">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
          onSubmit({ ...f, code, warehouse, document: documentId });
        }}
      >
        <p className="flex items-center gap-2 font-semibold">
          <PackagePlus className="size-4" aria-hidden /> {t("wh.scan.createTitle", { code })}
        </p>
        <div className="grid gap-3 sm:grid-cols-4">
          <Input name="name" required placeholder={t("wh.col.product")} aria-label={t("wh.col.product")} className="sm:col-span-2" />
          <Input name="cost_price" inputMode="decimal" placeholder={t("wh.col.cost")} aria-label={t("wh.col.cost")} />
          <Input name="price" inputMode="decimal" placeholder={t("wh.col.price")} aria-label={t("wh.col.price")} />
        </div>
        {documentId && <Input name="quantity" inputMode="decimal" defaultValue="1" aria-label={t("wh.col.qty")} className="w-32" />}
        <Button type="submit" size="sm" loading={busy}>
          {t("wh.scan.create")}
        </Button>
      </form>
    </Alert>
  );
}
