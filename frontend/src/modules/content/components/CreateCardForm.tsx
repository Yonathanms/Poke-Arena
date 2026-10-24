import React, { useEffect, useRef, useState } from "react";
import { PlusCircle, AlertCircle, CheckCircle2, Sparkles } from "lucide-react";
import { ApiClientError, apiFetch } from "@/shared/api/client";
import {
  AbilitySummaryDTO,
  CardCreatedResponseDTO,
  CardImageStatusResponseDTO,
  CardRarity,
  CardType,
} from "../types/content";

interface CreateCardFormProps {
  onSuccess: () => void;
}

const NONE_ABILITY: AbilitySummaryDTO = {
  code: "HAB-000",
  name: "Sin Habilidad",
  trigger: null,
  effect: null,
  affected_card_type: null,
  parameters: {},
};
const MAX_IMAGE_BYTES = 5_000_000;

export const CreateCardForm: React.FC<CreateCardFormProps> = ({ onSuccess }) => {
  const [name, setName] = useState("");
  const [cost, setCost] = useState(2);
  const [power, setPower] = useState(3);
  const [cardType, setCardType] = useState<CardType>("FUE");
  const [rarity, setRarity] = useState<CardRarity>("COMUN");

  const [abilities, setAbilities] = useState<AbilitySummaryDTO[]>([]);
  const [abilityCode, setAbilityCode] = useState("");
  const [abilityCatalogError, setAbilityCatalogError] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [createdCard, setCreatedCard] = useState<CardCreatedResponseDTO | null>(null);
  const [imageStatus, setImageStatus] = useState<CardImageStatusResponseDTO | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const idempotencyKey = useRef<string | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const changedRequestField = (): void => {
    idempotencyKey.current = null;
  };

  useEffect(() => {
    let active = true;
    apiFetch<AbilitySummaryDTO[]>("/content/abilities")
      .then((items) => {
        if (!active) return;
        const availableAbilities = items.length > 0 ? items : [NONE_ABILITY];
        setAbilities(availableAbilities);
        setAbilityCode((current) => current || availableAbilities[0].code);
        setAbilityCatalogError(items.length > 0
          ? null
          : "El catálogo está vacío; se puede continuar con HAB-000 — Sin Habilidad.");
      })
      .catch((err: unknown) => {
        if (!active) return;
        setAbilities([NONE_ABILITY]);
        setAbilityCode((current) => current || NONE_ABILITY.code);
        setAbilityCatalogError(
          err instanceof Error
            ? `No se pudo cargar el catálogo completo (${err.message}). Se puede continuar con HAB-000 — Sin Habilidad.`
            : "No se pudo cargar el catálogo completo. Se puede continuar con HAB-000 — Sin Habilidad."
        );
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (
      !createdCard?.image_status ||
      !createdCard.status_url ||
      imageStatus?.image_status === "READY" ||
      imageStatus?.image_status === "FAILED"
    ) {
      return;
    }
    let active = true;
    let timeout: ReturnType<typeof setTimeout>;
    const statusEndpoint = createdCard.status_url.replace(/^\/api\/v1/, "");

    const poll = async (): Promise<void> => {
      try {
        const current = await apiFetch<CardImageStatusResponseDTO>(statusEndpoint);
        if (!active) return;
        setImageStatus(current);
        setStatusError(null);
        if (current.image_status !== "READY" && current.image_status !== "FAILED") {
          timeout = setTimeout(() => void poll(), 2000);
        }
      } catch (err: unknown) {
        if (!active) return;
        setStatusError(err instanceof Error ? err.message : "No se pudo consultar el estado.");
        if (err instanceof ApiClientError && [401, 403].includes(err.status)) return;
        timeout = setTimeout(() => void poll(), 5000);
      }
    };

    timeout = setTimeout(() => void poll(), 1000);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [createdCard, imageStatus?.image_status]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!abilityCode) {
      setErrorMessage("Selecciona una habilidad para la carta.");
      return;
    }
    if (imageFile && imageFile.size > MAX_IMAGE_BYTES) {
      setErrorMessage("La imagen no puede superar los 5 MB.");
      return;
    }
    if (imageFile && !["image/jpeg", "image/png", "image/webp"].includes(imageFile.type)) {
      setErrorMessage("Formato no admitido. Usa JPG, PNG o WebP.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const formData = new FormData();
      formData.append("name", name.trim());
      formData.append("cost", cost.toString());
      formData.append("power", power.toString());
      formData.append("card_type", cardType);
      formData.append("rarity", rarity);
      formData.append("ability_code", abilityCode);
      if (imageFile) formData.append("image", imageFile);

      idempotencyKey.current ??= `card-${crypto.randomUUID()}`;
      const created = await apiFetch<CardCreatedResponseDTO>("/content/cards", {
        method: "POST",
        body: formData,
      }, idempotencyKey.current);

      setCreatedCard(created);
      setImageStatus(null);
      setStatusError(null);
      setSuccessMessage(created.image_status
        ? `La carta ${created.code} se registró. Su imagen está en procesamiento.`
        : `La carta ${created.code} quedó registrada como borrador sin imagen.`);
      idempotencyKey.current = null;
      setName("");
      setCost(2);
      setPower(3);
      setImageFile(null);
      if (imageInputRef.current) imageInputRef.current.value = "";
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

      {abilityCatalogError && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
          {abilityCatalogError}
        </div>
      )}

      {createdCard && (
        <section className="mb-6 rounded-xl border border-blue-500/30 bg-blue-500/10 p-4 text-sm" aria-live="polite">
          <h3 className="font-semibold text-slate-100">Estado de {createdCard.code}</h3>
          <p className="mt-1 text-slate-300">
            {statusError
              ? `No se pudo consultar el estado: ${statusError}`
              : createdCard.image_status
                ? `Imagen: ${imageStatus?.image_status ?? createdCard.image_status}`
              : "Sin imagen. La carta permanece como borrador y no está disponible para jugar."}
          </p>
          {!createdCard.image_status && (
            <button type="button" onClick={onSuccess} className="mt-2 text-blue-300 underline">
              Volver al catálogo
            </button>
          )}
          {imageStatus?.image_status === "FAILED" && (
            <p className="mt-1 text-amber-300">
              El procesamiento agotó sus intentos. La carta sigue sin estar disponible.
              {imageStatus.last_error ? ` ${imageStatus.last_error}` : ""}
            </p>
          )}
          {imageStatus?.image_status === "READY" && (
            <>
              <p className="mt-1 text-emerald-300">
                Las imágenes están listas y la carta ya está disponible.
              </p>
              <button type="button" onClick={onSuccess} className="mt-2 text-blue-300 underline">
                Volver al catálogo
              </button>
            </>
          )}
        </section>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Nombre */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Nombre del Pokémon *
            </label>
            <input
              type="text"
              required
              maxLength={100}
              placeholder="Charmander"
              value={name}
              onChange={(e) => {
                changedRequestField();
                setName(e.target.value);
              }}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Costo (0..10) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Costo de Energía ({cost}) *
            </label>
            <input
              type="range"
              min={0}
              max={10}
              value={cost}
              onChange={(e) => {
                changedRequestField();
                setCost(Number(e.target.value));
              }}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400 mt-1">
              <span>0</span>
              <span>2</span>
              <span>4</span>
              <span>6</span>
              <span>8</span>
              <span>10 (Máx)</span>
            </div>
          </div>

          {/* Poder */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Poder Base *
            </label>
            <input
              type="number"
              min={-20}
              max={20}
              required
              value={power}
              onChange={(e) => {
                changedRequestField();
                setPower(Number(e.target.value));
              }}
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
              onChange={(e) => {
                changedRequestField();
                setCardType(e.target.value as CardType);
              }}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="FUE">Fuego (FUE)</option>
              <option value="AGU">Agua (AGU)</option>
              <option value="PLA">Planta (PLA)</option>
              <option value="ELE">Eléctrico (ELE)</option>
              <option value="PSI">Psíquico (PSI)</option>
              <option value="LUC">Lucha (LUC)</option>
            </select>
          </div>

          {/* Rareza */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Rareza *
            </label>
            <select
              value={rarity}
              onChange={(e) => {
                changedRequestField();
                setRarity(e.target.value as CardRarity);
              }}
              className="w-full px-3.5 py-2.5 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="COMUN">Común</option>
              <option value="POCO_COMUN">Poco Común</option>
              <option value="RARA">Rara</option>
              <option value="LEGENDARIA">Legendaria</option>
            </select>
          </div>
        </div>

        <div className="rounded-xl border border-arena-border bg-arena-surface/50 p-4 space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
            Imagen de carta (opcional)
          </label>
          <input
            ref={imageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => {
              changedRequestField();
              setImageFile(event.currentTarget.files?.[0] ?? null);
            }}
            className="block w-full text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-600/20 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-blue-200 hover:file:bg-blue-600/30"
          />
          <p className="text-xs text-slate-400">
            JPG, PNG o WebP; hasta 5 MB; mínimo 300 × 420 px y proporción aproximada 5:7.
            {imageFile ? ` Seleccionada: ${imageFile.name}` : " Si se omite, la carta se guarda como borrador."}
          </p>
        </div>

        {/* Habilidad obligatoria del catálogo */}
        <div className="p-4 rounded-xl bg-arena-surface/50 border border-arena-border space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-blue-400">
            ✦ Habilidad (obligatoria)
          </label>
          <select
            required
            value={abilityCode}
            onChange={(e) => {
              changedRequestField();
              setAbilityCode(e.target.value);
            }}
            disabled={abilities.length === 0}
            className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-xs text-slate-100 disabled:opacity-50"
          >
            <option value="" disabled>
              {abilities.length === 0 ? "Cargando habilidades…" : "Selecciona una habilidad"}
            </option>
            {abilities.map((ability) => (
              <option key={ability.code} value={ability.code}>
                {ability.code} — {ability.name}
              </option>
            ))}
          </select>
          {abilities.find((ability) => ability.code === abilityCode)?.effect && (
            <p className="text-xs text-slate-300">
              {abilities.find((ability) => ability.code === abilityCode)?.effect}
            </p>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || !abilityCode || Boolean(createdCard?.image_status && imageStatus?.image_status !== "READY" && imageStatus?.image_status !== "FAILED")}
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
