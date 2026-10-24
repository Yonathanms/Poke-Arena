import React, { useState } from "react";
import {
  createLocalTestPlatformSession,
  PlatformSessionDTO,
} from "../api/identity";
import { setPlatformAccessToken } from "@/shared/auth/session";

interface LocalTestLoginButtonProps {
  onAuthenticated: (session: PlatformSessionDTO) => void;
}

export const LocalTestLoginButton: React.FC<LocalTestLoginButtonProps> = ({
  onAuthenticated,
}) => {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const signIn = async (): Promise<void> => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const session = await createLocalTestPlatformSession();
      setPlatformAccessToken(session.access_token, session.expires_in);
      onAuthenticated(session);
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof Error ? error.message : "No se pudo iniciar la sesión local."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => void signIn()}
        disabled={loading}
        className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-60"
      >
        {loading ? "Iniciando…" : "Entrar como admin local"}
      </button>
      {errorMessage && (
        <span role="alert" className="max-w-64 text-right text-xs text-amber-300">
          {errorMessage}
        </span>
      )}
    </div>
  );
};
