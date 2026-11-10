// Formulario de datos de la ubicación (sin imagen)
import { useState } from "react";
import type {
  CreateLocationFormValues,
  EnergyBonusMode,
  LocationEffectType,
  PokemonType,
} from "../types/location-admin.types";
import {
  LOCATION_VALIDATION_CONSTRAINTS,
  validateLocationFields,
} from "../validation/location-validation";

const TIPOS_POKEMON: PokemonType[] = ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"];

const TIPOS_EFECTO: { value: LocationEffectType; label: string }[] = [
  { value: "BONIFICACION_POR_TIPO", label: "Bonificación por Tipo" },
  { value: "MODIFICADOR_COSTO", label: "Modificador de Costo" },
  { value: "RESTRICCION_TURNO", label: "Restricción de Turno" },
];

const PARAMS_DEFAULT: Record<LocationEffectType, unknown> = {
  BONIFICACION_POR_TIPO: { tipo: "FUE", cantidad: 0 },
  MODIFICADOR_COSTO: { cantidad: 0 },
  RESTRICCION_TURNO: { turnos: [1] },
};

type FormValues = Omit<CreateLocationFormValues, "imagen">;

interface Props {
  values: FormValues;
  onChange: (values: FormValues) => void;
  disabled?: boolean;
}

const labelCls = "text-sm text-slate-300";

function inputCls(hasError: boolean): string {
  return `mt-1 w-full rounded bg-slate-800 border ${
    hasError ? "border-red-500 focus:border-red-400" : "border-slate-700 focus:border-indigo-500"
  } px-3 py-2 text-slate-100 focus:outline-none`;
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-red-400">{message}</p>;
}

export function LocationForm({ values, onChange, disabled }: Props) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const touch = (field: string) => setTouched((t) => ({ ...t, [field]: true }));

  const set = <K extends keyof FormValues>(field: K, val: FormValues[K]) => {
    touch(field);
    onChange({ ...values, [field]: val });
  };

  const setParams = (params: Record<string, unknown>) => {
    touch("efecto_cantidad");
    onChange({ ...values, efecto_params: params as unknown as FormValues["efecto_params"] });
  };

  const handleEfectoTipo = (tipo: LocationEffectType) =>
    onChange({
      ...values,
      efecto_tipo: tipo,
      efecto_params: PARAMS_DEFAULT[tipo] as FormValues["efecto_params"],
    });

  const maxEnergia = values.energia_tipo === "FIJA"
    ? LOCATION_VALIDATION_CONSTRAINTS.ENERGIA_FIJA_MAX
    : LOCATION_VALIDATION_CONSTRAINTS.ENERGIA_POR_CARTAS_MAX;
  const params = values.efecto_params as unknown as Record<string, unknown>;
  const allErrors = validateLocationFields(values);
  // Solo muestra errores en campos que el usuario ya tocó
  const errors = {
    nombre: touched.nombre ? allErrors.nombre : undefined,
    descripcion: touched.descripcion ? allErrors.descripcion : undefined,
    card_limit: touched.card_limit ? allErrors.card_limit : undefined,
    energia_valor: touched.energia_valor ? allErrors.energia_valor : undefined,
    efecto_cantidad: touched.efecto_cantidad ? allErrors.efecto_cantidad : undefined,
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Nombre */}
      <div>
        <div className="flex items-center justify-between">
          <label className={labelCls}>Nombre</label>
          <span
            className={`font-mono text-[11px] ${
              values.nombre.trim().length > LOCATION_VALIDATION_CONSTRAINTS.NOMBRE_MAX_LENGTH
                ? "font-bold text-red-400"
                : "text-slate-500"
            }`}
          >
            {values.nombre.trim().length}/{LOCATION_VALIDATION_CONSTRAINTS.NOMBRE_MAX_LENGTH}
          </span>
        </div>
        <input
          className={inputCls(!!errors.nombre)}
          value={values.nombre}
          onChange={(e) => set("nombre", e.target.value)}
          disabled={disabled}
          maxLength={120}
          placeholder="Ej. Estadio Eléctrico"
          aria-invalid={!!errors.nombre}
        />
        <FieldError message={errors.nombre} />
      </div>

      {/* Descripción */}
      <div>
        <div className="flex items-center justify-between">
          <label className={labelCls}>Descripción</label>
          <span
            className={`font-mono text-[11px] ${
              values.descripcion.length > LOCATION_VALIDATION_CONSTRAINTS.DESCRIPCION_MAX_LENGTH
                ? "font-bold text-red-400"
                : "text-slate-500"
            }`}
          >
            {values.descripcion.length}/{LOCATION_VALIDATION_CONSTRAINTS.DESCRIPCION_MAX_LENGTH}
          </span>
        </div>
        <textarea
          className={inputCls(!!errors.descripcion)}
          value={values.descripcion}
          onChange={(e) => set("descripcion", e.target.value)}
          disabled={disabled}
          rows={3}
          placeholder="Descripción breve de la arena…"
          aria-invalid={!!errors.descripcion}
        />
        <FieldError message={errors.descripcion} />
      </div>

      {/* Límite de cartas */}
      <div>
        <label className={labelCls}>
          Límite de cartas (0 = sin límite, máx {LOCATION_VALIDATION_CONSTRAINTS.CARD_LIMIT_MAX})
        </label>
        <input
          type="number"
          className={inputCls(!!errors.card_limit)}
          value={values.card_limit}
          onChange={(e) => set("card_limit", Number(e.target.value))}
          disabled={disabled}
          min={LOCATION_VALIDATION_CONSTRAINTS.CARD_LIMIT_MIN}
          max={LOCATION_VALIDATION_CONSTRAINTS.CARD_LIMIT_MAX}
          aria-invalid={!!errors.card_limit}
        />
        <FieldError message={errors.card_limit} />
      </div>

      {/* Energía */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className={labelCls}>Modo de energía</label>
          <select
            className={inputCls(false)}
            value={values.energia_tipo}
            onChange={(e) =>
              onChange({ ...values, energia_tipo: e.target.value as EnergyBonusMode, energia_valor: 0 })
            }
            disabled={disabled}
          >
            <option value="FIJA">Fija (0–{LOCATION_VALIDATION_CONSTRAINTS.ENERGIA_FIJA_MAX} por turno)</option>
            <option value="POR_CARTAS">Por cartas (0–{LOCATION_VALIDATION_CONSTRAINTS.ENERGIA_POR_CARTAS_MAX} por carta)</option>
          </select>
        </div>
        <div className="flex-1">
          <label className={labelCls}>Valor de energía (0–{maxEnergia})</label>
          <input
            type="number"
            className={inputCls(!!errors.energia_valor)}
            value={values.energia_valor}
            onChange={(e) => set("energia_valor", Number(e.target.value))}
            disabled={disabled}
            min={0}
            max={maxEnergia}
            aria-invalid={!!errors.energia_valor}
          />
          <FieldError message={errors.energia_valor} />
        </div>
      </div>

      {/* Efecto */}
      <div>
        <label className={labelCls}>Tipo de efecto</label>
        <select
          className={inputCls(false)}
          value={values.efecto_tipo}
          onChange={(e) => handleEfectoTipo(e.target.value as LocationEffectType)}
          disabled={disabled}
        >
          {TIPOS_EFECTO.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {/* Parámetros dinámicos del efecto */}
      {values.efecto_tipo === "BONIFICACION_POR_TIPO" && (
        <div className="flex gap-3 pl-4 border-l-2 border-slate-700">
          <div className="flex-1">
            <label className={labelCls}>Tipo Pokémon</label>
            <select
              className={inputCls(false)}
              value={(params.tipo as string) ?? "FUE"}
              onChange={(e) => setParams({ ...params, tipo: e.target.value })}
              disabled={disabled}
            >
              {TIPOS_POKEMON.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className={labelCls}>
              Cantidad ({LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MIN} a +{LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MAX})
            </label>
            <input
              type="number"
              className={inputCls(!!errors.efecto_cantidad)}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => setParams({ ...params, cantidad: Number(e.target.value) })}
              disabled={disabled}
              min={LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MIN}
              max={LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MAX}
              aria-invalid={!!errors.efecto_cantidad}
            />
            <FieldError message={errors.efecto_cantidad} />
          </div>
        </div>
      )}

      {values.efecto_tipo === "MODIFICADOR_COSTO" && (
        <div className="flex gap-3 pl-4 border-l-2 border-slate-700">
          <div className="flex-1">
            <label className={labelCls}>
              Cantidad ({LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MIN} a +{LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MAX})
            </label>
            <input
              type="number"
              className={inputCls(!!errors.efecto_cantidad)}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => setParams({ ...params, cantidad: Number(e.target.value) })}
              disabled={disabled}
              min={LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MIN}
              max={LOCATION_VALIDATION_CONSTRAINTS.EFECTO_CANTIDAD_MAX}
              aria-invalid={!!errors.efecto_cantidad}
            />
            <FieldError message={errors.efecto_cantidad} />
          </div>
          <div className="flex-1">
            <label className={labelCls}>Tipo Pokémon (opcional)</label>
            <select
              className={inputCls(false)}
              value={(params.tipo as string) ?? ""}
              onChange={(e) => {
                const { tipo: _t, ...rest } = params;
                setParams(e.target.value ? { ...rest, tipo: e.target.value } : rest);
              }}
              disabled={disabled}
            >
              <option value="">Sin filtro</option>
              {TIPOS_POKEMON.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {values.efecto_tipo === "RESTRICCION_TURNO" && (
        <div className="pl-4 border-l-2 border-slate-700">
          <label className={labelCls}>Turnos restringidos (enteros positivos, separados por coma)</label>
          <input
            className={inputCls(false)}
            value={((params.turnos as number[]) ?? []).join(", ")}
            onChange={(e) => {
              const turnos = e.target.value
                .split(",")
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !isNaN(n) && n > 0);
              setParams({ turnos });
            }}
            disabled={disabled}
            placeholder="1, 2, 3"
          />
        </div>
      )}
    </div>
  );
}
