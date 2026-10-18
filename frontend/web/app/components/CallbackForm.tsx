import { PhoneCall } from "lucide-react";
import { useFetcher } from "react-router";

import { useLocalPath, useT } from "~/i18n/react";

import { Button, Input } from "./ui";

export function CallbackForm() {
  const t = useT();
  const local = useLocalPath();
  const fetcher = useFetcher<{ ok: boolean; error: string | null }>();
  if (fetcher.data?.ok) {
    return <p className="font-medium text-success">{t("callback.thanks")}</p>;
  }
  return (
    <fetcher.Form method="post" action={local("/callback")} className="flex flex-col gap-2 sm:flex-row">
      <Input name="phone" type="tel" inputMode="tel" placeholder="+380 50 123 45 67" aria-label={t("checkout.phone")} required />
      <Button type="submit" loading={fetcher.state !== "idle"} className="shrink-0">
        <PhoneCall className="size-4" aria-hidden /> {t("callback.submit")}
      </Button>
      {fetcher.data?.error && <p className="text-sm text-danger sm:self-center">{fetcher.data.error}</p>}
    </fetcher.Form>
  );
}
