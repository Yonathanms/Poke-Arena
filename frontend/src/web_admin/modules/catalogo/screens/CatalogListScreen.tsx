/**
 * Pantalla de registro de cartas creadas en la sesión actual (`CatalogListScreen.tsx`).
 *
 * Responsabilidades:
 * 1. Mostrar las cartas confirmadas con `201 Created` (`image_status: READY`) durante
 *    la sesión administrativa activa en memoria.
 * 2. Declarar con transparencia arquitectónica que este listado refleja las operaciones
 *    confirmadas en la sesión actual (`POST /api/v1/content/cards`), sin inventar un
 *    endpoint inexistente `GET /api/v1/content/cards` ni descargas directas de GridFS
 *    fuera del alcance de la Entrega 1G.
 */

import React from "react";
import { CheckCircle2, Layers, PlusCircle, Shield } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import {
  CARD_RARITY_VISUAL_META,
  CARD_TYPE_VISUAL_META,
  formatDisplayPower,
} from "../components/CardPreviewCard";
import type { CreatedCardSessionEntry } from "../hooks/useCreateCard";

export interface CatalogListScreenProps {
  readonly entries: readonly CreatedCardSessionEntry[];
  readonly onNavigateToCreate?: () => void;
}

export function CatalogListScreen({
  entries,
  onNavigateToCreate,
}: CatalogListScreenProps): React.ReactElement {
  return (
    <section
      aria-labelledby="session-catalog-heading"
      className="space-y-6"
    >
      {/* Encabezado de la vista */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl glass-card border border-arena-border p-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
            <Layers className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h2
              id="session-catalog-heading"
              className="text-xl font-bold tracking-tight text-white"
            >
              Cartas Creadas en la Sesión Actual ({entries.length})
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Historial local en memoria de confirmaciones HTTP 201 recibidas desde FastAPI.
            </p>
          </div>
        </div>

        {onNavigateToCreate && (
          <button
            type="button"
            onClick={onNavigateToCreate}
            className="inline-flex items-center gap-2 rounded-xl bg-arena-accent px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-blue-600/20 transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            <span>Crear nueva carta</span>
          </button>
        )}
      </div>

      {/* Aviso explícito del alcance contractual 1G */}
      <AlertBanner
        variant="info"
        title="Alcance del registro en la Entrega 1G"
        description="Esta vista muestra las cartas creadas y confirmadas (image_status: READY) durante la sesión administrativa activa en memoria. La consulta paginada del catálogo histórico completo (GET /api/v1/content/cards) corresponde a una historia de usuario separada fuera del alcance de 2.1.1 — Crear Carta."
      />

      {entries.length === 0 ? (
        <div className="rounded-2xl border border-arena-border bg-arena-card/70 p-10 text-center space-y-3">
          <p className="text-sm font-semibold text-slate-200">
            Aún no se han creado cartas durante esta sesión administrativa.
          </p>
          <p className="mx-auto max-w-md text-xs text-slate-400">
            Cuando registres una carta mediante el formulario de creación y el backend confirme el estado 201 Created, su código oficial y metadatos aparecerán aquí.
          </p>
          {onNavigateToCreate && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onNavigateToCreate}
                className="inline-flex items-center gap-2 rounded-xl border border-blue-500/40 bg-blue-500/15 px-4 py-2 text-xs font-semibold text-blue-200 transition hover:bg-blue-500/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                <PlusCircle className="h-4 w-4" aria-hidden="true" />
                <span>Ir al formulario Crear Carta</span>
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {entries.map((entry) => {
            const typeMeta =
              CARD_TYPE_VISUAL_META[entry.values.card_type] ?? CARD_TYPE_VISUAL_META.FUE;
            const rarityMeta =
              CARD_RARITY_VISUAL_META[entry.values.rarity] ?? CARD_RARITY_VISUAL_META.COMUN;
            const { Icon: TypeIcon } = typeMeta;

            return (
              <article
                key={entry.card.id}
                aria-label={`Carta confirmada ${entry.card.code} — ${entry.values.name}`}
                className="rounded-2xl border border-arena-border bg-arena-card/85 p-5 shadow-lg space-y-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2 border-b border-arena-border/60 pb-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-extrabold text-emerald-300">
                        {entry.card.code}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[11px] font-bold uppercase ${typeMeta.badgeClass}`}
                      >
                        <TypeIcon className="h-3 w-3" aria-hidden="true" />
                        {typeMeta.code}
                      </span>
                      <span
                        className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase ${rarityMeta.badgeClass}`}
                      >
                        {rarityMeta.label}
                      </span>
                    </div>
                    <h3 className="mt-1 text-base font-bold text-white">{entry.values.name}</h3>
                  </div>

                  <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    {entry.card.image_status}
                  </span>
                </div>

                <dl className="grid grid-cols-2 gap-3 rounded-xl border border-arena-border/70 bg-arena-surface/60 p-3 text-xs">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-400">
                      Costo / Poder
                    </dt>
                    <dd className="mt-0.5 font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>Costo: {entry.values.cost}</span>
                      <span className="text-slate-500">·</span>
                      <span className="inline-flex items-center gap-1">
                        <Shield className="h-3 w-3 text-blue-400" aria-hidden="true" />
                        Poder: {formatDisplayPower(entry.values.power)}
                      </span>
                    </dd>
                  </div>

                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-400">
                      Habilidad
                    </dt>
                    <dd className="mt-0.5 truncate font-semibold text-slate-200">
                      <span className="font-mono text-blue-300">{entry.values.ability_code}</span>
                      {entry.abilityName ? ` — ${entry.abilityName}` : ""}
                    </dd>
                  </div>

                  <div className="col-span-2 truncate font-mono text-[11px] text-slate-300">
                    <dt className="inline text-slate-400">ID Carta: </dt>
                    <dd className="inline select-all">{entry.card.id}</dd>
                  </div>

                  <div className="col-span-2 truncate font-mono text-[11px] text-slate-300">
                    <dt className="inline text-slate-400">ID Imagen GridFS: </dt>
                    <dd className="inline select-all">{entry.card.image_id}</dd>
                  </div>

                  <div className="col-span-2 truncate font-mono text-[11px] text-slate-400">
                    <dt className="inline">Operación: </dt>
                    <dd className="inline select-all">{entry.card.operation_id}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
