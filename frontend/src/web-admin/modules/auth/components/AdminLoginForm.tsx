/**
 * Formulario de inicio de sesión para el Administrador Maestro (`web-admin`).
 *
 * Seguridad y accesibilidad:
 * - Limpia inmediatamente la contraseña del estado local tras enviar la solicitud.
 * - Deshabilita el botón y bloquea envíos repetidos mientras `isSubmitting` está activo
 *   o mientras corre la cuenta regresiva de bloqueo temporal `429` (`Retry-After`).
 * - Asocia explícitamente `<label htmlFor>` con cada `<input>`, expone `aria-invalid`
 *   y `aria-describedby`, y renderiza alertas RFC 7807 mediante `AlertBanner`.
 */

import React, { useId, useRef, useState } from "react";
import { Clock, KeyRound, Loader2, ShieldAlert, ShieldCheck, UserCheck } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type { AdminAuthErrorInfo } from "../hooks/useAdminSession";
import { validateLocalLoginInput } from "../services/auth.api";
import type {
  LocalLoginCredentialsDTO,
  SessionInvalidationReason,
} from "../types/auth.types";

export interface AdminLoginFormProps {
  readonly isSubmitting: boolean;
  readonly retryCooldownSeconds: number;
  readonly authError: AdminAuthErrorInfo | null;
  readonly logoutNotice: string | null;
  readonly invalidationReason: SessionInvalidationReason | null;
  readonly onSubmitCredentials: (credentials: LocalLoginCredentialsDTO) => Promise<boolean>;
  readonly onClearFeedback?: () => void;
}

export function AdminLoginForm({
  isSubmitting,
  retryCooldownSeconds,
  authError,
  logoutNotice,
  invalidationReason,
  onSubmitCredentials,
  onClearFeedback,
}: AdminLoginFormProps): React.ReactElement {
  const formId = useId();
  const usernameInputId = `${formId}-username`;
  const passwordInputId = `${formId}-password`;
  const fieldErrorId = `${formId}-field-error`;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [clientValidationError, setClientValidationError] = useState<string | null>(null);
  const submitGuardRef = useRef(false);

  const isCooldownActive = retryCooldownSeconds > 0;
  const isSubmitDisabled = isSubmitting || isCooldownActive;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (submitGuardRef.current || isSubmitDisabled) {
      return;
    }

    const credentials: LocalLoginCredentialsDTO = {
      username,
      password,
    };

    const validationMessage = validateLocalLoginInput(credentials);
    if (validationMessage) {
      setClientValidationError(validationMessage);
      return;
    }

    setClientValidationError(null);
    submitGuardRef.current = true;
    // Limpiar la contraseña del estado tan pronto se captura para el envío
    setPassword("");

    try {
      await onSubmitCredentials(credentials);
    } finally {
      submitGuardRef.current = false;
    }
  };

  const sessionExpiredMessage =
    invalidationReason === "expired"
      ? "Tu sesión administrativa expiró por tiempo. Inicia sesión nuevamente para continuar."
      : invalidationReason === "unauthorized_401"
        ? "La sesión anterior ya no es válida o fue revocada. Autentícate de nuevo para continuar."
        : null;

  return (
    <section
      aria-labelledby={`${formId}-heading`}
      className="mx-auto w-full max-w-md rounded-2xl glass-panel p-6 sm:p-8 shadow-2xl"
    >
      {/* Encabezado de marca */}
      <div className="mb-6 flex items-center gap-3.5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 shadow-lg shadow-blue-500/20">
          <ShieldCheck className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1
              id={`${formId}-heading`}
              className="text-xl font-bold tracking-tight text-slate-100"
            >
              Poké-Arena
            </h1>
            <span className="rounded-full border border-blue-500/30 bg-blue-500/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-blue-300">
              Web Admin
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Acceso exclusivo para Administrador Maestro (<code className="font-mono">PLATFORM_ADMIN</code>)
          </p>
        </div>
      </div>

      {/* Avisos de expiración o cierre previo */}
      <div className="space-y-3 mb-5">
        {sessionExpiredMessage && !authError && (
          <AlertBanner
            variant="warning"
            title="Sesión finalizada"
            description={sessionExpiredMessage}
          />
        )}

        {logoutNotice && !authError && (
          <AlertBanner
            variant="info"
            title="Estado de sesión"
            description={logoutNotice}
            onDismiss={onClearFeedback}
          />
        )}

        {clientValidationError && (
          <div id={fieldErrorId}>
            <AlertBanner
              variant="warning"
              title="Revisa los campos requeridos"
              description={clientValidationError}
              onDismiss={() => setClientValidationError(null)}
            />
          </div>
        )}

        {authError && (
          <AlertBanner
            variant={authError.status === 429 ? "warning" : "error"}
            title={authError.title}
            description={
              isCooldownActive
                ? `Bloqueo temporal activo. Podrás volver a intentarlo en ${retryCooldownSeconds} s.`
                : authError.detail
            }
            correlationId={authError.correlationId}
            onDismiss={onClearFeedback}
          />
        )}
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
        <div>
          <label
            htmlFor={usernameInputId}
            className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >
            Usuario administrador
          </label>
          <div className="relative">
            <UserCheck
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              id={usernameInputId}
              name="username"
              type="text"
              autoComplete="username"
              maxLength={63}
              required
              disabled={isSubmitDisabled}
              value={username}
              aria-invalid={clientValidationError !== null || authError?.status === 401}
              aria-describedby={clientValidationError ? fieldErrorId : undefined}
              onChange={(event) => {
                setUsername(event.target.value);
                if (clientValidationError) {
                  setClientValidationError(null);
                }
              }}
              placeholder="Ej. maestro-local"
              className="w-full rounded-xl border border-arena-border bg-arena-surface py-2.5 pl-10 pr-3.5 text-sm text-slate-100 placeholder-slate-500 transition focus:border-arena-accent focus:outline-none focus:ring-2 focus:ring-arena-accent/40 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor={passwordInputId}
            className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
          >
            Contraseña
          </label>
          <div className="relative">
            <KeyRound
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              id={passwordInputId}
              name="password"
              type="password"
              autoComplete="current-password"
              maxLength={256}
              required
              disabled={isSubmitDisabled}
              value={password}
              aria-invalid={clientValidationError !== null || authError?.status === 401}
              aria-describedby={clientValidationError ? fieldErrorId : undefined}
              onChange={(event) => {
                setPassword(event.target.value);
                if (clientValidationError) {
                  setClientValidationError(null);
                }
              }}
              placeholder="Ingresa tu contraseña administrativa"
              className="w-full rounded-xl border border-arena-border bg-arena-surface py-2.5 pl-10 pr-3.5 text-sm text-slate-100 placeholder-slate-500 transition focus:border-arena-accent focus:outline-none focus:ring-2 focus:ring-arena-accent/40 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>
        </div>

        {isCooldownActive && (
          <div
            role="timer"
            aria-live="polite"
            className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-950/30 px-3.5 py-2.5 text-xs text-amber-200"
          >
            <Clock className="h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
            <span>
              Espera <strong className="font-mono">{retryCooldownSeconds}s</strong> antes de enviar un nuevo intento.
            </span>
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-arena-accent px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300 disabled:shadow-none"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              <span>Verificando credenciales...</span>
            </>
          ) : isCooldownActive ? (
            <>
              <ShieldAlert className="h-4 w-4" aria-hidden="true" />
              <span>Reintentar en {retryCooldownSeconds}s</span>
            </>
          ) : (
            <span>Iniciar sesión administrativa</span>
          )}
        </button>
      </form>

      <footer className="mt-6 border-t border-arena-border/60 pt-4 text-center text-[11px] text-slate-400">
        Sesión opaca almacenada únicamente en memoria volátil (<code className="font-mono">no-store</code>).
      </footer>
    </section>
  );
}
