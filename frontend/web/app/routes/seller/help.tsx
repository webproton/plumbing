import { CheckCircle2, CircleHelp, ListChecks } from "lucide-react";

import { HELP } from "~/components/seller/help-content";
import { Card, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useLang } from "~/i18n/react";

import type { Route } from "./+types/help";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("help.nav") }];

/** Довідка кабінету: швидкий старт, розділи (якорі для кнопок «Як це працює?») і часті проблеми */
export default function Help() {
  const help = HELP[useLang()];

  return (
    <div className="space-y-6">
      <PageTitle subtitle={help.subtitle}>{help.title}</PageTitle>

      <Card className="border-brand-100 bg-brand-50/50 p-5">
        <h2 className="mb-3 flex items-center gap-2 font-semibold">
          <ListChecks className="text-brand-600 size-5" aria-hidden /> {help.quickStartTitle}
        </h2>
        <ol className="space-y-2">
          {help.quickStart.map((step, i) => (
            <li key={step.to + i} className="flex gap-3">
              <span className="bg-brand-600 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
                {i + 1}
              </span>
              <Link to={step.to} className="hover:text-brand-700 hover:underline">
                {step.text}
              </Link>
            </li>
          ))}
        </ol>
      </Card>

      <nav aria-label={help.contents} className="border-line rounded-2xl border bg-white p-4">
        <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">{help.contents}</p>
        <ul className="flex flex-wrap gap-2">
          {help.sections.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                className="border-line hover:bg-brand-50 inline-block rounded-full border px-3 py-1 text-sm"
              >
                {s.title}
              </a>
            </li>
          ))}
          <li>
            <a
              href="#faq"
              className="border-line hover:bg-brand-50 inline-block rounded-full border px-3 py-1 text-sm"
            >
              {help.faqTitle}
            </a>
          </li>
        </ul>
      </nav>

      {help.sections.map((s) => (
        <Card key={s.id} id={s.id} className="scroll-mt-24 p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">{s.title}</h2>
            {s.to && (
              <Link to={s.to} className="text-brand-700 text-sm font-medium hover:underline">
                {help.open} →
              </Link>
            )}
          </div>
          <p className="text-muted mt-1">{s.intro}</p>
          {s.steps && (
            <>
              <h3 className="mt-4 text-sm font-semibold">{help.stepsTitle}</h3>
              <ol className="mt-2 list-decimal space-y-1.5 pl-5">
                {s.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </>
          )}
          {s.tips && (
            <>
              <h3 className="mt-4 text-sm font-semibold">{help.tipsTitle}</h3>
              <ul className="mt-2 space-y-1.5">
                {s.tips.map((tip) => (
                  <li key={tip} className="flex gap-2">
                    <CheckCircle2 className="text-success mt-0.5 size-4 shrink-0" aria-hidden />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      ))}

      <Card id="faq" className="scroll-mt-24 p-5">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <CircleHelp className="text-brand-600 size-5" aria-hidden /> {help.faqTitle}
        </h2>
        <dl className="divide-line divide-y">
          {help.faq.map((item) => (
            <div key={item.q} className="py-3">
              <dt className="font-medium">{item.q}</dt>
              <dd className="text-muted mt-1">{item.a}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
