import React, { useState } from "react";
import { Navbar } from "./shared/components/Navbar";
import { CardList } from "./modules/content/components/CardList";
import { CreateCardForm } from "./modules/content/components/CreateCardForm";
import { LocationList } from "./modules/content/components/LocationList";
import { CreateLocationForm } from "./modules/content/components/CreateLocationForm";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "catalog" | "create-card" | "create-location" | "locations"
  >("catalog");

  return (
    <div className="min-h-screen flex flex-col bg-arena-bg text-slate-100">
      {/* Navbar con estado del sistema */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === "catalog" && <CardList />}
        {activeTab === "create-card" && (
          <CreateCardForm onSuccess={() => setActiveTab("catalog")} />
        )}
        {activeTab === "locations" && <LocationList />}
        {activeTab === "create-location" && (
          <CreateLocationForm onSuccess={() => setActiveTab("locations")} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-arena-border/60 py-6 mt-12 bg-arena-card/30">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-500 space-y-1">
          <p>
            <strong className="text-slate-400">Poké-Arena</strong> — Plataforma Web de Cartas Coleccionables • Equipo MAFY
          </p>
          <p>
            Sprint 1: Crear Carta (F-02, 5:7) • Crear Ubicación (F-03, 4:3) • Buscar Carta (US 2.1.2 MongoDB)
          </p>
        </div>
      </footer>
    </div>
  );
};

export default App;
