/**
 * Pantalla de bienvenida y autenticación pública de Poké-Arena (`shared`).
 *
 * Responsabilidades:
 * 1. Servir como punto de entrada público para cualquier visitante o jugador.
 * 2. Ofrecer exclusivamente el inicio de sesión oficial con Google Identity Services (OIDC).
 * 3. Renderizar el botón oficial de Google y coordinar el intercambio del `id_token`
 *    contra `POST /api/v1/identity/login/google` a través de `loginWithGoogleIdToken`.
 * 4. Gestionar estados de carga, feedback de error RFC 7807 y avisos de cierre de sesión.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertBanner } from "./AlertBanner";
import { loginWithGoogleIdToken } from "../../web_admin/modules/auth/services/auth.api";
import { ApiHttpError } from "../services/http-client";
import type { ActiveSessionSnapshot } from "../../web_admin/modules/auth/types/auth.types";
import pokemonIcon from "../../images/icons/icono_pokemon.png";

export interface WelcomeLoginScreenProps {
  readonly onLoginSuccess: (session: ActiveSessionSnapshot) => void;
  readonly logoutNotice?: string | null;
}

export function WelcomeLoginScreen({
  onLoginSuccess,
  logoutNotice,
}: WelcomeLoginScreenProps): React.ReactElement {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [googleScriptReady, setGoogleScriptReady] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);

  const clientId =
    (typeof import.meta !== "undefined" && import.meta.env?.VITE_GOOGLE_OAUTH_CLIENT_ID) || "";

  // Manejador del ID Token devuelto por Google
  const handleGoogleCredentialResponse = useCallback(
    async (response: { credential: string }) => {
      if (!response.credential) {
        setErrorMessage("No se recibió credencial de Google.");
        return;
      }
      setIsSubmitting(true);
      setErrorMessage(null);
      try {
        const snapshot = await loginWithGoogleIdToken(response.credential);
        onLoginSuccess(snapshot);
      } catch (err) {
        if (err instanceof ApiHttpError) {
          if (err.code === "identidad_tipo_en_conflicto") {
            setErrorMessage(
              "Esta cuenta fue registrada previamente con un tipo incompatible de autenticación (conflicto de identidad)."
            );
          } else if (err.code === "provision_inconsistente") {
            setErrorMessage(
              "Se detectó una inconsistencia técnica en la provisión del jugador. Contacta al soporte técnico."
            );
          } else if (err.code === "provision_no_disponible") {
            setErrorMessage(
              "El servicio de provisión de jugadores no está disponible en este momento. Reintenta iniciar sesión en unos segundos."
            );
          } else {
            setErrorMessage(err.detail || "Error al autenticar con el servidor de Poké-Arena.");
          }
        } else if (err instanceof Error) {
          setErrorMessage(err.message);
        } else {
          setErrorMessage("Error inesperado durante el inicio de sesión.");
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [onLoginSuccess]
  );

  // Esperar a que el script de Google esté cargado e inicializar el botón oficial
  useEffect(() => {
    let intervalId: number | undefined;

    const checkGoogle = () => {
      if (typeof window !== "undefined" && window.google?.accounts?.id) {
        setGoogleScriptReady(true);
        if (intervalId) clearInterval(intervalId);
      }
    };

    checkGoogle();
    if (!window.google?.accounts?.id) {
      intervalId = window.setInterval(checkGoogle, 200);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  // Renderizar el botón oficial de Google cuando el SDK esté disponible
  useEffect(() => {
    if (googleScriptReady && window.google?.accounts?.id && buttonRef.current && clientId) {
      try {
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleCredentialResponse,
          auto_select: false,
        });

        buttonRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: "filled_blue",
          size: "large",
          text: "continue_with",
          shape: "pill",
          width: 320,
        });
      } catch {
        // Fallback silencioso si falla la inicialización automática
      }
    }
  }, [googleScriptReady, clientId, handleGoogleCredentialResponse]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12 sm:px-6 poke-arena-bg text-slate-100">
      <div className="w-full max-w-md">
        {/* Cabecera / Identidad de Poké-Arena */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-[#0F172A]/80 backdrop-blur-md p-2.5 shadow-[0_0_25px_rgba(59,130,246,0.25)] mb-4 border border-white/10">
            <img
              src={pokemonIcon}
              alt="Poké-Arena"
              className="w-14 h-14 object-contain drop-shadow-[0_0_16px_rgba(239,68,68,0.4)]"
            />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Poké-Arena
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            Plataforma Competitiva de Cartas Coleccionables
          </p>
        </div>

        {/* Tarjeta de Inicio de Sesión */}
        <div className="glass-card p-8">
          <div className="mb-6 text-center">
            <h2 className="text-lg font-semibold text-slate-100">
              Iniciar Sesión
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Usa tu cuenta de Google para ingresar a tu cuenta de jugador o portal administrativo.
            </p>
          </div>

          {/* Avisos de feedback y errores */}
          {logoutNotice && (
            <div className="mb-5">
              <AlertBanner variant="info" title="Aviso" description={logoutNotice} />
            </div>
          )}

          {errorMessage && (
            <div className="mb-5">
              <AlertBanner
                variant="error"
                title="Error de autenticación"
                description={errorMessage}
                onDismiss={() => setErrorMessage(null)}
              />
            </div>
          )}

          {/* Contenedor del Botón Oficial de Google */}
          <div className="flex flex-col items-center justify-center my-6 min-h-[44px]">
            {isSubmitting ? (
              <div className="flex items-center gap-3 py-2 text-sm text-blue-400 font-medium">
                <svg
                  className="animate-spin h-5 w-5 text-blue-400"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                <span>Conectando con Poké-Arena...</span>
              </div>
            ) : (
              <>
                <div ref={buttonRef} className="flex justify-center" />
                {!googleScriptReady && (
                  <button
                    type="button"
                    disabled
                    className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-full border border-slate-700 bg-slate-800 text-slate-400 text-sm font-medium opacity-60"
                  >
                    <span>Cargando Google Identity...</span>
                  </button>
                )}
              </>
            )}
          </div>

          <div className="mt-6 border-t border-white/10 pt-4 text-center">
            <p className="text-xs text-slate-400">
              Ingresa para gestionar tu colección y competir en la arena
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
