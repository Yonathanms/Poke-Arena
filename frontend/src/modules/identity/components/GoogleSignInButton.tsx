import React, { useEffect, useRef, useState } from "react";
import {
  createGooglePlatformSession,
  PlatformSessionDTO,
} from "../api/identity";
import { setPlatformAccessToken } from "@/shared/auth/session";

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentityApi {
  accounts: {
    id: {
      initialize: (options: {
        client_id: string;
        callback: (response: GoogleCredentialResponse) => void;
      }) => void;
      disableAutoSelect: () => void;
      renderButton: (
        element: HTMLElement,
        options: { theme: "outline"; size: "large"; text: "signin_with" }
      ) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentityApi;
  }
}

interface GoogleSignInButtonProps {
  onAuthenticated: (session: PlatformSessionDTO) => void;
}

const GOOGLE_SCRIPT_ID = "google-identity-services-client";
let googleScriptPromise: Promise<GoogleIdentityApi> | null = null;
let initializedClientId: string | null = null;
let activeCredentialHandler: ((credential: string) => void) | null = null;

export function disableGoogleAutoSelect(): void {
  window.google?.accounts.id.disableAutoSelect();
}

function loadGoogleIdentityServices(): Promise<GoogleIdentityApi> {
  if (window.google) return Promise.resolve(window.google);
  if (googleScriptPromise) return googleScriptPromise;

  googleScriptPromise = new Promise<GoogleIdentityApi>((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    const script = existingScript ?? document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google) resolve(window.google);
      else reject(new Error("Google Identity Services no se pudo inicializar."));
    };
    script.onerror = () => reject(new Error("No se pudo cargar Google Identity Services."));
    if (!existingScript) document.head.appendChild(script);
  }).catch((error: unknown) => {
    googleScriptPromise = null;
    throw error;
  });
  return googleScriptPromise;
}

export const GoogleSignInButton: React.FC<GoogleSignInButtonProps> = ({ onAuthenticated }) => {
  const buttonRef = useRef<HTMLDivElement>(null);
  const authHandlerRef = useRef(onAuthenticated);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  authHandlerRef.current = onAuthenticated;

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID;
    let active = true;

    if (!clientId) {
      setErrorMessage("Falta configurar VITE_GOOGLE_OAUTH_CLIENT_ID para iniciar sesión.");
      return () => {
        active = false;
      };
    }

    const acceptGoogleCredential = async (credential: string): Promise<void> => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const session = await createGooglePlatformSession(credential);
        if (!active) return;
        setPlatformAccessToken(session.access_token, session.expires_in);
        authHandlerRef.current(session);
      } catch (error: unknown) {
        if (!active) return;
        setErrorMessage(
          error instanceof Error ? error.message : "No se pudo iniciar sesión en Poké-Arena."
        );
      } finally {
        if (active) setLoading(false);
      }
    };

    activeCredentialHandler = (credential) => void acceptGoogleCredential(credential);
    void loadGoogleIdentityServices()
      .then((google) => {
        if (!active || !buttonRef.current) return;
        if (initializedClientId !== clientId) {
          google.accounts.id.initialize({
            client_id: clientId,
            callback: (response) => activeCredentialHandler?.(response.credential),
          });
          initializedClientId = clientId;
        }
        buttonRef.current.replaceChildren();
        google.accounts.id.renderButton(buttonRef.current, {
          theme: "outline",
          size: "large",
          text: "signin_with",
        });
        setErrorMessage(null);
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(
            error instanceof Error ? error.message : "No se pudo cargar Google Identity Services."
          );
        }
      });

    return () => {
      active = false;
      activeCredentialHandler = null;
    };
  }, []);

  return (
    <div className="flex flex-col items-end gap-1">
      <div ref={buttonRef} aria-label="Iniciar sesión con Google" />
      {loading && <span className="text-xs text-slate-400">Validando sesión…</span>}
      {errorMessage && (
        <span role="alert" className="max-w-64 text-right text-xs text-amber-300">
          {errorMessage}
        </span>
      )}
    </div>
  );
};
