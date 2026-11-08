/**
 * Componente transversal para mostrar mensajes de estado, alertas de validación
 * y errores RFC 7807 con soporte opcional de `correlation_id` y botón de acción.
 *
 * Accesibilidad:
 * - Usa `role="alert"` (`aria-live="assertive"`) para errores y advertencias urgentes,
 *   y `role="status"` (`aria-live="polite"`) para mensajes informativos o de éxito.
 * - Combina iconografía explícita, etiqueta semántica y contraste cromático para no
 *   depender únicamente del color.
 */

import React from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
  type LucideIcon,
} from "lucide-react";

export type AlertBannerVariant = "error" | "warning" | "info" | "success";

export interface AlertBannerProps {
  readonly variant: AlertBannerVariant;
  readonly title: string;
  readonly description?: string | null;
  readonly correlationId?: string | null;
  readonly actionLabel?: string;
  readonly onAction?: () => void;
  readonly onDismiss?: () => void;
  readonly className?: string;
}

interface VariantStyleConfig {
  readonly containerClass: string;
  readonly badgeClass: string;
  readonly badgeLabel: string;
  readonly titleClass: string;
  readonly descriptionClass: string;
  readonly actionClass: string;
  readonly Icon: LucideIcon;
}

const VARIANT_STYLES: Record<AlertBannerVariant, VariantStyleConfig> = {
  error: {
    containerClass: "border-red-500/40 bg-red-950/40 text-red-100",
    badgeClass: "border-red-400/40 bg-red-500/20 text-red-200",
    badgeLabel: "Error",
    titleClass: "text-red-100",
    descriptionClass: "text-red-200/90",
    actionClass:
      "border-red-400/40 bg-red-500/20 text-red-100 hover:bg-red-500/30 focus-visible:ring-red-400",
    Icon: AlertCircle,
  },
  warning: {
    containerClass: "border-amber-500/40 bg-amber-950/40 text-amber-100",
    badgeClass: "border-amber-400/40 bg-amber-500/20 text-amber-200",
    badgeLabel: "Aviso",
    titleClass: "text-amber-100",
    descriptionClass: "text-amber-200/90",
    actionClass:
      "border-amber-400/40 bg-amber-500/20 text-amber-100 hover:bg-amber-500/30 focus-visible:ring-amber-400",
    Icon: AlertTriangle,
  },
  info: {
    containerClass: "border-blue-500/40 bg-blue-950/40 text-blue-100",
    badgeClass: "border-blue-400/40 bg-blue-500/20 text-blue-200",
    badgeLabel: "Info",
    titleClass: "text-blue-100",
    descriptionClass: "text-blue-200/90",
    actionClass:
      "border-blue-400/40 bg-blue-500/20 text-blue-100 hover:bg-blue-500/30 focus-visible:ring-blue-400",
    Icon: Info,
  },
  success: {
    containerClass: "border-emerald-500/40 bg-emerald-950/40 text-emerald-100",
    badgeClass: "border-emerald-400/40 bg-emerald-500/20 text-emerald-200",
    badgeLabel: "Éxito",
    titleClass: "text-emerald-100",
    descriptionClass: "text-emerald-200/90",
    actionClass:
      "border-emerald-400/40 bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/30 focus-visible:ring-emerald-400",
    Icon: CheckCircle2,
  },
};

export function AlertBanner({
  variant,
  title,
  description,
  correlationId,
  actionLabel,
  onAction,
  onDismiss,
  className = "",
}: AlertBannerProps): React.ReactElement {
  const style = VARIANT_STYLES[variant];
  const { Icon } = style;
  const isAssertive = variant === "error" || variant === "warning";

  return (
    <div
      role={isAssertive ? "alert" : "status"}
      aria-live={isAssertive ? "assertive" : "polite"}
      className={`rounded-xl border p-4 shadow-sm backdrop-blur-sm transition-colors ${style.containerClass} ${className}`.trim()}
    >
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden={true} />

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${style.badgeClass}`}
            >
              {style.badgeLabel}
            </span>
            <p className={`text-sm font-semibold leading-snug ${style.titleClass}`}>{title}</p>
          </div>

          {description && (
            <p className={`text-xs leading-relaxed ${style.descriptionClass}`}>{description}</p>
          )}

          {correlationId && (
            <p className="pt-1 font-mono text-[11px] opacity-80">
              ID de correlación: <span className="select-all">{correlationId}</span>
            </p>
          )}

          {actionLabel && onAction && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onAction}
                className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 ${style.actionClass}`}
              >
                {actionLabel}
              </button>
            </div>
          )}
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Cerrar mensaje"
            className="rounded-lg p-1 opacity-75 transition hover:bg-white/10 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          >
            <X className="h-4 w-4" aria-hidden={true} />
          </button>
        )}
      </div>
    </div>
  );
}
