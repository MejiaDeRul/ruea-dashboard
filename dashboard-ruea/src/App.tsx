import { useEffect, useMemo, useState } from "react";
import Filters from "./components/Filters";
import Table from "./components/Table";
import { buildDownloadUrl, getRuea, getRueaSummary } from "./api";
import type { RueaFilters } from "./api";


const PAGE_SIZE = 50;

export default function App() {
  const [filters, setFilters] = useState<RueaFilters>({ order_by: "documento", order_dir: "asc" });
  const [data, setData] = useState<{count:number, items:any[]}>({count:0, items:[]});
  const [summary, setSummary] = useState<{ total:number; top_corregimiento:any[]; top_vereda:any[] } | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query: RueaFilters = useMemo(() => ({
    ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE,
  }), [filters, page]);

  async function fetchData() {
    setLoading(true); setError(null);
    try {
      const [list, sum] = await Promise.all([
        getRuea(query),
        getRueaSummary(filters), // resumen no necesita paginación
      ]);
      setData(list);
      setSummary(sum);
    } catch (e:any) {
      setError(e.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchData(); },
    [query.offset, query.corregimiento, query.vereda, query.linea_productiva, query.escolaridad, query.sexo, query.order_by, query.order_dir]
  );

  const hasMore = data.items.length === PAGE_SIZE;
  const csvUrl  = buildDownloadUrl("csv",  filters);
  const xlsxUrl = buildDownloadUrl("xlsx", filters);

  const onSort = (col: string) => {
    // columnas especiales para orden normalizado:
    const special = ["corregimiento", "vereda"];
    const target = special.includes(col.toLowerCase()) ? col.toLowerCase() : col;
    setFilters(f => ({
      ...f,
      order_by: target,
      order_dir: f.order_by === target && f.order_dir === "asc" ? "desc" : "asc",
    }));
    setPage(0);
  };

  return (
    <div className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-3">RUEA — Consulta pública</h1>

      {/* Resumen */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div className="border rounded p-3">
          <div className="text-sm text-gray-600">Total (con filtros)</div>
          <div className="text-2xl font-semibold">{summary?.total ?? "…"}</div>
        </div>
        <div className="border rounded p-3">
          <div className="text-sm text-gray-600">Top 5 Corregimientos</div>
          <ul className="text-sm mt-1">
            {summary?.top_corregimiento?.map((x, i) => <li key={i}>{x.name} — {x.total}</li>) ?? <li>…</li>}
          </ul>
        </div>
        <div className="border rounded p-3">
          <div className="text-sm text-gray-600">Top 5 Veredas</div>
          <ul className="text-sm mt-1">
            {summary?.top_vereda?.map((x, i) => <li key={i}>{x.name} — {x.total}</li>) ?? <li>…</li>}
          </ul>
        </div>
      </div>

      <Filters
        values={filters}
        onChange={(patch) => { setPage(0); setFilters(f => ({...f, ...patch})); }}
        onSearch={() => { setPage(0); fetchData(); }}
      />

      <div className="flex gap-2 mt-3">
        <a className="border rounded px-3 py-2" href={csvUrl}  target="_blank" rel="noreferrer">Descargar CSV</a>
        <a className="border rounded px-3 py-2" href={xlsxUrl} target="_blank" rel="noreferrer">Descargar XLSX</a>
      </div>

      {loading && <div className="mt-4">Cargando…</div>}
      {error && <div className="mt-4 text-red-600">{error}</div>}
      {!loading && !error && (
        <Table
          rows={data.items}
          page={page}
          pageSize={PAGE_SIZE}
          onPrev={()=>setPage(p=>Math.max(0,p-1))}
          onNext={()=>setPage(p=>p+1)}
          hasMore={hasMore}
          sortBy={filters.order_by}
          sortDir={filters.order_dir}
          onSort={onSort}
        />
      )}
    </div>
  );
}
