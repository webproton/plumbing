import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useLocation } from "react-router";

import { useT } from "~/i18n/react";

import { buttonClass } from "./ui";

export function Pagination({ page, pages }: { page: number; pages: number }) {
  const t = useT();
  const { pathname, search } = useLocation();
  if (pages <= 1) return null;
  const href = (p: number) => {
    const params = new URLSearchParams(search);
    if (p === 1) params.delete("page");
    else params.set("page", String(p));
    const qs = params.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };
  const shown = [...new Set([1, page - 1, page, page + 1, pages])].filter((p) => p >= 1 && p <= pages);
  return (
    <nav aria-label={t("common.pages")} className="mt-8 flex flex-wrap items-center justify-center gap-2">
      {page > 1 && (
        <Link to={href(page - 1)} className={buttonClass("secondary", "sm")} aria-label={t("common.back")}>
          <ChevronLeft className="size-4" />
        </Link>
      )}
      {shown.map((p, i) => (
        <span key={p} className="flex items-center gap-2">
          {i > 0 && p - shown[i - 1] > 1 && <span className="text-muted">…</span>}
          <Link
            to={href(p)}
            aria-current={p === page ? "page" : undefined}
            className={buttonClass(p === page ? "primary" : "secondary", "sm", "min-w-9")}
          >
            {p}
          </Link>
        </span>
      ))}
      {page < pages && (
        <Link to={href(page + 1)} className={buttonClass("secondary", "sm")} aria-label={t("common.forward")}>
          <ChevronRight className="size-4" />
        </Link>
      )}
    </nav>
  );
}
