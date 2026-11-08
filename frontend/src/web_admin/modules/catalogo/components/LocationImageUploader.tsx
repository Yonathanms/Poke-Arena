// Componente de carga de imagen con validación 4:3 en cliente
import { useRef, useState } from "react";

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

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setError(null);
    setPreview(null);
    onChange(null);
    if (!file) return;

    // Siguiente paso: validar imagen en el cliente
    const err = await validarImagen(file);
    if (err) {
      setError(err);
      return;
    }
    setPreview(URL.createObjectURL(file));
    onChange(file);
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm text-slate-300">
        Imagen de la arena{" "}
        <span className="text-slate-500">(4:3, min 800×600, PNG/JPG/WebP, máx 5 MB)</span>
      </label>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="rounded border border-dashed border-slate-600 px-4 py-6 text-sm text-slate-400
                   hover:border-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors"
      >
        {value ? value.name : "Seleccionar imagen…"}
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {preview && (
        <img
          src={preview}
          alt="Previsualización"
          className="mt-1 max-h-48 w-full rounded object-cover border border-slate-700"
        />
      )}
    </div>
  );
}
