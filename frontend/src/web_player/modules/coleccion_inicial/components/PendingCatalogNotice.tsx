/**
 * Vista de información para el estado PENDING_CATALOG de US 3.1.1.
 *
 * Responsabilidades:
 * 1. Informar al jugador con rol PLAYER que el catálogo general aún no cuenta con
 *    las 15 cartas comunes elegibles necesarias para sortear la colección inicial.
 * 2. Explicar claramente que su cuenta fue creada y protegida en PostgreSQL, sin
 *    concesiones parciales de cartas ni cubos.
 * 3. Ofrecer la acción de cierre de sesión (`onLogout`) para permitir reintentar
 *    la provisión automáticamente en un inicio de sesión futuro cuando el catálogo
 *    haya sido abastecido.
 * 4. Respetar la regla funcional que prohíbe invocar provisiones desde el frontend
 *    o simular que un botón GET puede generar las cartas.
 */

import React from "react";
import { AlertCircle, Clock, LogOut, ShieldCheck } from "lucide-react";

export interface PendingCatalogNoticeProps {
  readonly onLogout: () => void | Promise<unknown>;
  readonly isLoggingOut?: boolean;
}

export function PendingCatalogNotice({
  onLogout,
  isLoggingOut = false,
}: PendingCatalogNoticeProps): React.ReactElement {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-12 text-slate-100">
      <div className="w-full max-w-lg rounded-3xl border border-amber-500/30 bg-slate-900/90 p-8 shadow-2xl shadow-black/60 backdrop-blur-md">
        {/* Encabezado con ícono de aviso */}
        <div className="flex flex-col items-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-amber-500/40 bg-gradient-to-tr from-amber-600/30 via-orange-600/20 to-amber-950/40 shadow-lg shadow-amber-500/20">
            <Clock className="h-8 w-8 text-amber-400" aria-hidden="true" />
          </div>

          <div className="mt-4">
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-amber-300">
              Colección Inicial No Disponible
            </span>
          </div>

          <h2 className="mt-4 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            Preparando tu colección inicial
          </h2>

          <p className="mt-3 text-sm leading-relaxed text-slate-300">
            El juego aún no cuenta con las 15 cartas comunes requeridas para otorgar
            tu colección inicial. En este momento el juego no está disponible para comenzar.
          </p>
        </div>

        {/* Garantías de seguridad y atomicidad */}
        <div className="mt-6 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-xs text-slate-400">
          <div className="flex items-start gap-2.5">
            <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" aria-hidden="true" />
            <span>
              <strong className="text-slate-200">Cuenta creada y protegida:</strong> Tu cuenta
              de jugador ha sido registrada exitosamente.
            </span>
          </div>

          <div className="flex items-start gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" aria-hidden="true" />
            <span>
              <strong className="text-slate-200">Sin entrega parcial:</strong> No se te han concedido
              cartas ni cubos de forma incompleta hasta que el paquete esté listo.
            </span>
          </div>
        </div>

        {/* Explicación de reintento automático */}
        <div className="mt-6 text-center">
          <p className="text-xs text-slate-400">
            Tan pronto como los administradores incorporen las cartas al catálogo, tu paquete inicial
            se sorteará y entregará <strong className="text-slate-200">automáticamente</strong> en tu
            próximo inicio de sesión.
          </p>
        </div>

        {/* Acción de salida */}
        <div className="mt-8 flex justify-center">
          <button
            type="button"
            disabled={isLoggingOut}
            onClick={() => void onLogout()}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-6 py-2.5 text-xs font-semibold text-slate-200 shadow-md transition hover:bg-slate-700 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            <span>{isLoggingOut ? "Cerrando sesión..." : "Cerrar Sesión"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
