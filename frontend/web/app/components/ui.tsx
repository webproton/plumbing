import { clsx } from "clsx";
import { AlertCircle, CheckCircle2, CircleHelp, Info, Loader2 } from "lucide-react";
import { useId, type ComponentProps, type ReactNode } from "react";
import { type LinkProps } from "react-router";

import { Link, useT } from "~/i18n/react";

// ---------- Button ----------

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60";
const buttonVariants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "border border-line bg-white text-ink hover:bg-brand-50",
  ghost: "text-ink hover:bg-brand-50",
  danger: "bg-danger text-white hover:opacity-90",
};
const buttonSizes: Record<Size, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4",
  lg: "h-12 px-6 text-lg",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", className?: string) {
  return clsx(buttonBase, buttonVariants[variant], buttonSizes[size], className);
}

interface ButtonProps extends ComponentProps<"button"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export function Button({ variant, size, loading, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button className={buttonClass(variant, size, className)} disabled={disabled || loading} {...props}>
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: LinkProps & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

// ---------- Form fields ----------

const inputClass =
  "w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-ink placeholder:text-muted/70 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 aria-[invalid=true]:border-danger";

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy })}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={clsx(inputClass, className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={clsx(inputClass, "min-h-24", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={clsx(inputClass, "pr-8", className)} {...props} />;
}

// ---------- Feedback ----------

type Tone = "info" | "success" | "danger";
const toneClass: Record<Tone, string> = {
  info: "border-brand-100 bg-brand-50 text-brand-700",
  success: "border-success/30 bg-success/10 text-success",
  danger: "border-danger/30 bg-danger/10 text-danger",
};
const toneIcon = { info: Info, success: CheckCircle2, danger: AlertCircle };

export function Alert({ tone = "info", children }: { tone?: Tone; children: ReactNode }) {
  const Icon = toneIcon[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={clsx("flex gap-3 rounded-xl border p-4", toneClass[tone])}>
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  );
}

export function Badge({ tone = "info", children }: { tone?: Tone | "muted"; children: ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        tone === "muted" ? "bg-line text-muted" : toneClass[tone],
      )}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Info;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[var(--radius-card)] border border-dashed border-line bg-white px-6 py-14 text-center">
      <Icon className="size-10 text-muted" aria-hidden />
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="max-w-md text-muted">{children}</div>}
    </div>
  );
}

export function Card({ className, ...props }: ComponentProps<"div">) {
  return <div className={clsx("rounded-[var(--radius-card)] border border-line bg-white", className)} {...props} />;
}

/** help — раздел справки кабинета (/seller/help#…): рядом с заголовком появится «Как это работает?» */
export function PageTitle({ children, subtitle, help }: { children: ReactNode; subtitle?: ReactNode; help?: string }) {
  const t = useT();
  const title = <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{children}</h1>;
  return (
    <div className="mb-6 space-y-1">
      {help ? (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {title}
          <Link
            to={`/seller/help#${help}`}
            className="text-brand-700 inline-flex items-center gap-1 text-sm font-medium hover:underline"
          >
            <CircleHelp className="size-4 self-center" aria-hidden /> {t("help.how")}
          </Link>
        </div>
      ) : (
        title
      )}
      {subtitle && <p className="text-muted">{subtitle}</p>}
    </div>
  );
}
