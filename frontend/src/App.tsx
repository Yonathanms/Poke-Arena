/**
 * Raíz de la aplicación Frontend de Poké-Arena (`web-admin`).
 *
 * Responsabilidades:
 * 1. Coordinar el ciclo de autenticación administrativa a través de `useAdminSession`.
 * 2. Restringir el acceso a `AdminLayout` y `CreateCardScreen` exclusivamente cuando
 *    existe una sesión activa con rol `PLATFORM_ADMIN`.
 * 3. Si una sesión expira o se invalida por `401` después de que el administrador ya
 *    había ingresado al área de trabajo, mantener el árbol del área de trabajo montado
 *    en memoria (oculto e inerte con `hidden` / `aria-hidden`) mientras presenta el
 *    formulario de reautenticación, preservando el borrador de Crear Carta y cualquier
 *    `Idempotency-Key` pendiente sin exponer contenido protegido ni usar `localStorage`.
 * 4. La ruta `#/ubicaciones` es pública: renderiza `CreateLocationScreen` directamente
 *    sin requerir sesión administrativa.
 */

import React, { useEffect, useState } from "react";
import { AdminLoginForm } from "./web-admin/modules/auth/components/AdminLoginForm";
import { useAdminSession } from "./web-admin/modules/auth/hooks/useAdminSession";
import { CreateCardScreen } from "./web-admin/modules/catalogo/screens/CreateCardScreen";
import { CreateLocationScreen } from "./web-admin/modules/catalogo/screens/CreateLocationScreen";
import { AdminLayout } from "./web-admin/shared/AdminLayout";

export interface AppProps {
  readonly children?: React.ReactNode;
}

export default function App({ children }: AppProps = {}): React.ReactElement {
  const [currentHash, setCurrentHash] = useState(() => window.location.hash);

  useEffect(() => {
    const handleHashChange = () => setCurrentHash(window.location.hash);
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

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

  // Ruta pública sin autenticación: crear ubicación
  if (currentHash === "#/ubicaciones") {
    return <CreateLocationScreen />;
  }

  const preserveWorkspaceInBackground =
    !isAdminAuthenticated &&
    hasEnteredWorkspace &&
    (lastInvalidationReason === "expired" || lastInvalidationReason === "unauthorized_401");

  const workspaceContent = children ?? <CreateCardScreen />;

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
          {workspaceContent}
        </AdminLayout>
      )}

      {/* Preservación inerte del contenedor de trabajo durante reautenticación por expiración */}
      {preserveWorkspaceInBackground && (
        <div hidden aria-hidden="true" data-testid="preserved-workspace-container">
          {workspaceContent}
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
