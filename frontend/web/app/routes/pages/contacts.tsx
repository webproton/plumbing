import { Clock, Mail, MapPin, MessageCircle, Phone } from "lucide-react";

import { CallbackForm } from "~/components/CallbackForm";
import { Card, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { useRootData } from "~/root";

import type { Route } from "./+types/contacts";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("page.contacts.title") }];

export default function Contacts() {
  const s = useRootData()?.settings;
  const t = useT();
  return (
    <div className="max-w-2xl space-y-6">
      <PageTitle subtitle={s?.opening_hours || t("page.contacts.hours")}>{t("page.contacts.title")}</PageTitle>
      <Card className="space-y-3 p-5">
        {s?.pickup_address && (
          <p className="flex items-start gap-3">
            <MapPin className="mt-0.5 size-5 shrink-0 text-brand-600" aria-hidden />
            <span>
              <span className="font-medium">{t("page.contacts.address")}:</span> {s.pickup_address}
              {s.google_business_url && (
                <>
                  {" · "}
                  <a href={s.google_business_url} target="_blank" rel="noreferrer" className="text-brand-700 underline">
                    {t("page.contacts.map")}
                  </a>
                </>
              )}
            </span>
          </p>
        )}
        {s?.opening_hours && (
          <p className="flex items-center gap-3">
            <Clock className="size-5 text-brand-600" aria-hidden /> {s.opening_hours}
          </p>
        )}
        {s?.phone && (
          <a href={`tel:${s.phone}`} className="flex items-center gap-3 text-lg font-medium">
            <Phone className="size-5 text-brand-600" aria-hidden /> {s.phone}
          </a>
        )}
        {s?.email && (
          <a href={`mailto:${s.email}`} className="flex items-center gap-3">
            <Mail className="size-5 text-brand-600" aria-hidden /> {s.email}
          </a>
        )}
        {s?.telegram && (
          <p className="flex items-center gap-3">
            <MessageCircle className="size-5 text-brand-600" aria-hidden /> Telegram: {s.telegram}
          </p>
        )}
        {!s && <p className="text-muted">{t("page.contacts.unavailable")}</p>}
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">{t("callback.title")}</h2>
        <CallbackForm />
      </Card>
    </div>
  );
}
