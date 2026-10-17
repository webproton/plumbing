import { ArrowRight, ShieldCheck, Truck, Wrench } from "lucide-react";
import { Link } from "react-router";

import { CallbackForm } from "~/components/CallbackForm";
import { ProductCard } from "~/components/ProductCard";
import { ButtonLink } from "~/components/ui";
import { apiContext } from "~/lib/context.server";
import type { ProductListItem } from "~/lib/types";
import { useRootData } from "~/root";

import type { Route } from "./+types/home";

export function meta({ matches }: Route.MetaArgs) {
  const site = (matches[0]?.loaderData as { siteName?: string } | undefined)?.siteName ?? "Магазин";
  return [
    { title: `${site} — сантехника и мебель с доставкой по Украине` },
    { name: "description", content: "Смесители, трубы, сантехника и мебель. Наличие на складе, доставка Новой Почтой." },
  ];
}

export async function loader({ context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  const newProducts = await api.get<ProductListItem[]>("/new_products/").catch(() => [] as ProductListItem[]);
  return { newProducts };
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const root = useRootData();
  const categories = root?.categories ?? [];
  return (
    <div className="space-y-12">
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 to-brand-500 px-6 py-12 text-white sm:px-12 sm:py-16">
        <div className="max-w-2xl space-y-5">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">Всё для ванной, кухни и дома</h1>
          <p className="text-lg text-white/85">
            Реальные остатки на складе, честные цены и доставка по всей Украине.
          </p>
          <div className="flex flex-wrap gap-3">
            <ButtonLink to="/catalog" size="lg" variant="secondary">
              Перейти в каталог <ArrowRight className="size-5" />
            </ButtonLink>
          </div>
          <div className="max-w-lg rounded-2xl bg-white/10 p-4 backdrop-blur">
            <p className="mb-2 text-sm text-white/85">Не нашли нужное? Оставьте телефон — подберём за вас.</p>
            <div className="text-ink [&_.text-success]:text-white">
              <CallbackForm />
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: ShieldCheck, title: "Только в наличии", text: "Показываем реальный остаток на складе" },
          { icon: Truck, title: "Доставка 1–3 дня", text: "Новая Почта или самовывоз" },
          { icon: Wrench, title: "Поможем с выбором", text: "Перезвоним и подскажем по совместимости" },
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
          <h2 className="mb-4 text-xl font-bold">Категории</h2>
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
            <h2 className="text-xl font-bold">Новинки</h2>
            <Link to="/catalog?ordering=new" className="text-sm font-medium text-brand-600 hover:underline">
              Смотреть все
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
