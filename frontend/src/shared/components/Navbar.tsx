import React, { useEffect, useState } from "react";
import { Sparkles, Layers, MapPin, PlusCircle, CheckCircle2, AlertCircle } from "lucide-react";
import { apiFetch } from "../api/client";
import { HealthResponse } from "../types/api";

interface NavbarProps {
  activeTab: "catalog" | "create-card" | "create-location" | "locations";
  setActiveTab: (tab: "catalog" | "create-card" | "create-location" | "locations") => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await apiFetch<HealthResponse>("/health");
        setHealth(data);
      } catch {
        setHealth(null);
      } finally {
        setLoadingHealth(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-arena-border/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Poké-Arena <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 font-semibold border border-blue-500/30">Sprint 1</span>
            </h1>
            <p className="text-xs text-slate-400">Plataforma de Cartas Coleccionables</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 sm:gap-2">
          <button
            onClick={() => setActiveTab("catalog")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "catalog"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                : "text-slate-300 hover:text-white hover:bg-arena-surface"
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Catálogo</span>
          </button>

          <button
            onClick={() => setActiveTab("create-card")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "create-card"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                : "text-slate-300 hover:text-white hover:bg-arena-surface"
            }`}
          >
            <PlusCircle className="w-4 h-4" />
            <span>Crear Carta</span>
          </button>

          <button
            onClick={() => setActiveTab("locations")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "locations"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                : "text-slate-300 hover:text-white hover:bg-arena-surface"
            }`}
          >
            <MapPin className="w-4 h-4" />
            <span>Ubicaciones</span>
          </button>

          <button
            onClick={() => setActiveTab("create-location")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "create-location"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                : "text-slate-300 hover:text-white hover:bg-arena-surface"
            }`}
          >
            <PlusCircle className="w-4 h-4" />
            <span>Crear Ubicación</span>
          </button>
        </nav>

        {/* System Health Badge */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-arena-surface/80 border border-arena-border text-xs">
          {loadingHealth ? (
            <div className="w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
          ) : health?.status === "healthy" ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Bases de Datos OK</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-amber-400 font-medium">Degradado</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
