import { Link, useT } from "~/i18n/react";

/**
 * Полоса над шапкой на витрине, открытой ссылкой ?store=… (сайт её запоминает): видно, где ты, и можно вернуться
 * во весь магазин. Демо-витрина — ещё и «другие тематики». На домене клиента полосы нет.
 */
export function DemoBar({ name, demo = true }: { name: string; demo?: boolean }) {
  const t = useT();
  if (!demo) {
    return (
      <div className="bg-ink px-4 py-2 text-center text-xs text-white sm:text-sm">
        <span className="font-semibold">{t("store.bar", { name })}</span>
        <span className="mx-2 opacity-50">·</span>
        <Link to="/?store=all" className="underline underline-offset-2 hover:opacity-80">
          {t("store.exit")}
        </Link>
      </div>
    );
  }
  return (
    <div className="bg-ink px-4 py-2 text-center text-xs text-white sm:text-sm">
      <span className="font-semibold">{t("demo.bar", { name })}</span>
      <span className="mx-2 opacity-50">·</span>
      <Link to="/demo" className="underline underline-offset-2 hover:opacity-80">
        {t("demo.others")}
      </Link>
      <span className="mx-2 opacity-50">·</span>
      <Link to="/?store=all" className="underline underline-offset-2 hover:opacity-80">
        {t("demo.exit")}
      </Link>
    </div>
  );
}
