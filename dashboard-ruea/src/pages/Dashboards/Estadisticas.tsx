// src/pages/Dashboards/Estadisticas.tsx
import React, { useEffect, useState } from "react";
import Filters from "../../components/Filters";
import { getRuea, getRueaStats, type FiltersState, type RueaItem, type StatItem } from "../../api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend
} from "recharts";

const COLORS = ["#0057B8","#0bb3b3","#ff7a00","#6e7bf2","#8ac926","#ff595e","#1982c4","#6a4c93","#ffd166"];

// ===== Normalizadores (idénticos a la idea del backend) =====
const unaccent = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
const collapse = (s: string) => s.toLowerCase().trim().replace(/\s+/g, " ");
const normCorreg = (s: string) => {
  s = unaccent(String(s ?? ""));
  s = s.replace(/^\s*\d+\s*-\s*/, "");
  s = s.replace(/^\s*corregimiento(\s+de)?\s+/i, "");
  return collapse(s);
};
const normVereda = (s: string) => {
  s = unaccent(String(s ?? ""));
  s = s.replace(/^\s*\d+\s*-\s*/, "");
  s = s.replace(/^\s*veredas?(\s+de)?\s+/i, "");
  s = s.replace(/^\s*area\s+de\s+expansion\s+/i, "");
  return collapse(s);
};
const normSimple = (s: string) => collapse(unaccent(String(s ?? "")));

function countByNorm(rows: any[], key: string, normFn: (s: string)=>string): StatItem[] {
  const m = new Map<string, number>();
  for (const r of rows) {
    const k = normFn(r?.[key] ?? "");
    if (!k) continue;
    m.set(k, (m.get(k) || 0) + 1);
  }
  return Array.from(m, ([name, value]) => ({ name, value })).sort((a,b)=>b.value-a.value);
}

// Paginación segura del endpoint /ruea (respeta limit<=1000)
async function fetchAllRuea(filters: FiltersState, pageSize = 1000, max = 20000): Promise<RueaItem[]> {
  const all: RueaItem[] = [];
  let off = 0;
  while (off < max) {
    const res = await getRuea({ ...filters, limit: pageSize, offset: off, order_by: "documento", order_dir: "asc" });
    // @ts-ignore
    const chunk: RueaItem[] = (res as any).items ?? [];
    all.push(...chunk);
    if (chunk.length < pageSize) break;
    off += pageSize;
  }
  return all;
}

export default function Estadisticas() {
  const [filters, setFilters] = useState<FiltersState>({});
  const [topVeredas, setTopVeredas] = useState<StatItem[]>([]);
  const [porLinea, setPorLinea]     = useState<StatItem[]>([]);
  const [porCorreg, setPorCorreg]   = useState<StatItem[]>([]);
  const [error, setError]           = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        setError("");

        // 1) Intento ligero: stats en backend
        const [ver, lin, corr] = await Promise.all([
          getRueaStats("vereda",           filters, 10),
          getRueaStats("linea_productiva", filters),
          getRueaStats("corregimiento",    filters),
        ]);

        const haveData =
          (ver.items?.length ?? 0) + (lin.items?.length ?? 0) + (corr.items?.length ?? 0) > 0;

        if (haveData) {
          setTopVeredas(ver.items);
          setPorLinea(lin.items);
          setPorCorreg((corr.items ?? []).slice().sort((a,b)=>a.name.localeCompare(b.name,"es")));
          return;
        }

        // 2) Fallback: agregamos en el front con normalización
        const rows = await fetchAllRuea(filters);
        setTopVeredas(countByNorm(rows, "vereda", normVereda).slice(0, 10));
        setPorLinea(countByNorm(rows, "linea_productiva", normSimple));
        setPorCorreg(countByNorm(rows, "corregimiento", normCorreg).sort((a,b)=>a.name.localeCompare(b.name,"es")));
      } catch (e:any) {
        setError(e?.message || "Error cargando estadísticas");
        // Último intento: dejar todo vacío para que la UI no reviente
        setTopVeredas([]); setPorLinea([]); setPorCorreg([]);
      }
    })();
  }, [filters]);

  return (
    <>
      <h1 className="h1">Estadísticas</h1>
      <p className="muted">Indicadores visuales sobre la base filtrada.</p>
      <Filters value={filters} onChange={setFilters} />

      {error && <div className="alert mt-2">{error}</div>}

      <section className="grid3 mt-4">
        {/* Barras: Top 10 Veredas */}
        <div className="card">
          <h3 className="t-sub">Top 10 Veredas</h3>
          <div className="chartbox">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topVeredas} margin={{ left: 8, right: 8 }}>
                <XAxis dataKey="name" hide />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value">
                  {topVeredas.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="chart-legend small">
              {topVeredas.map((d,i)=> <span key={d.name}><i style={{background:COLORS[i%COLORS.length]}}/> {d.name}</span>)}
            </div>
          </div>
        </div>

        {/* Torta: líneas productivas */}
        <div className="card">
          <h3 className="t-sub">Distribución por Línea Productiva</h3>
          <div className="chartbox">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Tooltip />
                <Pie data={porLinea} dataKey="value" nameKey="name" outerRadius={90} innerRadius={40}>
                  {porLinea.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="chart-legend small wrap">
              {porLinea.map((d,i)=> <span key={d.name}><i style={{background:COLORS[i%COLORS.length]}}/> {d.name} ({d.value})</span>)}
            </div>
          </div>
        </div>

        {/* Línea: por corregimiento */}
        <div className="card">
          <h3 className="t-sub">Registros por Corregimiento</h3>
          <div className="chartbox">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={porCorreg} margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" hide />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="chart-legend small wrap">
              {porCorreg.slice(0, 15).map((d)=> <span key={d.name}><b>{d.name}</b>: {d.value}</span>)}
              {porCorreg.length > 15 && <span>…</span>}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
