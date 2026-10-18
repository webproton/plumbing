import { clsx } from "clsx";
import type { ComponentProps, ReactNode } from "react";

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto rounded-2xl border border-line bg-white">{children}</div>;
}

export function Table({ className, ...props }: ComponentProps<"table">) {
  return <table className={clsx("w-full min-w-[40rem] text-sm", className)} {...props} />;
}

export function Th({ className, align, ...props }: ComponentProps<"th"> & { align?: "right" }) {
  return (
    <th
      className={clsx(
        "border-b border-line bg-surface px-4 py-2.5 text-xs font-semibold tracking-wide text-muted uppercase",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, align, ...props }: ComponentProps<"td"> & { align?: "right" }) {
  return (
    <td
      className={clsx("border-b border-line px-4 py-2.5 align-middle last:border-b-0", align === "right" && "text-right tabular-nums", className)}
      {...props}
    />
  );
}

export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
