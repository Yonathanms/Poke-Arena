import React, { useState } from "react";
import { MapPin, AlertCircle, CheckCircle2, Sparkles, Image as ImageIcon } from "lucide-react";
import { apiFetch, ApiClientError } from "@/shared/api/client";
import { LocationEffectType, EnergyBonusMode } from "../types/content";

interface CreateLocationFormProps {
  onSuccess: () => void;
}

const CARD_TYPES = ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"] as const;
const CARD_TYPE_LABELS: Record<string, string> = {
  FUE: "Fuego", AGU: "Agua", PLA: "Planta",
  ELE: "Eléctrico", PSI: "Psíquico", LUC: "Lucha",
};

export const CreateLocationForm: React.FC<CreateLocationFormProps> = ({ onSuccess }) => {
  // Campos básicos
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Configuración de efecto
  const [effectType, setEffectType] = useState<LocationEffectType>("BONIFICACION_PODER");
  const [effectDesc, setEffectDesc] = useState("");

  // Parámetros por tipo de efecto
  const [bpCardType, setBpCardType] = useState<string>("FUE");
  const [bpAmount, setBpAmount] = useState<number>(1);
  const [mcAmount, setMcAmount] = useState<number>(-1);
  const [mcCardType, setMcCardType] = useState<string>("");
  const [rtTurns, setRtTurns] = useState<string>("");

  // Card limit
  const [cardLimit, setCardLimit] = useState<number>(5);

  // Energy bonus
  const [energyBonusEnabled, setEnergyBonusEnabled] = useState(false);
  const [energyMode, setEnergyMode] = useState<EnergyBonusMode>("FIJA");
  const [energyAmount, setEnergyAmount] = useState<number>(1);

  // Imagen
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [aspectWarning, setAspectWarning] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const energyMaxAmount = energyMode === "FIJA" ? 3 : 2;

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    const objectUrl = URL.createObjectURL(file);
    setImagePreview(objectUrl);
    const img = new Image();
    img.src = objectUrl;
    img.onload = () => {
      const ratio = img.width / img.height;
      if (Math.abs(ratio - 4 / 3) > 0.05) {
        setAspectWarning(
          `Advertencia: proporción ${ratio.toFixed(2)} (${img.width}×${img.height}). Se requiere 4:3 (~1.33).`
        );
      } else {
        setAspectWarning(null);
      }
    };
  };

  const buildEffectParams = (): Record<string, unknown> => {
    if (effectType === "BONIFICACION_PODER") {
      return { card_type: bpCardType, amount: bpAmount };
    }
    if (effectType === "MODIFICADOR_COSTO") {
      const p: Record<string, unknown> = { amount: mcAmount };
      if (mcCardType) p.card_type = mcCardType;
      return p;
    }
    if (effectType === "RESTRICCION_TURNO") {
      const turns = rtTurns
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n) && n > 0);
      return { turns };
    }
    return {};
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) {
      setErrorMessage("Por favor selecciona una imagen para la ubicación.");
      return;
    }
    if (effectType === "RESTRICCION_TURNO") {
      const turns = rtTurns.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n) && n > 0);
      if (turns.length === 0) {
        setErrorMessage("Ingresa al menos un número de turno válido (enteros positivos separados por coma).");
        return;
      }
    }
    if (energyBonusEnabled && energyAmount > energyMaxAmount) {
      setErrorMessage(`La bonificación ${energyMode} debe ser entre 0 y ${energyMaxAmount}.`);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const formData = new FormData();
      formData.append("name", name.trim());
      formData.append("description", description.trim());
      formData.append("effect_type", effectType);
      formData.append("effect_description", effectDesc.trim());
      formData.append("effect_params_json", JSON.stringify(buildEffectParams()));
      formData.append("card_limit", String(cardLimit));
      if (energyBonusEnabled) {
        formData.append("energy_bonus_mode", energyMode);
        formData.append("energy_bonus_amount", String(energyAmount));
      }
      formData.append("image", imageFile);

      const idempotencyKey = `loc-${crypto.randomUUID()}`;

      await apiFetch("/content/locations", {
        method: "POST",
        body: formData,
      }, idempotencyKey);

      setSuccessMessage(`¡Ubicación '${name.trim()}' creada exitosamente!`);
      setName("");
      setDescription("");
      setEffectDesc("");
      setImageFile(null);
      setImagePreview(null);
      setAspectWarning(null);
      setBpCardType("FUE");
      setBpAmount(1);
      setMcAmount(-1);
      setMcCardType("");
      setRtTurns("");
      setCardLimit(5);
      setEnergyBonusEnabled(false);
      setEnergyAmount(1);
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
            Cada partida de Poké-Arena utiliza 3 ubicaciones con efectos del catálogo cerrado.
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
        {/* Nombre */}
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

        {/* Descripción de la ubicación */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Descripción de la Ubicación *
          </label>
          <textarea
            required
            rows={2}
            placeholder="Una cima montañosa donde el viento sopla con fuerza..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>

        {/* Límite de cartas */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Límite de Cartas por Jugador (0–5, 0 = sin cartas)
          </label>
          <input
            type="number"
            min={0}
            max={5}
            value={cardLimit}
            onChange={(e) => setCardLimit(Number(e.target.value))}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Bonificación de energía */}
        <div className="rounded-xl border border-arena-border/60 p-4 bg-arena-surface/30 space-y-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={energyBonusEnabled}
              onChange={(e) => setEnergyBonusEnabled(e.target.checked)}
              className="w-4 h-4 rounded accent-purple-500"
            />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Bonificación de Energía por Turno
            </span>
          </label>
          {energyBonusEnabled && (
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Modalidad</label>
                <select
                  value={energyMode}
                  onChange={(e) => {
                    setEnergyMode(e.target.value as EnergyBonusMode);
                    setEnergyAmount(1);
                  }}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                >
                  <option value="FIJA">Fija (0–3 por turno)</option>
                  <option value="POR_CARTAS">Por carta en ubicación (0–2)</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Cantidad (máx. {energyMaxAmount})
                </label>
                <input
                  type="number"
                  min={0}
                  max={energyMaxAmount}
                  value={energyAmount}
                  onChange={(e) => setEnergyAmount(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Tipo de efecto */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Tipo de Efecto del Catálogo *
          </label>
          <select
            value={effectType}
            onChange={(e) => setEffectType(e.target.value as LocationEffectType)}
            className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
          >
            <option value="BONIFICACION_PODER">Bonificación de Poder por Tipo</option>
            <option value="MODIFICADOR_COSTO">Modificador de Costo de Energía</option>
            <option value="RESTRICCION_TURNO">Restricción por Turno</option>
          </select>
        </div>

        {/* Parámetros dinámicos del efecto */}
        <div className="rounded-xl border border-arena-border/60 p-4 bg-arena-surface/30 space-y-3">
          <p className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
            Parámetros del Efecto
          </p>

          {effectType === "BONIFICACION_PODER" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Tipo de carta beneficiada</label>
                <select
                  value={bpCardType}
                  onChange={(e) => setBpCardType(e.target.value)}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                >
                  {CARD_TYPES.map((t) => (
                    <option key={t} value={t}>{CARD_TYPE_LABELS[t]} ({t})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Delta de poder (–5 a +5)</label>
                <input
                  type="number"
                  min={-5}
                  max={5}
                  value={bpAmount}
                  onChange={(e) => setBpAmount(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}

          {effectType === "MODIFICADOR_COSTO" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Delta de costo (–5 a +5)</label>
                <input
                  type="number"
                  min={-5}
                  max={5}
                  value={mcAmount}
                  onChange={(e) => setMcAmount(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Tipo afectado (opcional)
                </label>
                <select
                  value={mcCardType}
                  onChange={(e) => setMcCardType(e.target.value)}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                >
                  <option value="">Todos los tipos</option>
                  {CARD_TYPES.map((t) => (
                    <option key={t} value={t}>{CARD_TYPE_LABELS[t]} ({t})</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {effectType === "RESTRICCION_TURNO" && (
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">
                Números de turno restringidos (separados por coma, ej: 1,3,5)
              </label>
              <input
                type="text"
                placeholder="1,3,5"
                value={rtTurns}
                onChange={(e) => setRtTurns(e.target.value)}
                className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}
        </div>

        {/* Descripción del efecto */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Descripción del Efecto *
          </label>
          <textarea
            required
            rows={2}
            placeholder="+2 de poder a cartas tipo Lucha jugadas aquí..."
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
                accept="image/png,image/jpeg,image/webp"
                onChange={handleImageChange}
                className="text-xs text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer"
              />
              <p className="text-[11px] text-slate-400 mt-1.5">
                PNG, JPG o WebP · máx. 5 MB · proporción 4:3 obligatoria · mín. 800×600 px
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
