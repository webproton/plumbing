import { Heart, Menu, Phone, Search, ShoppingCart, User } from "lucide-react";
import { Form, Link, NavLink } from "react-router";

import type { Category } from "~/lib/types";

export interface HeaderProps {
  siteName: string;
  user: { email: string; name: string } | null;
  cartCount: number;
  categories: Category[];
  phone: string | null;
}

export function Header({ siteName, user, cartCount, categories, phone }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:gap-6">
        <details className="relative md:hidden">
          <summary className="grid size-10 cursor-pointer list-none place-items-center rounded-xl hover:bg-brand-50" aria-label="Меню">
            <Menu className="size-5" />
          </summary>
          <nav className="absolute top-12 left-0 w-64 rounded-xl border border-line bg-white p-2 shadow-xl">
            <MobileLink to="/catalog">Весь каталог</MobileLink>
            {categories.map((c) => (
              <MobileLink key={c.id} to={`/catalog?category=${c.slug}`}>
                {c.name}
              </MobileLink>
            ))}
            <hr className="my-2 border-line" />
            <MobileLink to="/delivery">Доставка и оплата</MobileLink>
            <MobileLink to="/contacts">Контакты</MobileLink>
          </nav>
        </details>

        <Link to="/" className="text-xl font-extrabold tracking-tight text-brand-700">
          {siteName}
        </Link>

        <nav className="hidden items-center gap-5 text-sm font-medium md:flex">
          <NavLink to="/catalog" className={({ isActive }) => (isActive ? "text-brand-600" : "hover:text-brand-600")}>
            Каталог
          </NavLink>
          <NavLink to="/delivery" className={({ isActive }) => (isActive ? "text-brand-600" : "hover:text-brand-600")}>
            Доставка
          </NavLink>
          <NavLink to="/contacts" className={({ isActive }) => (isActive ? "text-brand-600" : "hover:text-brand-600")}>
            Контакты
          </NavLink>
        </nav>

        <Form method="get" action="/catalog" role="search" className="relative ml-auto hidden flex-1 sm:block md:max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input
            name="search"
            type="search"
            placeholder="Поиск по названию или артикулу"
            aria-label="Поиск товаров"
            className="h-10 w-full rounded-xl border border-line bg-surface pr-3 pl-9 text-sm focus:border-brand-500 focus:outline-none"
          />
        </Form>

        <div className="ml-auto flex items-center gap-1 sm:ml-0">
          {phone && (
            <a href={`tel:${phone}`} className="hidden items-center gap-2 px-2 text-sm font-medium lg:flex">
              <Phone className="size-4 text-brand-600" aria-hidden />
              {phone}
            </a>
          )}
          <IconLink to="/catalog?focus=search" label="Поиск" className="sm:hidden">
            <Search className="size-5" />
          </IconLink>
          {user && (
            <IconLink to="/wishlist" label="Избранное">
              <Heart className="size-5" />
            </IconLink>
          )}
          <IconLink to={user ? "/account" : "/login"} label={user ? "Личный кабинет" : "Войти"}>
            <User className="size-5" />
          </IconLink>
          <IconLink to="/cart" label={`Корзина, товаров: ${cartCount}`}>
            <ShoppingCart className="size-5" />
            {cartCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 grid min-w-5 place-items-center rounded-full bg-brand-600 px-1 text-xs font-semibold text-white">
                {cartCount > 99 ? "99+" : cartCount}
              </span>
            )}
          </IconLink>
        </div>
      </div>
    </header>
  );
}

function IconLink({
  to,
  label,
  className = "",
  children,
}: {
  to: string;
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link to={to} aria-label={label} title={label} className={`relative grid size-10 place-items-center rounded-xl hover:bg-brand-50 ${className}`}>
      {children}
    </Link>
  );
}

function MobileLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} className="block rounded-lg px-3 py-2 text-sm hover:bg-brand-50">
      {children}
    </Link>
  );
}
