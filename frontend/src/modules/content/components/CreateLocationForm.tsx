import React, { useState } from "react";
import { MapPin, AlertCircle, CheckCircle2, Sparkles, Image as ImageIcon } from "lucide-react";
import { ApiClientError } from "@/shared/api/client";
import { LocationEffectType } from "../types/content";

interface CreateLocationFormProps {
  onSuccess: () => void;
}

export const CreateLocationForm: React.FC<CreateLocationFormProps> = ({ onSuccess }) => {
  const [name, setName] = useState("");
  const [effectType, setEffectType] = useState<LocationEffectType>("BONIFICACION_PODER");
  const [effectDesc, setEffectDesc] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [aspectWarning, setAspectWarning] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImageFile(file);
    const objectUrl = URL.createObjectURL(file);
    setImagePreview(objectUrl);

    // Pre-validar proporción 4:3 (~1.333)
    const img = new Image();
    img.src = objectUrl;
    img.onload = () => {
      const ratio = img.width / img.height;
      const target = 4 / 3;
      if (Math.abs(ratio - target) > 0.05) {
        setAspectWarning(
          `Advertencia: La imagen tiene proporción ${(ratio).toFixed(2)} (${img.width}x${img.height}). La proporción requerida para ubicación es 4:3 (~1.33).`
        );
      } else {
        setAspectWarning(null);
      }
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) {
      setErrorMessage("Por favor selecciona una imagen para la ubicación.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const formData = new FormData();
      formData.append("name", name.trim());
      formData.append("effect_type", effectType);
      formData.append("effect_description", effectDesc.trim());
      formData.append("image", imageFile);

      const idempotencyKey = `loc-${crypto.randomUUID()}`;

      const response = await fetch("/api/v1/content/locations", {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: formData,
      });

      const json = await response.json();

      if (!response.ok) {
        if (json.error) {
          throw new ApiClientError(response.status, json.error);
        }
        throw new Error(json.message || "Error al crear ubicación");
      }

      setSuccessMessage(`¡Ubicación '${name}' creada exitosamente!`);
      setName("");
      setEffectDesc("");
      setImageFile(null);
      setImagePreview(null);
      setAspectWarning(null);
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrorMessage(`[${err.code}]: ${err.message}`);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Ocurrió un error inesperado al crear la ubicación.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto glass-panel p-6 sm:p-8 rounded-2xl border border-arena-border shadow-2xl">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-arena-border">
        <div className="w-10 h-10 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
          <MapPin className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100">Crear Ubicación de Juego (F-03)</h2>
          <p className="text-xs text-slate-400">
            Cada partida de Poké-Arena utiliza 3 ubicaciones con efectos cerrados.
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block">Error de Dominio</span>
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      {successMessage && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3 text-emerald-300 text-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Nombre del Lugar *
          </label>
          <input
            type="text"
            required
            placeholder="Monte Corona"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Tipo de Efecto del Catálogo Cerrado *
          </label>
          <select
            value={effectType}
            onChange={(e) => setEffectType(e.target.value as LocationEffectType)}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
          >
            <option value="BONIFICACION_PODER">Bonificación de Poder por Tipo</option>
            <option value="MODIFICADOR_COSTO">Modificador de Costo de Energía</option>
            <option value="RESTRICCION_TURNO">Restricción por Turno</option>
            <option value="LIMITE_CARTAS">Límite de Cartas en Ubicación</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Descripción del Efecto *
          </label>
          <textarea
            required
            rows={2}
            placeholder="+2 de poder a cartas tipo Lucha jugadas en este lugar..."
            value={effectDesc}
            onChange={(e) => setEffectDesc(e.target.value)}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>

        {/* Imagen 4:3 */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Imagen de la Ubicación (Proporción Obligatoria 4:3) *
          </label>
          <div className="flex flex-col sm:flex-row gap-4 items-center p-4 border-2 border-dashed border-arena-border rounded-xl bg-arena-surface/40 hover:bg-arena-surface/70 transition-colors">
            {imagePreview ? (
              <div className="w-28 aspect-[4/3] rounded-lg overflow-hidden border border-arena-border shrink-0 bg-black">
                <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="w-28 aspect-[4/3] rounded-lg border border-arena-border/50 bg-arena-card flex flex-col items-center justify-center text-slate-500 shrink-0">
                <ImageIcon className="w-6 h-6 mb-1" />
                <span className="text-[10px]">4:3</span>
              </div>
            )}

            <div className="flex-1 w-full text-center sm:text-left">
              <input
                type="file"
                accept="image/*"
                onChange={handleImageChange}
                className="text-xs text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer"
              />
              <p className="text-[11px] text-slate-400 mt-1.5">
                La imagen de fondo para el tablero debe cumplir la relación de aspecto 4:3.
              </p>
              {aspectWarning && (
                <p className="text-[11px] text-amber-400 mt-1 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  {aspectWarning}
                </p>
              )}
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Guardar Ubicación</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
