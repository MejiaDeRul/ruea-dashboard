import React, { useCallback, useEffect, useMemo, useState } from "react";
import Filters from "../../components/Filters";
import DataTable from "../../components/DataTable";
import { getRuea, type RueaItem, type RueaQuery, type OrderDir, type FiltersState } from "../../api";

const BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? ""; // "" => usa proxy de Vite

export default function General() {
  // --- estado de filtros / orden / paginado ---
  const [filters, setFilters]   = useState<FiltersState>({});
  const [orderBy, setOrderBy]   = useState<string>("documento");
  const [orderDir, setOrderDir] = useState<OrderDir>("asc");
  const [limit, setLimit]       = useState<number>(50);
  const [offset, setOffset]     = useState<number>(0);

  // --- datos ---
  const [items, setItems]   = useState<RueaItem[]>([]);
  const [total, setTotal]   = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError]     = useState<string>("");

  // query unificado
  const query: RueaQuery = useMemo(
    () => ({ ...filters, order_by: orderBy, order_dir: orderDir, limit, offset }),
    [filters, orderBy, orderDir, limit, offset]
  );

  // carga
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await getRuea(query);
      // soporta {total} o {count}
      // @ts-ignore
      const nextItems: RueaItem[] = (res as any).items ?? [];
      // @ts-ignore
      const nextTotal: number = (res as any).total ?? (res as any).count ?? nextItems.length ?? 0;
      setItems(nextItems);
      setTotal(nextTotal);
    } catch (e: any) {
      setError(e?.message || "Error cargando datos");
      setItems([]); setTotal(0);
    } finally { setLoading(false); }
  }, [query]);

  useEffect(() => { load(); }, [load]);

  // filtros → reinicia paginación
  const onFiltersChange = (next: FiltersState) => { setFilters(next); setOffset(0); };

  // columnas (prioriza claves comunes)
  const columns = useMemo(() => {
    const pref = ["documento","cedula","corregimiento","vereda","linea_productiva","escolaridad","sexo"];
    if (!items.length) return pref;
    const cols = Object.keys(items[0] ?? {});
    return [...new Set([...pref.filter(c=>cols.includes(c)), ...cols])];
  }, [items]);

  // orden
  const onSort = (col: string) => {
    if (orderBy === col) setOrderDir(orderDir === "asc" ? "desc" : "asc");
    else { setOrderBy(col); setOrderDir("asc"); }
    setOffset(0);
  };

  // paginación
  const canPrev = offset > 0;
  const canNext = offset + limit < total;
  const goPrev = () => canPrev && setOffset(Math.max(0, offset - limit));
  const goNext = () => canNext && setOffset(offset + limit);

  // QS para descargas (mismos filtros + orden; sin limit/offset para traer todo)
  const dlQS = useMemo(() => {
    const u = new URLSearchParams();
    Object.entries(filters).forEach(([k,v])=>{ if(v) u.set(k, String(v)); });
    if (orderBy) u.set("order_by", orderBy);
    if (orderDir) u.set("order_dir", orderDir);
    return u.toString();
  }, [filters, orderBy, orderDir]);

  const csvHref  = `${BASE}/api/v1/ruea/download.csv${dlQS ? `?${dlQS}` : ""}`;
  const xlsxHref = `${BASE}/api/v1/ruea/download.xlsx${dlQS ? `?${dlQS}` : ""}`;

  return (
    <>
      <h1 className="h1">Dashboard General</h1>
      <p className="muted">Vista principal con filtros, tabla y descargas.</p>

      {/* Filtros dinámicos */}
      <Filters value={filters} onChange={onFiltersChange} />

      {/* KPIs */}
      <section className="grid3 mt-4">
        <div className="card kpi"><div className="metric">{total.toLocaleString("es-CO")}</div><div className="label">Registros</div></div>
        <div className="card kpi"><div className="metric">{limit}</div><div className="label">Por página</div></div>
        <div className="card kpi"><div className="metric">{Math.floor(offset / Math.max(1, limit)) + 1}</div><div className="label">Página</div></div>
      </section>

      {/* Tabla + descargas */}
      <section className="card mt-4">
        <div className="flex between mb-2">
          <h2 className="t-sub">Resultados</h2>
          <div className="actions">
            <a className="btn" href={csvHref}  target="_blank" rel="noreferrer">CSV</a>
            <a className="btn" href={xlsxHref} target="_blank" rel="noreferrer">XLSX</a>
          </div>
        </div>

        {error && <div className="alert">{error}</div>}
        {loading && <div className="muted">Cargando…</div>}

        <DataTable
          columns={columns}
          rows={items}
          onSort={onSort}
          orderBy={orderBy}
          orderDir={orderDir}
        />

        <div className="flex between mt-2">
          <div className="muted">Mostrando {items.length} de {total.toLocaleString("es-CO")} registros</div>
          <div className="flex gap">
            <button className="btn" onClick={goPrev} disabled={!canPrev}>← Anterior</button>
            <button className="btn" onClick={goNext} disabled={!canNext}>Siguiente →</button>
            <select className="input" value={limit} onChange={(e)=>{ setLimit(+e.target.value); setOffset(0); }}>
              {[25,50,100,200].map(n => <option key={n} value={n}>{n} / pág</option>)}
            </select>
          </div>
        </div>
      </section>
    </>
  );
}
