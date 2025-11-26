from fastapi import APIRouter, Response, Query
from fastapi.responses import StreamingResponse
from typing import Literal
import pandas as pd
import io
from ..services.duck import Duck
from ..services.meta import read_meta
from ..services.cache import set_cache_headers
from ..services.textnorm import norm_corregimiento_py, norm_vereda_py
from ..core.config import settings
from ..models.responses import Meta

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
):
    con = Duck.ro()

    # Normalizadores SQL (mismos que ya usas en filtros)
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

    # WHERE según tus helpers existentes (idéntico a antes)
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

    # Determinar columna de orden
    dir_sql = "ASC" if order_dir.lower() == "asc" else "DESC"
    # columnas reales de la vista
    cols = list(con.execute("SELECT * FROM v_ruea LIMIT 0").fetch_df().columns)

    if order_by.lower() in ("corregimiento", "corregimiento_norm"):
        order_expr = corr_sql
    elif order_by.lower() in ("vereda", "vereda_norm"):
        order_expr = ver_sql
    else:
        # si no existe, cae a primera columna
        order_col = order_by if order_by in cols else (cols[0] if cols else "documento")
        order_expr = f"{order_col}"

    sql = f"{base} ORDER BY {order_expr} {dir_sql} NULLS LAST LIMIT ? OFFSET ?"
    params += [limit, offset]

    df = con.execute(sql, params).fetch_df()

    if campos:
        keep = [c.strip() for c in campos.split(",") if c.strip() in df.columns]
        if keep: df = df[keep]

    data = df.to_dict("records")
    set_cache_headers(resp, etag_source=str(hash((len(data), corregimiento, vereda, linea_productiva, escolaridad, sexo, order_by, order_dir))))
    return {"count": len(data), "items": data}

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
def ruea_facetas():
    con = Duck.ro()

    # 1) Obtener columnas de forma segura (sin abrir result sets vacíos)
    try:
        # Opción A (súper simple con DuckDB):
        cols = con.table("v_ruea").columns
        # Opción B (alternativa igualmente robusta):
        # cols = [r[1] for r in con.execute("PRAGMA table_info('v_ruea')").fetchall()]
    except Exception:
        # Si la vista no existe (no hay refresh), no rompas
        return {
            "corregimiento": [],
            "vereda": [],
            "linea_productiva": [],
            "escolaridad": [],
            "sexo": [],
        }

    res: dict[str, list[str]] = {}

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

    if "corregimiento" in cols:
        q = f"""SELECT DISTINCT {corr_sql} AS corregimiento
                FROM v_ruea
                WHERE COALESCE(corregimiento,'') <> ''
                ORDER BY 1"""
        res["corregimiento"] = [r[0] for r in con.execute(q).fetchall()]
    else:
        res["corregimiento"] = []

    if "vereda" in cols:
        q = f"""SELECT DISTINCT {ver_sql} AS vereda
                FROM v_ruea
                WHERE COALESCE(vereda,'') <> ''
                ORDER BY 1"""
        res["vereda"] = [r[0] for r in con.execute(q).fetchall()]
    else:
        res["vereda"] = []

    if "linea_productiva" in cols:
        q = "SELECT DISTINCT LOWER(TRIM(linea_productiva)) FROM v_ruea WHERE COALESCE(linea_productiva,'')<>'' ORDER BY 1"
        res["linea_productiva"] = [r[0] for r in con.execute(q).fetchall()]
    else:
        res["linea_productiva"] = []

    if "escolaridad" in cols:
        q = "SELECT DISTINCT LOWER(TRIM(escolaridad)) FROM v_ruea WHERE COALESCE(escolaridad,'')<>'' ORDER BY 1"
        res["escolaridad"] = [r[0] for r in con.execute(q).fetchall()]
    else:
        res["escolaridad"] = []

    if "sexo" in cols:
        q = "SELECT DISTINCT LOWER(TRIM(sexo)) FROM v_ruea WHERE COALESCE(sexo,'')<>'' ORDER BY 1"
        res["sexo"] = [r[0] for r in con.execute(q).fetchall()]
    else:
        res["sexo"] = []

    return res

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
    total = con.execute(base.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]

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


