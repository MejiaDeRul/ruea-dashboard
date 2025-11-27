// src/components/Filters.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  getFacetasWithFallback,
  type Facetas,
  type FiltersState,
} from "../api";

type Props = {
  value: FiltersState;
  onChange: (next: FiltersState) => void;
  enableFallback?: boolean; // no lo usamos, queda por compatibilidad
};

export default function Filters({ value, onChange }: Props) {
  const [fac, setFac] = useState<Facetas>({
    corregimiento: [],
    vereda: [],
    linea_productiva: [],
    escolaridad: [],
    sexo: [],
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>("");

  // carga facetas en función de los filtros actuales
  useEffect(() => {
    let canceled = false;
    (async () => {
      try {
        setLoading(true); setErr("");
        // Con fallback: si /facetas falla, calcula desde /ruea
        const f = await getFacetasWithFallback(value, { sampleLimit: 5000 });
        if (!canceled) setFac(f);
      } catch (e: any) {
        if (!canceled) setErr(e?.message || "No se pudieron cargar las facetas");
      } finally {
        if (!canceled) setLoading(false);
      }
    })();
    return () => { canceled = true; };
  }, [value?.corregimiento, value?.vereda, value?.linea_productiva, value?.escolaridad, value?.sexo]);

  // helpers
  const onSel = (k: keyof FiltersState) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value || undefined;
    const next: FiltersState = { ...value, [k]: v };
    // si cambias un filtro "padre", limpiamos dependientes débiles
    if (k === "corregimiento") {
      next.vereda = undefined;
    }
    onChange(next);
  };
  const clearAll = () => onChange({});

  // opciones visuales (muestran “Cargando…” y “— Todas —”)
  const Opts = ({ items }: { items: string[] }) => (
    <>
      <option value="">— Todas —</option>
      {items.map((x) => <option key={x} value={x}>{x}</option>)}
    </>
  );

  return (
    <section className="card">
      <div className="flex between mb-2">
        <h2 className="t-sub">Filtros</h2>
        <div className="flex gap">
          <button className="btn" onClick={clearAll}>Limpiar</button>
        </div>
      </div>

      {err && <div className="alert">{err}</div>}

      <div className="grid3">
        <label className="field">
          <span>Corregimiento</span>
          <select className="input" value={value.corregimiento ?? ""} onChange={onSel("corregimiento")} disabled={loading}>
            {loading ? <option>Cargando…</option> : <Opts items={fac.corregimiento} />}
          </select>
        </label>

        <label className="field">
          <span>Vereda</span>
          <select className="input" value={value.vereda ?? ""} onChange={onSel("vereda")} disabled={loading || !fac.vereda.length}>
            {loading ? <option>Cargando…</option> : <Opts items={fac.vereda} />}
          </select>
        </label>

        <label className="field">
          <span>Línea productiva</span>
          <select className="input" value={value.linea_productiva ?? ""} onChange={onSel("linea_productiva")} disabled={loading}>
            {loading ? <option>Cargando…</option> : <Opts items={fac.linea_productiva} />}
          </select>
        </label>

        <label className="field">
          <span>Escolaridad</span>
          <select className="input" value={value.escolaridad ?? ""} onChange={onSel("escolaridad")} disabled={loading}>
            {loading ? <option>Cargando…</option> : <Opts items={fac.escolaridad} />}
          </select>
        </label>

        <label className="field">
          <span>Sexo</span>
          <select className="input" value={value.sexo ?? ""} onChange={onSel("sexo")} disabled={loading}>
            {loading ? <option>Cargando…</option> : <Opts items={fac.sexo} />}
          </select>
        </label>
      </div>
    </section>
  );
}
