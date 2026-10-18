import {
  ArrowLeftRight,
  Building2,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Lock,
  PackageSearch,
  ScanBarcode,
  Truck,
  Warehouse,
} from "lucide-react";
import { Outlet, useRouteLoaderData } from "react-router";

import { EmptyState } from "~/components/ui";
import { tFromMatches, type TKey } from "~/i18n";
import { NavLink, useT } from "~/i18n/react";
import { requireSeller } from "~/lib/seller.server";
import type { WarehouseMe } from "~/lib/types";

import type { Route } from "./+types/layout";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("wh.title") },
  { name: "robots", content: "noindex" },
];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const me = await api.get<WarehouseMe>("/warehouse/me/");
  return { me };
}

/** Данные кабинета (роль, склады продавца) для вложенных страниц */
export function useSellerMe(): WarehouseMe {
  const data = useRouteLoaderData<typeof loader>("routes/seller/layout");
  if (!data) throw new Error("useSellerMe used outside of /seller");
  return data.me;
}

const NAV: { to: string; label: TKey; icon: typeof Warehouse; end?: boolean }[] = [
  { to: "/seller", label: "wh.nav.overview", icon: LayoutDashboard, end: true },
  { to: "/seller/stock", label: "wh.nav.stock", icon: PackageSearch },
  { to: "/seller/documents", label: "wh.nav.documents", icon: FileText },
  { to: "/seller/operations", label: "wh.nav.operations", icon: ArrowLeftRight },
  { to: "/seller/scanner", label: "wh.nav.scanner", icon: ScanBarcode },
  { to: "/seller/movements", label: "wh.nav.movements", icon: ClipboardList },
  { to: "/seller/warehouses", label: "wh.nav.warehouses", icon: Building2 },
  { to: "/seller/suppliers", label: "wh.nav.suppliers", icon: Truck },
];

export default function SellerLayout({ loaderData }: Route.ComponentProps) {
  const { me } = loaderData;
  const t = useT();

  if (!me.is_staff_user) {
    return me.seller_pending ? (
      <EmptyState icon={Lock} title={t("wh.pending.title")}>
        {t("wh.pending.text")}
      </EmptyState>
    ) : (
      <EmptyState icon={Lock} title={t("wh.noAccess.title")}>
        {t("wh.noAccess.text")}
      </EmptyState>
    );
  }

  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "hover:bg-brand-50"}`;

  return (
    <div className="grid gap-6 lg:grid-cols-[14rem_1fr]">
      <aside className="self-start rounded-2xl border border-line bg-white p-3 lg:sticky lg:top-24">
        <p className="truncate px-3 pb-2 text-sm font-semibold">{me.seller?.shop_name ?? t("wh.admin")}</p>
        <nav className="flex gap-1 overflow-x-auto lg:flex-col" aria-label={t("wh.title")}>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={link}>
              <Icon className="size-4 shrink-0" aria-hidden /> {t(label)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <section className="min-w-0">
        <Outlet />
      </section>
    </div>
  );
}
