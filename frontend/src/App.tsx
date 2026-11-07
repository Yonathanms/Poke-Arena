/**
 * Raíz de la aplicación Frontend de Poké-Arena (`web-admin`).
 *
 * Responsabilidades:
 * 1. Coordinar el ciclo de autenticación administrativa a través de `useAdminSession`.
 * 2. Restringir el acceso a `AdminLayout` exclusivamente cuando existe una sesión activa
 *    con rol `PLATFORM_ADMIN`.
 * 3. Si una sesión expira o se invalida por `401` después de que el administrador ya
 *    había ingresado al área de trabajo, mantener el árbol del área de trabajo montado
 *    en memoria (oculto e inerte con `hidden` / `aria-hidden`) mientras presenta el
 *    formulario de reautenticación, evitando destruir borradores futuros de Crear Carta (F4)
 *    sin mostrar contenido protegido ni conservar tokens en `localStorage`.
 */

import React, { useEffect, useState } from "react";
import { AdminLoginForm } from "./web-admin/modules/auth/components/AdminLoginForm";
import { useAdminSession } from "./web-admin/modules/auth/hooks/useAdminSession";
import { AdminLayout } from "./web-admin/shared/AdminLayout";

export interface AppProps {
  readonly children?: React.ReactNode;
}

export default function App({ children }: AppProps = {}): React.ReactElement {
  const {
    session,
    isAdminAuthenticated,
    isAuthenticating,
    isLoggingOut,
    remainingSeconds,
    retryCooldownSeconds,
    authError,
    logoutNotice,
    lastInvalidationReason,
    loginLocal,
    logout,
    clearAuthFeedback,
  } = useAdminSession();

  // Recuerda si hubo una sesión administrativa en el ciclo actual para preservar el árbol
  // montado en caso de expiración temporal (sin exponerlo ni desmontar borradores de F4).
  const [hasEnteredWorkspace, setHasEnteredWorkspace] = useState(false);

  useEffect(() => {
    if (isAdminAuthenticated) {
      setHasEnteredWorkspace(true);
    } else if (lastInvalidationReason === "manual_logout") {
      setHasEnteredWorkspace(false);
    }
  }, [isAdminAuthenticated, lastInvalidationReason]);

  const preserveWorkspaceInBackground =
    !isAdminAuthenticated &&
    hasEnteredWorkspace &&
    (lastInvalidationReason === "expired" || lastInvalidationReason === "unauthorized_401");

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100">
      {/* Vista protegida activa únicamente con sesión vigente y rol PLATFORM_ADMIN */}
      {isAdminAuthenticated && session && (
        <AdminLayout
          session={session}
          remainingSeconds={remainingSeconds}
          isLoggingOut={isLoggingOut}
          onLogout={logout}
        >
          {children}
        </AdminLayout>
      )}

      {/* Preservación inerte del contenedor de trabajo durante reautenticación por expiración */}
      {preserveWorkspaceInBackground && children && (
        <div hidden aria-hidden="true" data-testid="preserved-workspace-container">
          {children}
        </div>
      )}

      {/* Pantalla de autenticación / reautenticación */}
      {!isAdminAuthenticated && (
        <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12 sm:px-6">
          <AdminLoginForm
            isSubmitting={isAuthenticating}
            retryCooldownSeconds={retryCooldownSeconds}
            authError={authError}
            logoutNotice={logoutNotice}
            invalidationReason={lastInvalidationReason}
            onSubmitCredentials={loginLocal}
            onClearFeedback={clearAuthFeedback}
          />
        </div>
      )}
    </div>
  );
}
