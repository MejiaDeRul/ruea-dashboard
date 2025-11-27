// src/api.ts
export type OrderDir = "asc" | "desc";

export type FiltersState = {
  corregimiento?: string;
  vereda?: string;
  linea_productiva?: string;
  escolaridad?: string;
  sexo?: string;
};

export type RueaQuery = FiltersState & {
  order_by?: string;
  order_dir?: OrderDir;
  limit?: number;
  offset?: number;
};

export type RueaItem = Record<string, any>;

type RueaRespA = { total: number; limit: number; offset: number; items: RueaItem[] };
type RueaRespB = { count: number; items: RueaItem[]; limit?: number; offset?: number };

export type Facetas = {
  corregimiento: string[];
  vereda: string[];
  linea_productiva: string[];
  escolaridad: string[];
  sexo: string[];
};

const BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? ""; // "" -> usa proxy de Vite

function toQS(params: Record<string, any>) {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== "") u.set(k, String(v));
  });
  return u.toString();
}

async function http<T>(path: string, params?: Record<string, any>): Promise<T> {
  const qs = params ? `?${toQS(params)}` : "";
  const url = `${BASE}/api/v1${path}${qs}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    let detail = "";
    try { const e = await res.json(); detail = e?.detail ?? ""; } catch {}
    throw new Error(`HTTP ${res.status} ${res.statusText}${detail ? ` - ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

// === Endpoints ===
export async function getRuea(q: RueaQuery) {
  return http<RueaRespA | RueaRespB>("/ruea", q);
}

export async function getFacetas(f: FiltersState) {
  return http<Facetas>("/ruea/facetas", f);
}

// === Utilidades internas para fallback ===
function uniqSorted(values: (string | undefined | null)[]): string[] {
  const set = new Set<string>();
  for (const v of values) {
    if (v == null) continue;
    const s = String(v).trim();
    if (!s) continue;
    set.add(s);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, "es"));
}

function pick<T extends Record<string, any>>(rows: T[], key: string): string[] {
  return rows.map(r => {
    const v = r?.[key];
    return v == null ? "" : String(v).trim();
  });
}

// === Fallback: si /ruea/facetas falla, calculamos desde /ruea ===
export async function getFacetasWithFallback(
  f: FiltersState,
  options?: { sampleLimit?: number }
): Promise<Facetas> {
  try {
    return await getFacetas(f);
  } catch (e) {
    // Calcula facetas client-side con una muestra amplia
    const limit = options?.sampleLimit ?? 5000;
    const data = await getRuea({ ...f, limit, offset: 0, order_by: "documento", order_dir: "asc" });
    // @ts-ignore
    const items: RueaItem[] = (data as any).items ?? [];
    return {
      corregimiento: uniqSorted(pick(items, "corregimiento")),
      vereda: uniqSorted(pick(items, "vereda")),
      linea_productiva: uniqSorted(pick(items, "linea_productiva")),
      escolaridad: uniqSorted(pick(items, "escolaridad")),
      sexo: uniqSorted(pick(items, "sexo")),
    };
  }
}

export type StatItem = { name: string; value: number };

export async function getRueaStats(
  by: "corregimiento" | "vereda" | "linea_productiva" | "escolaridad" | "sexo",
  filters: FiltersState,
  top?: number
) {
  const params: any = { ...filters, by };
  if (top) params.top = top;
  // reutilizamos http()
  return http<{ items: StatItem[] }>("/ruea/stats", params);
}
