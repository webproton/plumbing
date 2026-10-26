import { ArrowRight, Store } from "lucide-react";

import { Card, EmptyState, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { apiContext } from "~/lib/context.server";
import { storefrontTagline } from "~/lib/storefront";
import type { Storefront } from "~/lib/types";

import type { Route } from "./+types/demo";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("demo.title") },
  // страница для показа клиентам — не для поиска
  { name: "robots", content: "noindex" },
];

export async function loader({ context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const storefronts = await api.get<Storefront[]>("/storefronts/demo/").catch(() => [] as Storefront[]);
  return { storefronts };
}

/** Демо-витрины: показать клиенту «его» магазин — велосипеды, инструмент, сантехника — на одном сайте */
export default function Demo({ loaderData }: Route.ComponentProps) {
  const t = useT();
  const lang = useLang();
  const { storefronts } = loaderData;
  return (
    <div className="space-y-6">
      <PageTitle subtitle={t("demo.subtitle")}>{t("demo.title")}</PageTitle>
      {storefronts.length === 0 && <EmptyState icon={Store} title={t("demo.empty")} />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {storefronts.map((s) => (
          <Link key={s.slug} to={`/?store=${s.slug}`} className="group">
            <Card className="h-full overflow-hidden transition-shadow group-hover:shadow-lg">
              <div className="h-2" style={{ background: s.brand_color || "var(--color-brand-600)" }} />
              <div className="space-y-2 p-5">
                <p className="text-lg font-bold">{s.name}</p>
                <p className="text-muted text-sm">{storefrontTagline(s, lang)}</p>
                <p
                  className="flex items-center gap-1 pt-2 text-sm font-semibold"
                  style={{ color: s.brand_color || undefined }}
                >
                  {t("demo.open")}{" "}
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" aria-hidden />
                </p>
              </div>
            </Card>
          </Link>
        ))}
        <Link to="/?store=all" className="group">
          <Card className="h-full space-y-2 border-dashed p-5 transition-shadow group-hover:shadow-lg">
            <p className="text-lg font-bold">{t("demo.all")}</p>
            <p className="text-muted text-sm">{t("demo.allText")}</p>
          </Card>
        </Link>
      </div>
    </div>
  );
}
