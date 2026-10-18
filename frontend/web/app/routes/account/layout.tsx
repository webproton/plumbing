import { LogOut, Package, UserRound } from "lucide-react";
import { Form, Outlet } from "react-router";

import { NavLink, useLocalPath, useT } from "~/i18n/react";

import { requireUser } from "~/lib/auth.server";

import type { Route } from "./+types/layout";

export function loader({ request, context }: Route.LoaderArgs) {
  return { user: requireUser(request, context) };
}

export default function AccountLayout({ loaderData }: Route.ComponentProps) {
  const t = useT();
  const local = useLocalPath();
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "hover:bg-brand-50"}`;
  return (
    <div className="grid gap-6 md:grid-cols-[14rem_1fr]">
      <aside className="space-y-1 self-start rounded-2xl border border-line bg-white p-3">
        <p className="truncate px-3 pb-2 text-sm text-muted">{loaderData.user.name || loaderData.user.email}</p>
        <NavLink to="/account" end className={link}>
          <UserRound className="size-4" aria-hidden /> {t("account.profile")}
        </NavLink>
        <NavLink to="/account/orders" className={link}>
          <Package className="size-4" aria-hidden /> {t("account.orders")}
        </NavLink>
        <Form method="post" action={local("/logout")}>
          <button type="submit" className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-muted hover:bg-brand-50 hover:text-ink">
            <LogOut className="size-4" aria-hidden /> {t("account.logout")}
          </button>
        </Form>
      </aside>
      <section>
        <Outlet />
      </section>
    </div>
  );
}
