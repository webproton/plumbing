import { Link } from "react-router";

import type { SiteSettings } from "~/lib/types";

export function Footer({ siteName, settings }: { siteName: string; settings: SiteSettings | null }) {
  return (
    <footer className="mt-16 border-t border-line bg-white">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div className="space-y-2">
          <p className="text-lg font-extrabold text-brand-700">{siteName}</p>
          <p className="text-sm text-muted">Сантехника и мебель с доставкой по Украине.</p>
        </div>
        <nav className="space-y-2 text-sm" aria-label="Информация">
          <p className="font-semibold">Покупателям</p>
          <Link to="/catalog" className="block text-muted hover:text-ink">Каталог</Link>
          <Link to="/delivery" className="block text-muted hover:text-ink">Доставка и оплата</Link>
          <Link to="/contacts" className="block text-muted hover:text-ink">Контакты</Link>
        </nav>
        <div className="space-y-2 text-sm">
          <p className="font-semibold">Связаться с нами</p>
          {settings?.phone && <a href={`tel:${settings.phone}`} className="block text-muted hover:text-ink">{settings.phone}</a>}
          {settings?.email && <a href={`mailto:${settings.email}`} className="block text-muted hover:text-ink">{settings.email}</a>}
          {settings?.telegram && <p className="text-muted">Telegram: {settings.telegram}</p>}
        </div>
      </div>
      <p className="border-t border-line py-4 text-center text-xs text-muted">
        © {new Date().getFullYear()} {siteName}
      </p>
    </footer>
  );
}
