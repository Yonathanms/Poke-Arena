import React, { useState } from "react";
import { PlusCircle, AlertCircle, CheckCircle2, Sparkles, Image as ImageIcon } from "lucide-react";
import { ApiClientError } from "@/shared/api/client";
import { AbilityType, CardRarity, CardType } from "../types/content";

interface CreateCardFormProps {
  onSuccess: () => void;
}

export const CreateCardForm: React.FC<CreateCardFormProps> = ({ onSuccess }) => {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [cost, setCost] = useState(2);
  const [power, setPower] = useState(3);
  const [cardType, setCardType] = useState<CardType>("FUE");
  const [rarity, setRarity] = useState<CardRarity>("COMUN");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [aspectWarning, setAspectWarning] = useState<string | null>(null);

  // Habilidad opcional
  const [abilityType, setAbilityType] = useState<AbilityType>("HAB-000");
  const [abilityDesc, setAbilityDesc] = useState("");

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImageFile(file);
    const objectUrl = URL.createObjectURL(file);
    setImagePreview(objectUrl);

    // Pre-validar proporción 5:7 (~0.714) en el cliente
    const img = new Image();
    img.src = objectUrl;
    img.onload = () => {
      const ratio = img.width / img.height;
      const target = 5 / 7;
      if (Math.abs(ratio - target) > 0.05) {
        setAspectWarning(
          `Advertencia: La imagen tiene proporción ${(ratio).toFixed(2)} (${img.width}x${img.height}). La proporción requerida es 5:7 (~0.71).`
        );
      } else {
        setAspectWarning(null);
      }
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) {
      setErrorMessage("Por favor selecciona una imagen para la carta.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const formData = new FormData();
      formData.append("code", code.trim().toUpperCase());
      formData.append("name", name.trim());
      formData.append("cost", cost.toString());
      formData.append("power", power.toString());
      formData.append("card_type", cardType);
      formData.append("rarity", rarity);
      formData.append("image", imageFile);

      if (abilityType !== "HAB-000") {
        formData.append("ability_type", abilityType);
        formData.append("ability_description", abilityDesc);
      }

      const idempotencyKey = `card-${crypto.randomUUID()}`;

      const response = await fetch("/api/v1/content/cards", {
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
        throw new Error(json.message || "Error al crear carta");
      }

      setSuccessMessage(`¡Carta '${name}' creada exitosamente y sincronizada en PostgreSQL y MongoDB!`);
      // Reset form
      setCode("");
      setName("");
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
        setErrorMessage("Ocurrió un error inesperado al crear la carta.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto glass-panel p-6 sm:p-8 rounded-2xl border border-arena-border shadow-2xl">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-arena-border">
        <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
          <PlusCircle className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100">Crear Carta Pokémon (F-02)</h2>
          <p className="text-xs text-slate-400">
            Persistencia transaccional en PostgreSQL con proyección rápida en MongoDB.
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block">Error de Dominio / Validación</span>
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

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Código */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Código Oficial (ej: PKA-FUE-001) *
            </label>
            <input
              type="text"
              required
              placeholder="PKA-FUE-001"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Nombre */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Nombre del Pokémon *
            </label>
            <input
              type="text"
              required
              placeholder="Charmander"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Costo (1..6) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Costo de Energía ({cost} Puntos) *
            </label>
            <input
              type="range"
              min={1}
              max={6}
              value={cost}
              onChange={(e) => setCost(Number(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400 mt-1">
              <span>1</span>
              <span>2</span>
              <span>3</span>
              <span>4</span>
              <span>5</span>
              <span>6 (Máx)</span>
            </div>
          </div>

          {/* Poder */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Poder Base *
            </label>
            <input
              type="number"
              min={0}
              required
              value={power}
              onChange={(e) => setPower(Number(e.target.value))}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Tipo Elemental */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Tipo Elemental *
            </label>
            <select
              value={cardType}
              onChange={(e) => setCardType(e.target.value as CardType)}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="FUE">Fuego (FUE)</option>
              <option value="AGU">Agua (AGU)</option>
              <option value="PLA">Planta (PLA)</option>
              <option value="ELE">Eléctrico (ELE)</option>
              <option value="PSI">Psíquico (PSI)</option>
              <option value="LUC">Lucha (LUC)</option>
              <option value="INC">Incoloro (INC)</option>
            </select>
          </div>

          {/* Rareza */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Rareza *
            </label>
            <select
              value={rarity}
              onChange={(e) => setRarity(e.target.value as CardRarity)}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="COMUN">Común</option>
              <option value="POCO_COMUN">Poco Común</option>
              <option value="RARA">Rara</option>
              <option value="EPICA">Épica</option>
              <option value="LEGENDARIA">Legendaria</option>
            </select>
          </div>
        </div>

        {/* Imagen de Carta (5:7) */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Imagen de la Carta (Proporción Obligatoria 5:7) *
          </label>
          <div className="flex flex-col sm:flex-row gap-4 items-center p-4 border-2 border-dashed border-arena-border rounded-xl bg-arena-surface/40 hover:bg-arena-surface/70 transition-colors">
            {imagePreview ? (
              <div className="w-24 aspect-[5/7] rounded-lg overflow-hidden border border-arena-border shrink-0 bg-black">
                <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="w-24 aspect-[5/7] rounded-lg border border-arena-border/50 bg-arena-card flex flex-col items-center justify-center text-slate-500 shrink-0">
                <ImageIcon className="w-6 h-6 mb-1" />
                <span className="text-[10px]">5:7</span>
              </div>
            )}

            <div className="flex-1 w-full text-center sm:text-left">
              <input
                type="file"
                accept="image/*"
                onChange={handleImageChange}
                className="text-xs text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer"
              />
              <p className="text-[11px] text-slate-400 mt-1.5">
                Formatos permitidos: JPG, PNG, WEBP. Se procesará automáticamente a WebP y miniatura con Pillow.
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

        {/* Habilidad Opcional */}
        <div className="p-4 rounded-xl bg-arena-surface/50 border border-arena-border space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-blue-400">
            ✦ Habilidad Especial (Opcional)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <select
                value={abilityType}
                onChange={(e) => setAbilityType(e.target.value as AbilityType)}
                className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-xs text-slate-100"
              >
                <option value="HAB-000">Sin habilidad (HAB-000)</option>
                <option value="AL_REVELARSE">Al Revelarse</option>
                <option value="EFECTO_CONTINUO">Efecto Continuo</option>
                <option value="EVOLUCION">Evolución</option>
              </select>
            </div>
            {abilityType !== "HAB-000" && (
              <div>
                <input
                  type="text"
                  placeholder="Descripción de la habilidad..."
                  value={abilityDesc}
                  onChange={(e) => setAbilityDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-xs text-slate-100"
                />
              </div>
            )}
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Guardar Carta en Catálogo</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
