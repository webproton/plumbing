import { ArrowRight, ShieldCheck, Truck, Wrench } from "lucide-react";

import { CallbackForm } from "~/components/CallbackForm";
import { ProductCard } from "~/components/ProductCard";
import { ButtonLink } from "~/components/ui";
import { makeT, type Lang } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { apiContext } from "~/lib/context.server";
import type { ProductListItem } from "~/lib/types";
import { useRootData } from "~/root";

import type { Route } from "./+types/home";

export function meta({ matches }: Route.MetaArgs) {
  const root = matches[0]?.loaderData as { siteName?: string; lang?: Lang } | undefined;
  const t = makeT(root?.lang ?? "uk");
  return [
    { title: t("home.title", { site: root?.siteName ?? "" }) },
    { name: "description", content: t("site.description") },
  ];
}

export async function loader({ context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const newProducts = await api.get<ProductListItem[]>("/new_products/").catch(() => [] as ProductListItem[]);
  return { newProducts };
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const root = useRootData();
  const t = useT();
  const categories = root?.categories ?? [];
  return (
    <div className="space-y-12">
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 to-brand-500 px-6 py-12 text-white sm:px-12 sm:py-16">
        <div className="max-w-2xl space-y-5">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">{t("home.hero.title")}</h1>
          <p className="text-lg text-white/85">
            {t("home.hero.text")}
          </p>
          <div className="flex flex-wrap gap-3">
            <ButtonLink to="/catalog" size="lg" variant="secondary">
              {t("common.toCatalog")} <ArrowRight className="size-5" />
            </ButtonLink>
          </div>
          <div className="max-w-lg rounded-2xl bg-white/10 p-4 backdrop-blur">
            <p className="mb-2 text-sm text-white/85">{t("home.hero.callback")}</p>
            <div className="text-ink [&_.text-success]:text-white">
              <CallbackForm />
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: ShieldCheck, title: t("home.usp.stock.title"), text: t("home.usp.stock.text") },
          { icon: Truck, title: t("home.usp.delivery.title"), text: t("home.usp.delivery.text") },
          { icon: Wrench, title: t("home.usp.help.title"), text: t("home.usp.help.text") },
        ].map(({ icon: Icon, title, text }) => (
          <div key={title} className="flex gap-4 rounded-2xl border border-line bg-white p-5">
            <Icon className="size-8 shrink-0 text-brand-600" aria-hidden />
            <div>
              <p className="font-semibold">{title}</p>
              <p className="text-sm text-muted">{text}</p>
            </div>
          </div>
        ))}
      </section>

      {categories.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-bold">{t("home.categories")}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {categories.map((c) => (
              <Link
                key={c.id}
                to={`/catalog?category=${c.slug}`}
                className="flex flex-col items-center gap-2 rounded-2xl border border-line bg-white p-4 text-center text-sm font-medium hover:border-brand-500 hover:text-brand-700"
              >
                {c.photo && <img src={c.photo} alt="" className="h-16 object-contain" loading="lazy" />}
                {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      {loaderData.newProducts.length > 0 && (
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-bold">{t("home.new")}</h2>
            <Link to="/catalog?ordering=new" className="text-sm font-medium text-brand-600 hover:underline">
              {t("home.seeAll")}
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {loaderData.newProducts.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
