import React, { useEffect, useState } from "react";
import { MapPin, Sparkles } from "lucide-react";
import { apiFetch } from "@/shared/api/client";
import { LocationDTO } from "../types/content";

export const LocationList: React.FC = () => {
  const [locations, setLocations] = useState<LocationDTO[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchLocations = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<LocationDTO[]>("/content/locations");
      setLocations(data);
    } catch (err) {
      console.error("Error al cargar ubicaciones:", err);
      setLocations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLocations();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-3 border-b border-arena-border">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <MapPin className="w-5 h-5 text-purple-400" />
            <span>Ubicaciones del Tablero ({locations.length})</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Zonas de combate donde se enfrentan los jugadores en cada partida (Lecturas servidas desde réplica SQL).
          </p>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="aspect-[4/3] rounded-2xl bg-arena-surface/40 animate-pulse border border-arena-border/40" />
          ))}
        </div>
      ) : locations.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-2xl border border-arena-border">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-purple-500/10 flex items-center justify-center text-purple-400">
            <MapPin className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">No hay ubicaciones registradas</h3>
          <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
            Crea una ubicación en la pestaña "Crear Ubicación" para que esté disponible en las partidas.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {locations.map((loc) => (
            <div
              key={loc.id}
              className="group glass-card rounded-2xl overflow-hidden border border-arena-border hover:border-purple-500/40 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-purple-500/10"
            >
              {/* 4:3 Image */}
              <div className="relative w-full aspect-[4/3] bg-arena-surface overflow-hidden">
                <img
                  src={loc.thumbnail_url || loc.image_url}
                  alt={loc.name}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%' viewBox='0 0 800 600' fill='%231E2738'><text x='50%' y='50%' fill='%2364748B' font-size='28' font-family='sans-serif' text-anchor='middle'>Ubicación 4:3</text></svg>";
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                <div className="absolute bottom-3 left-3 right-3">
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-purple-500/80 text-white backdrop-blur-sm">
                    {loc.effect.effect_type}
                  </span>
                  <h3 className="text-lg font-bold text-white mt-1 drop-shadow-md">{loc.name}</h3>
                </div>
              </div>

              {/* Effect Description */}
              <div className="p-4 bg-arena-card/90">
                <p className="text-xs text-slate-300 flex items-start gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                  <span>{loc.effect.description}</span>
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
