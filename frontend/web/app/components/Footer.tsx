import { Link, useT } from "~/i18n/react";
import type { SiteSettings } from "~/lib/types";

export function Footer({ siteName, settings }: { siteName: string; settings: SiteSettings | null }) {
  const t = useT();
  return (
    <footer className="mt-16 border-t border-line bg-white">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div className="space-y-2">
          <p className="text-lg font-extrabold text-brand-700">{siteName}</p>
          <p className="text-sm text-muted">{t("site.tagline")}.</p>
        </div>
        <nav className="space-y-2 text-sm" aria-label={t("footer.info")}>
          <p className="font-semibold">{t("footer.customers")}</p>
          <Link to="/catalog" className="block text-muted hover:text-ink">{t("nav.catalog")}</Link>
          <Link to="/delivery" className="block text-muted hover:text-ink">{t("nav.deliveryPayment")}</Link>
          <Link to="/contacts" className="block text-muted hover:text-ink">{t("nav.contacts")}</Link>
        </nav>
        <div className="space-y-2 text-sm">
          <p className="font-semibold">{t("footer.contact")}</p>
          {settings?.phone && <a href={`tel:${settings.phone}`} className="block text-muted hover:text-ink">{settings.phone}</a>}
          {settings?.email && <a href={`mailto:${settings.email}`} className="block text-muted hover:text-ink">{settings.email}</a>}
          {settings?.telegram && <p className="text-muted">Telegram: {settings.telegram}</p>}
          {settings?.pickup_address && <p className="text-muted">{settings.pickup_address}</p>}
          {settings?.opening_hours && <p className="text-muted">{settings.opening_hours}</p>}
        </div>
      </div>
      <p className="border-t border-line py-4 text-center text-xs text-muted">
        © {new Date().getFullYear()} {siteName}
      </p>
    </footer>
  );
}
