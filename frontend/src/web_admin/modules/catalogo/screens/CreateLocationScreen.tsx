// Pantalla principal de creación de ubicación: ensambla form + uploader + hook
import { useState } from "react";
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
  const { loading, error, success, submitLocation, reset } = useCreateLocation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Pasa form values e imagen
    await submitLocation({ ...formValues, imagen });
  };

  const handleReset = () => {
    setFormValues(VALORES_INICIALES);
    setImagen(null);
    reset();
  };

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100 p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold tracking-tight mb-6">Crear Ubicación</h1>

        {success ? (
          <div className="rounded-xl border border-green-700 bg-green-900/20 p-8 text-center">
            <p className="text-green-400 font-semibold text-lg">¡Ubicación creada!</p>
            <p className="text-slate-400 text-sm mt-1">{success.nombre}</p>
            <button
              onClick={handleReset}
              className="mt-6 rounded bg-slate-700 px-5 py-2 text-sm hover:bg-slate-600 transition-colors"
            >
              Crear otra ubicación
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="rounded-xl border border-arena-border bg-arena-card p-6 flex flex-col gap-6"
          >
            <LocationForm values={formValues} onChange={setFormValues} disabled={loading} />

            <LocationImageUploader value={imagen} onChange={setImagen} disabled={loading} />

            {error && (
              <div className="rounded border border-red-800 bg-red-900/20 p-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !imagen}
              className="rounded bg-indigo-600 px-6 py-3 font-semibold hover:bg-indigo-500
                         disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Guardando…" : "Guardar ubicación"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
