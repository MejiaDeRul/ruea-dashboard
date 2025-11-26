const BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "";

export type RueaItem = Record<string, any>;

export type RueaResponse = {
  count: number;
  items: RueaItem[];
};

export type RueaFilters = {
  corregimiento?: string;
  vereda?: string;
  linea_productiva?: string;
  escolaridad?: string;
  sexo?: string;
  campos?: string;
  order_by?: string;      // <-- nuevo
  order_dir?: "asc"|"desc"; // <-- nuevo
  limit?: number;
  offset?: number;
};

export async function getRueaSummary(filters: RueaFilters) {
  const res = await fetch(`${BASE}/api/v1/ruea/summary${qs(filters)}`);
  if (!res.ok) throw new Error("Error obteniendo resumen");
  return res.json() as Promise<{ total:number; top_corregimiento:{name:string,total:number}[]; top_vereda:{name:string,total:number}[] }>;
}


export async function getFacetas() {
  const res = await fetch(`${BASE}/api/v1/ruea/facetas`);
  if (!res.ok) throw new Error("Error obteniendo facetas");
  return res.json() as Promise<{
    corregimiento: string[];
    vereda: string[];
    linea_productiva: string[];
    escolaridad: string[];
    sexo: string[];
  }>;
}

function qs(params: Record<string, any>) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function getRuea(filters: RueaFilters): Promise<RueaResponse> {
  const res = await fetch(`${BASE}/api/v1/ruea${qs(filters)}`);
  if (!res.ok) throw new Error("Error obteniendo RUEA");
  return res.json();
}

export function buildDownloadUrl(fmt: "csv" | "xlsx", filters: RueaFilters) {
  return `${BASE}/api/v1/ruea/download.${fmt}${qs(filters)}`;
}

export type Facetas = {
  corregimiento: string[];
  vereda: string[];
  linea_productiva: string[];
  escolaridad: string[];
  sexo: string[];
};

function uniqSorted(values: (string | undefined | null)[]) {
  return Array.from(
    new Set(
      values
        .map(v => (v ?? "").toString().toLowerCase().trim())
        .filter(Boolean)
    )
  ).sort();
}

/** Intenta /ruea/facetas; si viene vacío o falla, deriva facetas desde una muestra de /ruea */
export async function getFacetasWithFallback(): Promise<Facetas> {
  try {
    const f = await getFacetas();
    const hasData = Object.values(f).some(arr => Array.isArray(arr) && arr.length > 0);
    if (hasData) return f;
  } catch {
    // sigue al fallback
  }

  // Fallback: muestra de /ruea (ajusta limit si quieres más)
  const sample = await getRuea({ limit: 1000 });
  const items = sample.items || [];

  const take = (k: string) => uniqSorted(items.map((it: any) => it?.[k]));
  return {
    corregimiento: take("corregimiento"),
    vereda: take("vereda"),
    linea_productiva: take("linea_productiva"),
    escolaridad: take("escolaridad"),
    sexo: take("sexo"),
  };
}


