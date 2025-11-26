type Props = {
  rows: Record<string, any>[];
  page: number;
  pageSize: number;
  onPrev: () => void;
  onNext: () => void;
  hasMore: boolean;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  onSort?: (col: string) => void;
};

export default function Table({ rows, page, pageSize, onPrev, onNext, hasMore, sortBy, sortDir, onSort }: Props) {
  const cols = rows.length ? Object.keys(rows[0]) : [];

  const arrow = (col: string) => {
    if (sortBy !== col) return "";
    return sortDir === "asc" ? " ↑" : " ↓";
  };

  return (
    <div className="mt-4">
      <div className="overflow-auto border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className="text-left px-2 py-2 whitespace-nowrap cursor-pointer select-none"
                  onClick={() => onSort?.(c)}
                  title="Ordenar"
                >
                  {c}{arrow(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t">
                {cols.map((c) => (
                  <td key={c} className="px-2 py-1 whitespace-nowrap">{r[c] ?? ""}</td>
                ))}
              </tr>
            ))}
            {!rows.length && (
              <tr><td className="px-2 py-3 text-gray-500">Sin resultados</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-2 mt-3">
        <button className="border rounded px-3 py-1" onClick={onPrev} disabled={page===0}>Anterior</button>
        <span>Página {page+1}</span>
        <button className="border rounded px-3 py-1" onClick={onNext} disabled={!hasMore}>Siguiente</button>
      </div>
    </div>
  );
}
