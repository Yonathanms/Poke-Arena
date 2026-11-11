// Componente de carga de imagen con validación 4:3 en cliente
import { useEffect, useRef, useState } from "react";
import { ImagePlus, RefreshCw, Trash2, CheckCircle2 } from "lucide-react";

const RATIO_TARGET = 4 / 3;
const RATIO_TOLERANCIA = 0.02;
const MIN_ANCHO = 800;
const MIN_ALTO = 600;
const MAX_BYTES = 5 * 1024 * 1024;

interface Props {
  value: File | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
}

function validarImagen(file: File): Promise<string | null> {
  return new Promise((resolve) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      resolve("Formato inválido. Solo PNG, JPG o WebP.");
      return;
    }
    if (file.size > MAX_BYTES) {
      resolve("La imagen supera los 5 MB.");
      return;
    }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      if (img.width < MIN_ANCHO || img.height < MIN_ALTO) {
        resolve(`La imagen debe ser al menos ${MIN_ANCHO}×${MIN_ALTO} px.`);
        return;
      }
      if (Math.abs(img.width / img.height - RATIO_TARGET) > RATIO_TOLERANCIA) {
        resolve("La imagen debe tener proporción 4:3.");
        return;
      }
      resolve(null);
    };
    img.onerror = () => resolve("No se pudo leer la imagen.");
    img.src = url;
  });
}

export function LocationImageUploader({ value, onChange, disabled }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!value) {
      setPreview(null);
    }
  }, [value]);

  const handleFile = async (file: File | null) => {
    setError(null);
    setPreview(null);
    onChange(null);
    if (!file) return;

    const err = await validarImagen(file);
    if (err) {
      setError(err);
      return;
    }
    setPreview(URL.createObjectURL(file));
    onChange(file);
  };

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    await handleFile(file);
  };

  const handleClear = () => {
    setError(null);
    setPreview(null);
    onChange(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-200">
          Imagen de la Arena <span className="text-red-400">*</span>
        </label>
        <span className="font-mono text-[11px] text-slate-400">
          4:3 · Mín. 800×600 px · Máx. 5 MB
        </span>
      </div>

      {value && preview ? (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 rounded-xl border border-white/10 bg-[#090D16]/90 p-4">
          <img
            src={preview}
            alt="Previsualización de arena"
            className="h-24 w-32 shrink-0 rounded-lg object-cover border border-white/15 shadow-md"
          />
          <div className="flex-1 min-w-0 space-y-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              4:3 válida ({(value.size / 1024).toFixed(1)} KB)
            </span>
            <p className="text-xs font-semibold text-white truncate">{value.name}</p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button
                type="button"
                disabled={disabled}
                onClick={() => inputRef.current?.click()}
                className="inline-flex items-center gap-1.5 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-3 py-1.5 text-xs font-semibold transition-all disabled:opacity-50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Cambiar</span>
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={handleClear}
                className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-200 transition-all disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Quitar</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className="w-full flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-white/15 bg-[#090D16]/70 px-4 py-7 text-sm text-slate-300 hover:border-blue-500/60 hover:bg-blue-500/5 hover:text-white disabled:opacity-50 transition-all"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-400">
            <ImagePlus className="h-5 w-5" />
          </div>
          <span className="font-semibold text-xs sm:text-sm">
            Seleccionar arte oficial de la ubicación
          </span>
          <span className="text-[11px] text-slate-400">
            Formatos soportados: PNG, JPG o WebP en proporción horizontal 4:3
          </span>
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />

      {error && <p className="text-xs font-medium text-red-300">{error}</p>}
    </div>
  );
}
