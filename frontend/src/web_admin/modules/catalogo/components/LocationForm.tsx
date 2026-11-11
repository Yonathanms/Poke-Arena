// Formulario de datos de la ubicación (sin imagen)
import { useState } from "react";
import type {
  CreateLocationFormValues,
  EnergyBonusMode,
  LocationEffectType,
  PokemonType,
} from "../types/location-admin.types";
import { validateLocationFields } from "../validation/location-validation";

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

const baseCls =
  "mt-1.5 w-full bg-[#090D16]/90 border rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 transition-all disabled:opacity-60";
const inputCls = (hasError: boolean) =>
  `${baseCls} ${
    hasError
      ? "border-red-500/70 focus:ring-red-400/40"
      : "border-white/10 focus:border-blue-500 focus:ring-blue-500/20"
  }`;
const labelCls = "block text-xs font-semibold uppercase tracking-wider text-slate-200";
const errorCls = "mt-1 text-xs font-medium text-red-300";

export function LocationForm({ values, onChange, disabled }: Props) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const touch = (field: string) => setTouched((prev) => ({ ...prev, [field]: true }));

  const set = <K extends keyof FormValues>(field: K, val: FormValues[K]) => {
    touch(String(field));
    onChange({ ...values, [field]: val });
  };

  const setParams = (params: Record<string, unknown>) =>
    onChange({ ...values, efecto_params: params as unknown as FormValues["efecto_params"] });

  const handleEfectoTipo = (tipo: LocationEffectType) =>
    onChange({
      ...values,
      efecto_tipo: tipo,
      efecto_params: PARAMS_DEFAULT[tipo] as unknown as FormValues["efecto_params"],
    });

  const errors = validateLocationFields(values);
  const maxEnergia = values.energia_tipo === "FIJA" ? 3 : 2;
  const params = values.efecto_params as unknown as Record<string, unknown>;

  return (
    <div className="flex flex-col gap-4">
      {/* Nombre */}
      <div>
        <label className={labelCls}>Nombre</label>
        <input
          className={inputCls(!!touched.nombre && !!errors.nombre)}
          value={values.nombre}
          onChange={(e) => set("nombre", e.target.value)}
          onBlur={() => touch("nombre")}
          disabled={disabled}
          maxLength={100}
          placeholder="Ej. Estadio Eléctrico"
        />
        {touched.nombre && errors.nombre && <p className={errorCls}>{errors.nombre}</p>}
      </div>

      {/* Descripción */}
      <div>
        <label className={labelCls}>Descripción</label>
        <textarea
          className={inputCls(!!touched.descripcion && !!errors.descripcion)}
          value={values.descripcion}
          onChange={(e) => set("descripcion", e.target.value)}
          onBlur={() => touch("descripcion")}
          disabled={disabled}
          maxLength={500}
          rows={3}
          placeholder="Descripción breve de la arena…"
        />
        {touched.descripcion && errors.descripcion && (
          <p className={errorCls}>{errors.descripcion}</p>
        )}
      </div>

      {/* Límite de cartas */}
      <div>
        <label className={labelCls}>Límite de cartas (0 = sin límite, máx 5)</label>
        <input
          type="number"
          className={inputCls(!!touched.card_limit && !!errors.card_limit)}
          value={values.card_limit}
          onChange={(e) => set("card_limit", Number(e.target.value))}
          onBlur={() => touch("card_limit")}
          disabled={disabled}
          min={0}
          max={5}
        />
        {touched.card_limit && errors.card_limit && (
          <p className={errorCls}>{errors.card_limit}</p>
        )}
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
            <option value="FIJA">Fija (0–3 por turno)</option>
            <option value="POR_CARTAS">Por cartas (0–2 por carta)</option>
          </select>
        </div>
        <div className="flex-1">
          <label className={labelCls}>Valor de energía (0–{maxEnergia})</label>
          <input
            type="number"
            className={inputCls(!!touched.energia_valor && !!errors.energia_valor)}
            value={values.energia_valor}
            onChange={(e) => set("energia_valor", Number(e.target.value))}
            onBlur={() => touch("energia_valor")}
            disabled={disabled}
            min={0}
            max={maxEnergia}
          />
          {touched.energia_valor && errors.energia_valor && (
            <p className={errorCls}>{errors.energia_valor}</p>
          )}
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
            <label className={labelCls}>Cantidad (−5 a +5)</label>
            <input
              type="number"
              className={inputCls(!!touched.efecto_cantidad && !!errors.efecto_cantidad)}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => { touch("efecto_cantidad"); setParams({ ...params, cantidad: Number(e.target.value) }); }}
              disabled={disabled}
              min={-5}
              max={5}
            />
            {touched.efecto_cantidad && errors.efecto_cantidad && (
              <p className={errorCls}>{errors.efecto_cantidad}</p>
            )}
          </div>
        </div>
      )}

      {values.efecto_tipo === "MODIFICADOR_COSTO" && (
        <div className="flex gap-3 pl-4 border-l-2 border-slate-700">
          <div className="flex-1">
            <label className={labelCls}>Cantidad (−5 a +5)</label>
            <input
              type="number"
              className={inputCls(!!touched.efecto_cantidad && !!errors.efecto_cantidad)}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => { touch("efecto_cantidad"); setParams({ ...params, cantidad: Number(e.target.value) }); }}
              disabled={disabled}
              min={-5}
              max={5}
            />
            {touched.efecto_cantidad && errors.efecto_cantidad && (
              <p className={errorCls}>{errors.efecto_cantidad}</p>
            )}
          </div>
          <div className="flex-1">
            <label className={labelCls}>Tipo Pokémon (opcional)</label>
            <select
              className={inputCls(false)}
              value={(params.tipo as string) ?? ""}
              onChange={(e) => {
                const rest = { ...params };
                delete rest.tipo;
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
