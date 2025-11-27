import React from "react";

type Props = {
  columns: string[];
  rows: Record<string, any>[];
  onSort?: (col: string) => void;
  orderBy?: string;
  orderDir?: "asc" | "desc";
  className?: string;
};

export default function DataTable({
  columns, rows, onSort, orderBy, orderDir, className,
}: Props) {
  return (
    <div className={`table-wrap ${className || ""}`}>
      <table className="tbl">
        <thead>
          <tr>
            {columns.map((c) => {
              const active = orderBy === c;
              const arrow = active ? (orderDir === "asc" ? " ▲" : " ▼") : "";
              return (
                <th key={c} className={active ? "th active" : "th"}>
                  <button className="th-btn" onClick={() => onSort?.(c)} title={`Ordenar por ${c}`}>
                    {c}{arrow}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="tr">
              {columns.map((c) => (
                <td key={c} className="td" title={formatCell(r[c])}>
                  {formatCell(r[c])}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="td empty" colSpan={columns.length || 1}>Sin resultados</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(v: any) {
  if (v == null) return "";
  if (typeof v === "number") return v.toLocaleString("es-CO");
  if (typeof v === "boolean") return v ? "Sí" : "No";
  return String(v);
}
