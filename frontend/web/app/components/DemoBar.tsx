import { Link, useT } from "~/i18n/react";

/** Полоса над шапкой на демо-витрине: видно, что это показ, и можно переключить тематику */
export function DemoBar({ name }: { name: string }) {
  const t = useT();
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
