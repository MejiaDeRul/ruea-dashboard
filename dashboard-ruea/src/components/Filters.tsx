import { useEffect, useState } from "react";
import { getFacetasWithFallback as getFacetas } from "../api";


type Props = {
  values: {
    corregimiento?: string;
    vereda?: string;
    linea_productiva?: string;
    escolaridad?: string;
    sexo?: string;
  };
  onChange: (patch: Partial<Props["values"]>) => void;
  onSearch: () => void;
};

export default function Filters({ values, onChange, onSearch }: Props) {
  const [fac, setFac] = useState<{
    corregimiento: string[];
    vereda: string[];
    linea_productiva: string[];
    escolaridad: string[];
    sexo: string[];
  } | null>(null);

  useEffect(() => {
    getFacetas().then(setFac).catch(console.error);
  }, []);

  const Input = (p: any) => <input className="border rounded px-2 py-1 w-full" {...p} />;
  const Select = (p: any) => <select className="border rounded px-2 py-1 w-full" {...p} />;

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div>
        <label className="text-sm">Corregimiento</label>
        {fac ? (
          <Select
            value={values.corregimiento || ""}
            onChange={(e) => onChange({ corregimiento: e.target.value || undefined })}
          >
            <option value="">(Todos)</option>
            {fac.corregimiento.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </Select>
        ) : <Input placeholder="Cargando..." disabled/>}
      </div>

      <div>
        <label className="text-sm">Vereda</label>
        {fac ? (
          <Select
            value={values.vereda || ""}
            onChange={(e) => onChange({ vereda: e.target.value || undefined })}
          >
            <option value="">(Todas)</option>
            {fac.vereda.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </Select>
        ) : <Input placeholder="Cargando..." disabled/>}
      </div>

      <div>
        <label className="text-sm">Línea productiva</label>
        {fac ? (
          <Select
            value={values.linea_productiva || ""}
            onChange={(e) => onChange({ linea_productiva: e.target.value || undefined })}
          >
            <option value="">(Todas)</option>
            {fac.linea_productiva.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </Select>
        ) : <Input placeholder="Cargando..." disabled/>}
      </div>

      <div>
        <label className="text-sm">Escolaridad</label>
        {fac ? (
          <Select
            value={values.escolaridad || ""}
            onChange={(e) => onChange({ escolaridad: e.target.value || undefined })}
          >
            <option value="">(Todas)</option>
            {fac.escolaridad.map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </Select>
        ) : <Input placeholder="Cargando..." disabled/>}
      </div>

      <div>
        <label className="text-sm">Sexo</label>
        {fac ? (
          <Select
            value={values.sexo || ""}
            onChange={(e) => onChange({ sexo: e.target.value || undefined })}
          >
            <option value="">(Todos)</option>
            {fac.sexo.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        ) : <Input placeholder="Cargando..." disabled/>}
      </div>

      <div className="flex items-end">
        <button
          className="bg-black text-white px-4 py-2 rounded w-full"
          onClick={onSearch}
        >
          Buscar
        </button>
      </div>
    </div>
  );
}
