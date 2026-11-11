// Pantalla principal de creación de ubicación: ensambla form + uploader + vista previa en vivo + hook
import { useEffect, useState } from "react";
import { CheckCircle2, ImageIcon, Loader2, MapPin, RotateCcw, Save, Shield, Sparkles, X, Zap } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { LocationForm } from "../components/LocationForm";
import { LocationImageUploader } from "../components/LocationImageUploader";
import { useCreateLocation } from "../hooks/useCreateLocation";
import type { CreateLocationFormValues } from "../types/location-admin.types";

const VALORES_INICIALES: Omit<CreateLocationFormValues, "imagen"> = {
  nombre: "",
  descripcion: "",
  card_limit: 0,
  energia_tipo: "FIJA",
  energia_valor: 0,
  efecto_tipo: "BONIFICACION_POR_TIPO",
  efecto_params: { tipo: "FUE", cantidad: 0 },
};

export function CreateLocationScreen() {
  const [formValues, setFormValues] = useState(VALORES_INICIALES);
  const [imagen, setImagen] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [toastLocationName, setToastLocationName] = useState<string | null>(null);
  const { loading, error, success, submitLocation, reset } = useCreateLocation();

  useEffect(() => {
    if (!imagen) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(imagen);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imagen]);

  useEffect(() => {
    if (success) {
      setToastLocationName(success.nombre);
      setFormValues(VALORES_INICIALES);
      setImagen(null);
      reset();
      const timer = window.setTimeout(() => {
        setToastLocationName(null);
      }, 3500);
      return () => window.clearTimeout(timer);
    }
  }, [success, reset]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitLocation({ ...formValues, imagen });
  };

  const handleReset = () => {
    setFormValues(VALORES_INICIALES);
    setImagen(null);
    reset();
  };

  const params = formValues.efecto_params as unknown as Record<string, unknown>;
  const effectSummary =
    formValues.efecto_tipo === "BONIFICACION_POR_TIPO"
      ? `Bonificación ${Number(params.cantidad ?? 0) >= 0 ? `+${Number(params.cantidad ?? 0)}` : Number(params.cantidad ?? 0)} a tipo ${String(params.tipo ?? "FUE")}`
      : formValues.efecto_tipo === "MODIFICADOR_COSTO"
      ? `Modificador de costo ${Number(params.cantidad ?? 0) >= 0 ? `+${Number(params.cantidad ?? 0)}` : Number(params.cantidad ?? 0)}${params.tipo ? ` (${String(params.tipo)})` : ""}`
      : `Turnos restringidos: ${((params.turnos as number[]) ?? [1]).join(", ")}`;

  return (
    <div className="space-y-6">
      {/* Toast flotante no bloqueante */}
      {toastLocationName && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-20 right-6 z-50 max-w-sm rounded-2xl border border-emerald-500/40 bg-[#0F172A]/95 backdrop-blur-md p-4 shadow-[0_12px_32px_rgba(0,0,0,0.6)] animate-toast-in flex items-start gap-3"
        >
          <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-emerald-300">
              ✓ Ubicación creada correctamente
            </p>
            <p className="mt-0.5 text-xs text-slate-300">
              <span className="font-semibold text-white">{toastLocationName}</span> ya está disponible en el catálogo.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setToastLocationName(null)}
            className="text-slate-400 hover:text-white transition"
            aria-label="Cerrar aviso"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Encabezado homologado con Crear Carta */}
      <div className="flex items-center gap-3.5 glass-card p-5 sm:px-6">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
          <MapPin className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white sm:text-xl">
            Crear Ubicación Oficial
          </h1>
          <p className="text-xs text-slate-400">
            Registra un estadio en el catálogo con validación 4:3 y previsualización en tiempo real.
          </p>
        </div>
      </div>

      {error && (
        <AlertBanner
          variant="error"
          title="No se pudo crear la ubicación"
          description={error}
        />
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_380px] items-start">
        {/* Columna izquierda: Formulario */}
        <form
          onSubmit={handleSubmit}
          className="space-y-6 glass-card p-6 sm:p-8"
        >
          <div className="border-b border-white/10 pb-4">
            <h3 className="text-lg font-bold tracking-tight text-white">Datos de la Ubicación</h3>
            <p className="mt-0.5 text-xs text-slate-400">
              Configura las reglas de arena, límite de cartas y modificadores elementales.
            </p>
          </div>

          <LocationForm values={formValues} onChange={setFormValues} disabled={loading} />

          <LocationImageUploader value={imagen} onChange={setImagen} disabled={loading} />

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-5">
            <button
              type="button"
              disabled={loading}
              onClick={handleReset}
              className="inline-flex items-center gap-2 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2 text-xs font-semibold transition-all disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Limpiar formulario</span>
            </button>

            <button
              type="submit"
              disabled={loading || !imagen}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  <span>Guardando…</span>
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  <span>Guardar Ubicación</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Columna derecha: Vista Previa de la Arena */}
        <div className="lg:sticky lg:top-24 glass-card p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Vista Previa de la Arena
              </h3>
              <p className="text-[11px] text-slate-400">
                Proporción 4:3 · Escenario de Combate
              </p>
            </div>
            <span className="rounded-full border border-blue-500/30 bg-blue-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-blue-300">
              En edición
            </span>
          </div>

          <div className="rounded-2xl border border-amber-500/30 bg-[#090D16]/95 p-4 shadow-xl space-y-4">
            {/* Marco 4:3 */}
            <div className="relative aspect-[4/3] w-full overflow-hidden rounded-xl border border-white/10 bg-slate-900 flex items-center justify-center">
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt={formValues.nombre || "Vista previa de ubicación"}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-center p-4 text-slate-500">
                  <ImageIcon className="h-10 w-10 mb-2 text-slate-600" />
                  <p className="text-xs font-medium text-slate-400">Sin imagen 4:3 seleccionada</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">800×600 px mínimo</p>
                </div>
              )}

              <div className="absolute top-2.5 left-2.5 rounded-lg bg-slate-950/85 backdrop-blur-sm border border-white/15 px-2.5 py-1 text-[11px] font-bold text-amber-300 flex items-center gap-1">
                <Zap className="h-3 w-3 text-amber-400" />
                <span>
                  {formValues.energia_tipo === "FIJA"
                    ? `+${formValues.energia_valor} Energía fija`
                    : `+${formValues.energia_valor} Energía / carta`}
                </span>
              </div>

              <div className="absolute top-2.5 right-2.5 rounded-lg bg-slate-950/85 backdrop-blur-sm border border-white/15 px-2.5 py-1 text-[11px] font-semibold text-slate-200 flex items-center gap-1">
                <Shield className="h-3 w-3 text-blue-400" />
                <span>
                  {formValues.card_limit === 0
                    ? "Sin límite"
                    : `Máx. ${formValues.card_limit} cartas`}
                </span>
              </div>
            </div>

            {/* Nombre y Descripción */}
            <div className="space-y-1.5">
              <h4 className="text-base font-extrabold tracking-tight text-white truncate">
                {formValues.nombre.trim() || "Nombre del Estadio"}
              </h4>
              <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                {formValues.descripcion.trim() ||
                  "La descripción oficial y las reglas activas del estadio aparecerán aquí durante el combate."}
              </p>
            </div>

            {/* Regla activa */}
            <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Sparkles className="h-4 w-4 text-blue-400 shrink-0" />
                <span className="text-xs font-semibold text-blue-200 truncate">
                  {effectSummary}
                </span>
              </div>
              <span className="rounded bg-blue-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-blue-300 shrink-0">
                REGLA
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
