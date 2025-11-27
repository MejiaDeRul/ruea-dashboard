from fastapi import APIRouter, Response, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Literal, Any, List, Set, Dict
import pandas as pd
import io
import re
import logging
from ..services.duck import Duck
from ..services.meta import read_meta
from ..services.cache import set_cache_headers
from ..services.textnorm import norm_corregimiento_py, norm_vereda_py
from ..core.config import settings
from ..models.responses import Meta

def _safe_columns(con, view_name: str = "v_ruea") -> List[str]:
    # 1) Ruta nativa: relación de DuckDB (sirve para tablas/vistas existentes)
    try:
        return list(con.table(view_name).columns)
    except Exception:
        pass

    # 2) information_schema: incluye vistas y tablas (orden en posición)
    try:
        rows = con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
            """,
            [view_name],
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass

    # 3) Fallback con DESCRIBE (cubre casos donde info_schema no listó la vista)
    try:
        safe_ident = view_name.replace('"', '""')
        rows = con.execute(f'DESCRIBE SELECT * FROM "{safe_ident}"').fetchall()
        # en DuckDB, la 1ª columna del DESCRIBE es el nombre de columna
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass

    # 4) Si no existe la vista o aún no se ha publicado nada
    return []

def _unaccent_sql(expr: str) -> str:
    # Quita tildes/diacríticos más comunes en es-ES/es-CO tras LOWER()
    # REPLACE(REPLACE(...)) anidado porque DuckDB no trae unaccent nativo
    return (
        "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
        f"{expr}"
        ",'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ü','u'),'ñ','n')"
    )


router = APIRouter(prefix="/api/v1", tags=["public"])

@router.get("/meta", response_model=Meta)
def meta(resp: Response):
    m = read_meta()
    set_cache_headers(resp, etag_source=(m.get("version") or "none"))
    return m

@router.get("/indicadores")
def indicadores(resp: Response, anio: int | None = Query(None), eje: str | None = Query(None)):
    con = Duck.ro()
    base = "SELECT anio, eje, total, cumplimiento FROM mv_indicadores"
    where, params = [], []
    if anio is not None:
        where.append("anio = ?"); params.append(anio)
    if eje:
        where.append("eje = ?"); params.append(eje)
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY anio, eje"
    out = con.execute(base, params).fetch_df().to_dict("records")
    set_cache_headers(resp, etag_source=str(out.__hash__()))
    return out

@router.get("/comercializacion")
def comercializacion(resp: Response, anio: int | None = Query(None), estrategia: str | None = Query(None)):
    con = Duck.ro()
    base = "SELECT anio, estrategia, total, operaciones FROM mv_comercializacion"
    where, params = [], []
    if anio is not None:
        where.append("anio = ?"); params.append(anio)
    if estrategia:
        where.append("estrategia = ?"); params.append(estrategia)
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY anio, estrategia"
    out = con.execute(base, params).fetch_df().to_dict("records")
    set_cache_headers(resp, etag_source=str(out.__hash__()))
    return out

@router.get("/ruea")
def ruea(
    resp: Response,
    corregimiento: str | None = Query(None),
    vereda: str | None = Query(None),
    linea_productiva: str | None = Query(None),
    escolaridad: str | None = Query(None),
    sexo: str | None = Query(None),
    campos: str | None = Query(None),
    order_by: str = Query("documento", description="columna o 'corregimiento'/'vereda' para orden normalizado"),
    order_dir: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    debug: bool = Query(False),
):
    con = Duck.ro()
    view = "v_ruea"

    # columnas disponibles
    cols = _safe_columns(con, view)
    if not cols:
        return {"total": 0, "limit": limit, "offset": offset, "items": []}
    cols_set = set(cols)
    has = cols_set.__contains__

    # helper local para quitar tildes en SQL
    def _unaccent_sql(expr: str) -> str:
        return (
            "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
            f"{expr}"
            ",'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ü','u'),'ñ','n')"
        )

    # normalizadores simétricos (Python/SQL) para filtros de igualdad/LIKE
    def _norm_py(s: str) -> str:
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        s = re.sub(r"\s+", " ", s.lower()).strip()
        return s

    def _norm_sql_col(col: str) -> str:
        # lower + unaccent + trim + colapso de espacios
        return (
            "REGEXP_REPLACE("
            + _unaccent_sql(f"LOWER(TRIM(COALESCE({col},'')))")
            + ",'\\s+',' '"
            + ")"
        )

    # expresiones normalizadas para corregimiento y vereda
    _corr_base = _unaccent_sql("LOWER(COALESCE(corregimiento,''))")
    corr_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_corr_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*corregimiento(\\s+de)?\\s+',''),"
        "'\\s+',' '"
        ")"
    )
    _ver_base = _unaccent_sql("LOWER(COALESCE(vereda,''))")
    ver_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_ver_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*veredas?(\\s+de)?\\s+',''),"
        "'^\\s*area\\s+de\\s+expansion\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    # WHERE (solo si existen las columnas)
    from ..services.textnorm import norm_corregimiento_py, norm_vereda_py

    where: list[str] = []
    binds: list[Any] = []

    if corregimiento and has("corregimiento"):
        val = norm_corregimiento_py(corregimiento)
        where.append(f"({corr_sql} = ? OR {corr_sql} LIKE ?)")
        binds += [val, f"%{val}%"]

    if vereda and has("vereda"):
        val = norm_vereda_py(vereda)
        where.append(f"({ver_sql} = ? OR {ver_sql} LIKE ?)")
        binds += [val, f"%{val}%"]

    if linea_productiva and has("linea_productiva"):
        where.append(f"{_norm_sql_col('linea_productiva')} LIKE ?")
        binds.append(f"%{_norm_py(linea_productiva)}%")

    if escolaridad and has("escolaridad"):
        where.append(f"{_norm_sql_col('escolaridad')} LIKE ?")
        binds.append(f"%{_norm_py(escolaridad)}%")

    if sexo and has("sexo"):
        where.append(f"{_norm_sql_col('sexo')} LIKE ?")
        binds.append(f"%{_norm_py(sexo)}%")

    base = f"SELECT * FROM {view}"
    if where:
        base += " WHERE " + " AND ".join(where)

    # TOTAL robusto (sin ORDER/LIMIT)
    count_sql = f"SELECT COUNT(*) FROM ({base}) AS t"
    row = con.execute(count_sql, binds).fetchone()
    total = int(row[0]) if row else 0

    # === ORDEN ===
    order_dir_norm = (order_dir or "asc").strip().lower()
    dir_sql = "ASC" if order_dir_norm == "asc" else "DESC"

    order_by_norm = (order_by or "").strip()
    if order_by_norm not in cols:
        order_by_norm = "documento" if "documento" in cols else cols[0]

    if order_by_norm.lower() in ("corregimiento", "corregimiento_norm") and has("corregimiento"):
        order_expr = corr_sql
    elif order_by_norm.lower() in ("vereda", "vereda_norm") and has("vereda"):
        order_expr = ver_sql
    else:
        safe = order_by_norm.replace('"', '""')
        order_expr = f'"{safe}"'

    # clave para mandar nulos/vacíos al final sin romper tipos numéricos
    ord_cast  = f"NULLIF(TRIM(CAST({order_expr} AS VARCHAR)), '')"
    nulls_key = f"CASE WHEN {ord_cast} IS NULL THEN 1 ELSE 0 END"

    # consulta final (sin NULLS LAST) + ejecución segura
    sql = f"{base} ORDER BY {nulls_key} ASC, {order_expr} {dir_sql} LIMIT ? OFFSET ?"
    try:
        res = con.execute(sql, binds + [int(limit), int(offset)])
        rows = res.fetchall() or []
    except Exception as e:
        # Si prefieres, devuelve 500 JSON en vez de tumbar conexión:
        # from fastapi import HTTPException
        # raise HTTPException(status_code=500, detail=f"ruea_query_failed: {e}")
        raise

    # subconjunto de columnas (campos)
    selected_cols = cols
    if campos:
        keep = [c.strip() for c in campos.split(",") if c.strip() in cols]
        if keep:
            selected_cols = keep

    # mapeo manual fila→dict (evita fetch_df/pyarrow)
    col_index = {c: i for i, c in enumerate(cols)}
    items: list[dict[str, Any]] = []
    for tup in rows:
        obj = {c: (tup[col_index[c]] if c in col_index and col_index[c] < len(tup) else None)
               for c in selected_cols}
        items.append(obj)

    # cache/etag
    set_cache_headers(
        resp,
        etag_source=str(
            hash(
                (
                    total,
                    corregimiento, vereda, linea_productiva, escolaridad, sexo,
                    order_by_norm, order_dir_norm, limit, offset
                )
            )
        ),
    )

    payload = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
    if debug:
        payload["_debug"] = {
            "sql": sql,
            "binds": binds + [int(limit), int(offset)],
        }
    return payload


def _build_ruea_query_and_params(
    corregimiento: str | None,
    vereda: str | None,
    linea_productiva: str | None,
    escolaridad: str | None,
    sexo: str | None,
):
    # mismas expr. SQL de normalización que ya tienes:
    corr_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE(LOWER(COALESCE(corregimiento,'')),'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*corregimiento(\\s+de)?\\s+',''),"
        "'\\s+',' '"
        ")"
    )
    ver_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE(LOWER(COALESCE(vereda,'')),'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*veredas?(\\s+de)?\\s+',''),"
        "'^\\s*area\\s+de\\s+expansion\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    base = "SELECT * FROM v_ruea"
    where, params = [], []
    from ..services.textnorm import norm_corregimiento_py, norm_vereda_py
    if corregimiento:
        val = norm_corregimiento_py(corregimiento)
        where.append(f"({corr_sql} = ? OR {corr_sql} LIKE ?)"); params += [val, f"%{val}%"]
    if vereda:
        val = norm_vereda_py(vereda)
        where.append(f"({ver_sql} = ? OR {ver_sql} LIKE ?)"); params += [val, f"%{val}%"]
    if linea_productiva:
        where.append("LOWER(linea_productiva)=LOWER(?)"); params.append(linea_productiva)
    if escolaridad:
        where.append("LOWER(escolaridad)=LOWER(?)"); params.append(escolaridad)
    if sexo:
        where.append("LOWER(sexo)=LOWER(?)"); params.append(sexo)

    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY 1"
    return base, params

@router.get("/ruea/download.csv")
def ruea_download_csv(
    corregimiento: str | None = Query(None),
    vereda: str | None = Query(None),
    linea_productiva: str | None = Query(None),
    escolaridad: str | None = Query(None),
    sexo: str | None = Query(None),
    campos: str | None = Query(None),
):
    con = Duck.ro()
    sql, params = _build_ruea_query_and_params(corregimiento, vereda, linea_productiva, escolaridad, sexo)
    df = con.execute(sql, params).fetch_df()
    if campos:
        keep = [c.strip() for c in campos.split(",") if c.strip() in df.columns]
        if keep: df = df[keep]
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ruea.csv"})

@router.get("/ruea/download.xlsx")
def ruea_download_xlsx(
    corregimiento: str | None = Query(None),
    vereda: str | None = Query(None),
    linea_productiva: str | None = Query(None),
    escolaridad: str | None = Query(None),
    sexo: str | None = Query(None),
    campos: str | None = Query(None),
):
    con = Duck.ro()
    sql, params = _build_ruea_query_and_params(corregimiento, vereda, linea_productiva, escolaridad, sexo)
    df = con.execute(sql, params).fetch_df()
    if campos:
        keep = [c.strip() for c in campos.split(",") if c.strip() in df.columns]
        if keep: df = df[keep]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="ruea")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=ruea.xlsx"})

@router.get("/ruea/facetas")
def ruea_facetas(
    corregimiento: str | None = Query(None),
    vereda: str | None = Query(None),
    linea_productiva: str | None = Query(None),
    escolaridad: str | None = Query(None),
    sexo: str | None = Query(None),
    debug: bool = Query(False),
):
    con = Duck.ro()
    view = "v_ruea"

    cols: List[str] = _safe_columns(con, view)
    if not cols:
        return {"corregimiento": [], "vereda": [], "linea_productiva": [], "escolaridad": [], "sexo": []}
    has = set(cols).__contains__

    # ===== Helpers iguales a /ruea =====
    def _unaccent_sql(expr: str) -> str:
        return (
            "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
            f"{expr}"
            ",'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ü','u'),'ñ','n')"
        )

    def _norm_sql_col(col: str) -> str:
        # lower + unaccent + trim + colapso de espacios
        return (
            "REGEXP_REPLACE("
            + _unaccent_sql(f"LOWER(TRIM(COALESCE({col},'')))")
            + ",'\\s+',' '"
            + ")"
        )

    # Normalizadores de corregimiento/vereda (idénticos a /ruea)
    _corr_base = _unaccent_sql("LOWER(COALESCE(corregimiento,''))")
    corr_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_corr_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*corregimiento(\\s+de)?\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    _ver_base = _unaccent_sql("LOWER(COALESCE(vereda,''))")
    ver_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_ver_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*veredas?(\\s+de)?\\s+',''),"
        "'^\\s*area\\s+de\\s+expansion\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    # Normalizadores python iguales a los usados en /ruea
    from ..services.textnorm import norm_corregimiento_py, norm_vereda_py

    def build_filters(skip: str | None = None) -> tuple[list[str], list[Any]]:
        where: list[str] = []
        binds: list[Any] = []
        if skip != "corregimiento" and corregimiento and has("corregimiento"):
            val = norm_corregimiento_py(corregimiento)
            where.append(f"({corr_sql} = ? OR {corr_sql} LIKE ?)")
            binds += [val, f"%{val}%"]
        if skip != "vereda" and vereda and has("vereda"):
            val = norm_vereda_py(vereda)
            where.append(f"({ver_sql} = ? OR {ver_sql} LIKE ?)")
            binds += [val, f"%{val}%"]
        if skip != "linea_productiva" and linea_productiva and has("linea_productiva"):
            where.append(f"{_norm_sql_col('linea_productiva')} LIKE ?")
            binds.append(f"%{linea_productiva.lower().strip()}%")
        if skip != "escolaridad" and escolaridad and has("escolaridad"):
            where.append(f"{_norm_sql_col('escolaridad')} LIKE ?")
            binds.append(f"%{escolaridad.lower().strip()}%")
        if skip != "sexo" and sexo and has("sexo"):
            where.append(f"{_norm_sql_col('sexo')} LIKE ?")
            binds.append(f"%{sexo.lower().strip()}%")
        return where, binds

    def distinct_for(expr_sql: str, required_col: str, skip: str | None) -> list[str]:
        if not has(required_col):
            return []
        where, binds = build_filters(skip)
        sql = f"SELECT DISTINCT TRIM({expr_sql}) AS v FROM {view}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (" AND " if where else " WHERE ") + f"TRIM(COALESCE({expr_sql},''))<>''"
        sql += " ORDER BY 1"
        try:
            rows = con.execute(sql, binds).fetchall()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"facetas_query_failed: {e}")
        return [r[0] for r in rows] if rows else []

    out = {
        "corregimiento":   distinct_for(corr_sql, "corregimiento", "corregimiento"),
        "vereda":          distinct_for(ver_sql, "vereda", "vereda"),
        "linea_productiva":distinct_for(_norm_sql_col("linea_productiva"), "linea_productiva", "linea_productiva"),
        "escolaridad":     distinct_for(_norm_sql_col("escolaridad"), "escolaridad", "escolaridad"),
        "sexo":            distinct_for(_norm_sql_col("sexo"), "sexo", "sexo"),
    }
    if debug:
        out["_debug"] = {"cols": cols}
    return out

@router.get("/ruea/summary")
def ruea_summary(
    corregimiento: str | None = Query(None),
    vereda: str | None = Query(None),
    linea_productiva: str | None = Query(None),
    escolaridad: str | None = Query(None),
    sexo: str | None = Query(None),
):
    con = Duck.ro()

    corr_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE(LOWER(COALESCE(corregimiento,'')),'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*corregimiento(\\s+de)?\\s+',''),"
        "'\\s+',' '"
        ")"
    )
    ver_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE(LOWER(COALESCE(vereda,'')),'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*veredas?(\\s+de)?\\s+',''),"
        "'^\\s*area\\s+de\\s+expansion\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    base = "SELECT * FROM v_ruea"
    where, params = [], []
    from ..services.textnorm import norm_corregimiento_py, norm_vereda_py
    if corregimiento:
        val = norm_corregimiento_py(corregimiento)
        where.append(f"({corr_sql} = ? OR {corr_sql} LIKE ?)"); params += [val, f"%{val}%"]
    if vereda:
        val = norm_vereda_py(vereda)
        where.append(f"({ver_sql} = ? OR {ver_sql} LIKE ?)"); params += [val, f"%{val}%"]
    if linea_productiva:
        where.append("LOWER(linea_productiva) = LOWER(?)"); params.append(linea_productiva)
    if escolaridad:
        where.append("LOWER(escolaridad) = LOWER(?)"); params.append(escolaridad)
    if sexo:
        where.append("LOWER(sexo) = LOWER(?)"); params.append(sexo)
    if where:
        base += " WHERE " + " AND ".join(where)

    # total
    base_no_paging = re.sub(r"\s+ORDER\s+BY\s+.+$", "", base, flags=re.IGNORECASE)
    base_no_paging = re.sub(r"\s+LIMIT\s+\S+(?:\s+OFFSET\s+\S+)?", "", base_no_paging, flags=re.IGNORECASE)
    count_sql = f"SELECT COUNT(*) FROM ({base_no_paging}) AS t"
    row = con.execute(count_sql, params).fetchone()
    total = int(row[0]) if row else 0


    # top-5 corregimientos normalizados
    q_top_corr = f"""
    WITH base AS ({base})
    SELECT {corr_sql} AS nombre, COUNT(*) AS total
    FROM base
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 5
    """
    top_corr = [{"name": r[0] or "", "total": r[1]} for r in con.execute(q_top_corr, params).fetchall()]

    # top-5 veredas normalizadas
    q_top_ver = f"""
    WITH base AS ({base})
    SELECT {ver_sql} AS nombre, COUNT(*) AS total
    FROM base
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 5
    """
    top_ver = [{"name": r[0] or "", "total": r[1]} for r in con.execute(q_top_ver, params).fetchall()]

    return {"total": int(total), "top_corregimiento": top_corr, "top_vereda": top_ver}

@router.get("/ruea/stats")
def ruea_stats(
    by: Literal["corregimiento","vereda","linea_productiva","escolaridad","sexo"] = Query(...),
    top: int = Query(0, ge=0, le=1000),
    corregimiento: str | None = None,
    vereda: str | None = None,
    linea_productiva: str | None = None,
    escolaridad: str | None = None,
    sexo: str | None = None,
):
    con = Duck.ro()
    view = "v_ruea"
    cols = _safe_columns(con, view)
    if not cols:
        return {"items": []}
    has = set(cols).__contains__

    # === helpers SQL locales (evita NameError) ===
    def _unaccent_sql(expr: str) -> str:
        return (
            "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
            f"{expr}"
            ",'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ü','u'),'ñ','n')"
        )

    def _norm_sql_col(col: str) -> str:
        return (
            "REGEXP_REPLACE("
            + _unaccent_sql(f"LOWER(TRIM(COALESCE({col},'')))")
            + ",'\\s+',' '"
            + ")"
        )

    _corr_base = _unaccent_sql("LOWER(COALESCE(corregimiento,''))")
    corr_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_corr_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*corregimiento(\\s+de)?\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    _ver_base = _unaccent_sql("LOWER(COALESCE(vereda,''))")
    ver_sql = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        f"REGEXP_REPLACE({_ver_base},'^\\s*\\d+\\s*-\\s*',''),"
        "'^\\s*veredas?(\\s+de)?\\s+',''),"
        "'^\\s*area\\s+de\\s+expansion\\s+',''),"
        "'\\s+',' '"
        ")"
    )

    expr_map = {
        "corregimiento": corr_sql if has("corregimiento") else None,
        "vereda": ver_sql if has("vereda") else None,
        "linea_productiva": _norm_sql_col("linea_productiva") if has("linea_productiva") else None,
        "escolaridad": _norm_sql_col("escolaridad") if has("escolaridad") else None,
        "sexo": _norm_sql_col("sexo") if has("sexo") else None,
    }
    expr = expr_map.get(by)
    if not expr:
        return {"items": []}

    # filtros (idénticos a /ruea)
    from ..services.textnorm import norm_corregimiento_py, norm_vereda_py
    where, binds = [], []

    if corregimiento and has("corregimiento"):
        val = norm_corregimiento_py(corregimiento)
        where.append(f"({corr_sql} = ? OR {corr_sql} LIKE ?)")
        binds += [val, f"%{val}%"]

    if vereda and has("vereda"):
        val = norm_vereda_py(vereda)
        where.append(f"({ver_sql} = ? OR {ver_sql} LIKE ?)")
        binds += [val, f"%{val}%"]

    if linea_productiva and has("linea_productiva"):
        where.append(f"{_norm_sql_col('linea_productiva')} LIKE ?")
        binds.append(f"%{linea_productiva.lower().strip()}%")

    if escolaridad and has("escolaridad"):
        where.append(f"{_norm_sql_col('escolaridad')} LIKE ?")
        binds.append(f"%{escolaridad.lower().strip()}%")

    if sexo and has("sexo"):
        where.append(f"{_norm_sql_col('sexo')} LIKE ?")
        binds.append(f"%{sexo.lower().strip()}%")

    sql = f"SELECT {expr} AS name, COUNT(*) AS value FROM {view}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY 1 ORDER BY 2 DESC"
    if top and top > 0:
        sql += f" LIMIT {int(top)}"

    try:
        rows = con.execute(sql, binds).fetchall() or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"stats_query_failed: {e}")

    return {"items": [{"name": r[0], "value": r[1]} for r in rows if r and r[0] is not None]}


