// Formulario de datos de la ubicación (sin imagen)
import type {
  CreateLocationFormValues,
  EnergyBonusMode,
  LocationEffectType,
  PokemonType,
} from "../types/location-admin.types";

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

const inputCls =
  "mt-1 w-full rounded bg-slate-800 border border-slate-700 px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500";
const labelCls = "text-sm text-slate-300";

export function LocationForm({ values, onChange, disabled }: Props) {
  const set = <K extends keyof FormValues>(field: K, val: FormValues[K]) =>
    onChange({ ...values, [field]: val });

  const setParams = (params: Record<string, unknown>) =>
    onChange({ ...values, efecto_params: params as FormValues["efecto_params"] });

  const handleEfectoTipo = (tipo: LocationEffectType) =>
    onChange({
      ...values,
      efecto_tipo: tipo,
      efecto_params: PARAMS_DEFAULT[tipo] as FormValues["efecto_params"],
    });

  const maxEnergia = values.energia_tipo === "FIJA" ? 3 : 2;
  const params = values.efecto_params as Record<string, unknown>;

  return (
    <div className="flex flex-col gap-4">
      {/* Nombre */}
      <div>
        <label className={labelCls}>Nombre</label>
        <input
          className={inputCls}
          value={values.nombre}
          onChange={(e) => set("nombre", e.target.value)}
          disabled={disabled}
          maxLength={100}
          placeholder="Ej. Estadio Eléctrico"
        />
      </div>

      {/* Descripción */}
      <div>
        <label className={labelCls}>Descripción</label>
        <textarea
          className={inputCls}
          value={values.descripcion}
          onChange={(e) => set("descripcion", e.target.value)}
          disabled={disabled}
          maxLength={500}
          rows={3}
          placeholder="Descripción breve de la arena…"
        />
      </div>

      {/* Límite de cartas */}
      <div>
        <label className={labelCls}>Límite de cartas (0 = sin límite, máx 5)</label>
        <input
          type="number"
          className={inputCls}
          value={values.card_limit}
          onChange={(e) => set("card_limit", Number(e.target.value))}
          disabled={disabled}
          min={0}
          max={5}
        />
      </div>

      {/* Energía */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className={labelCls}>Modo de energía</label>
          <select
            className={inputCls}
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
            className={inputCls}
            value={values.energia_valor}
            onChange={(e) => set("energia_valor", Number(e.target.value))}
            disabled={disabled}
            min={0}
            max={maxEnergia}
          />
        </div>
      </div>

      {/* Efecto */}
      <div>
        <label className={labelCls}>Tipo de efecto</label>
        <select
          className={inputCls}
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
              className={inputCls}
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
              className={inputCls}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => setParams({ ...params, cantidad: Number(e.target.value) })}
              disabled={disabled}
              min={-5}
              max={5}
            />
          </div>
        </div>
      )}

      {values.efecto_tipo === "MODIFICADOR_COSTO" && (
        <div className="flex gap-3 pl-4 border-l-2 border-slate-700">
          <div className="flex-1">
            <label className={labelCls}>Cantidad (−5 a +5)</label>
            <input
              type="number"
              className={inputCls}
              value={(params.cantidad as number) ?? 0}
              onChange={(e) => setParams({ ...params, cantidad: Number(e.target.value) })}
              disabled={disabled}
              min={-5}
              max={5}
            />
          </div>
          <div className="flex-1">
            <label className={labelCls}>Tipo Pokémon (opcional)</label>
            <select
              className={inputCls}
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
            className={inputCls}
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
