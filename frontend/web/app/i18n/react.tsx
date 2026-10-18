import { forwardRef } from "react";
import {
  Link as RRLink,
  NavLink as RRNavLink,
  useLocation,
  useRouteLoaderData,
  type LinkProps,
  type NavLinkProps,
} from "react-router";

import { localizePath, makeT, langFromPath, type Lang } from "./index";

export function useLang(): Lang {
  const data = useRouteLoaderData("root") as { lang?: Lang } | undefined;
  const { pathname } = useLocation();
  // если корневой загрузчик не отработал (ошибка в middleware) — язык берём из адреса
  return data?.lang ?? langFromPath(pathname);
}

export function useT() {
  return makeT(useLang());
}

/** Внутренний путь с префиксом текущего языка */
export function useLocalPath() {
  const lang = useLang();
  return (to: string) => localizePath(lang, to);
}

/** Link, который сам добавляет /ru для русской версии */
export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link({ to, ...props }, ref) {
  const lang = useLang();
  return <RRLink ref={ref} to={typeof to === "string" ? localizePath(lang, to) : to} {...props} />;
});

export const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(function NavLink({ to, ...props }, ref) {
  const lang = useLang();
  return <RRNavLink ref={ref} to={typeof to === "string" ? localizePath(lang, to) : to} {...props} />;
});
