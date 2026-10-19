import { useEffect } from "react";
import { useRevalidator } from "react-router";

import type { TKey } from "~/i18n";
import { useT } from "~/i18n/react";
import type { ImportSource, RunStatus } from "~/lib/types";

import { Badge } from "../ui";

const RUN_TONE: Record<RunStatus, "success" | "info" | "danger" | "muted"> = {
  pending: "muted",
  running: "info",
  preview: "info",
  applying: "info",
  done: "success",
  failed: "danger",
};

export const ACTIVE_RUN: RunStatus[] = ["pending", "running", "applying"];

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const t = useT();
  return <Badge tone={RUN_TONE[status]}>{t(`imp.status.${status}` as TKey)}</Badge>;
}

export function SourceStatusBadge({ source }: { source: Pick<ImportSource, "last_status" | "is_active"> }) {
  const t = useT();
  if (!source.is_active) return <Badge tone="muted">{t("src.inactive")}</Badge>;
  if (source.last_status === "ok") return <Badge tone="success">{t("src.status.ok")}</Badge>;
  if (source.last_status === "error") return <Badge tone="danger">{t("src.status.error")}</Badge>;
  if (source.last_status === "running") return <Badge>{t("src.status.running")}</Badge>;
  return <Badge tone="muted">{t("src.never")}</Badge>;
}

/** Пока идёт фоновая задача — периодически перезагружаем данные страницы (только видимой вкладки). */
export function usePolling(active: boolean, ms = 2500) {
  const { revalidate } = useRevalidator();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") void revalidate();
    }, ms);
    return () => clearInterval(id);
  }, [active, ms, revalidate]);
}

export const INTERVALS = [0, 60, 180, 360, 720, 1440] as const;

export function intervalLabel(minutes: number): TKey {
  return (INTERVALS as readonly number[]).includes(minutes)
    ? (`src.interval.${minutes}` as TKey)
    : "src.manual";
}
