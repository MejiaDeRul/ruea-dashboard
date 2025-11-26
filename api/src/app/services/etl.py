import os, shutil, json, time
from datetime import datetime
from typing import Dict
import pandas as pd
import polars as pl
import duckdb
import io
import unicodedata
import re

from . import paths
from ..core.config import settings
from .validators import validate_df

def _ts():
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")

def _write_staging(uploaded: Dict[str, bytes]) -> str:
    ts = _ts()
    stg = os.path.join(paths.STAGING, ts)
    pq_dir = os.path.join(stg, "parquet")
    os.makedirs(pq_dir, exist_ok=True)

    # 1) leer excels → pandas → validar → polars → parquet
    written_modules = []
    for module, filelike in uploaded.items():
        # pandas lee xlsx fiable; luego convertimos a polars
        df_pd = pd.read_excel(filelike)  # engine=openpyxl por defecto
        df_pd = validate_df(module, df_pd)
        df_pl = pl.from_pandas(df_pd)
        # normalizaciones simples
        df_pl = df_pl.rename({c: c.strip().lower().replace(" ", "_") for c in df_pl.columns})
        df_pl.write_parquet(os.path.join(pq_dir, f"{module}.parquet"))
        written_modules.append(module)

    # 2) duckdb materializado
    db_path = os.path.join(stg, "duckdb.db")
    con = duckdb.connect(db_path)
    con.execute("SET threads TO 4;")
    # cargar cada parquet como tabla base
    for module in written_modules:
        con.execute(f"CREATE OR REPLACE VIEW v_{module} AS SELECT * FROM read_parquet('parquet/{module}.parquet');")
    # ejemplos de MVs mínimas si existen módulos
    if "indicadores" in written_modules:
        con.execute("""
            CREATE OR REPLACE TABLE mv_indicadores AS
            SELECT COALESCE(anio, 0) AS anio, COALESCE(eje,'') AS eje,
                   SUM(COALESCE(valor,0)) AS total,
                   AVG(COALESCE(cumplimiento,0)) AS cumplimiento
            FROM v_indicadores GROUP BY 1,2 ORDER BY 1,2;
        """)
    if "comercializacion" in written_modules:
        con.execute("""
            CREATE OR REPLACE TABLE mv_comercializacion AS
            SELECT COALESCE(anio,0) anio, COALESCE(estrategia,'') estrategia,
                   SUM(COALESCE(monto,0)) total, COUNT(*) operaciones
            FROM v_comercializacion GROUP BY 1,2 ORDER BY 1,2;
        """)
    con.close()

    # 3) meta.json
    meta = {"version": ts, "created_at": ts, "modules": written_modules}
    with open(os.path.join(stg, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return stg

def _atomic_swap(stg_dir: str):
    cur = paths.CURRENT
    arc = os.path.join(paths.ARCHIVE, os.path.basename(stg_dir))
    # mueve current a archive (si existe) y staging→current
    if os.path.exists(cur):
        shutil.move(cur, arc)
    shutil.move(stg_dir, cur)

def run_refresh_from_files(files_dict: Dict[str, bytes]) -> dict:
    stg = _write_staging(files_dict)
    _atomic_swap(stg)
    return {"status": "ok", "version": os.path.basename(stg)}


def _slugify(name: str) -> str:
    # normaliza: minúsculas, sin acentos, espacios/puntuación→_
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    return s

def _normalize_df_ruea(df_pd: pd.DataFrame) -> pd.DataFrame:
    df_pd = df_pd.copy()

    # 1) normaliza encabezados
    df_pd.columns = [_slugify(c) for c in df_pd.columns]

    # 2) alias suaves de nombres frecuentes
    aliases = {
        "linea_prod": "linea_productiva",
        "linea_productiva_": "linea_productiva",
        "telefono_contacto": "telefono",
        "tel": "telefono",
        "e_mail": "email",
        "correo": "email",
        "fecha_de_registro": "fecha_registro",
        "sexo_genero": "sexo",
        "estrato_socioeconomico": "estrato",
    }
    df_pd.rename(columns={k: v for k, v in aliases.items() if k in df_pd.columns}, inplace=True)

    # 3) columnas que siempre deben ser TEXTO
    text_cols = [
        "documento", "telefono", "celular", "email", "nit",
        "corregimiento", "vereda", "linea_productiva"
    ]
    for c in text_cols:
        if c in df_pd.columns:
            df_pd[c] = df_pd[c].astype(str).str.strip()

    # 4) fechas (best-effort)
    for c in df_pd.columns:
        if c.startswith("fecha"):
            df_pd[c] = pd.to_datetime(df_pd[c], errors="coerce")

    return df_pd

def _rename_soft(df_pl: pl.DataFrame, module: str) -> pl.DataFrame:
    # equivalencias suaves (por si cambian etiquetas)
    aliases = {}
    if module == "ruea":
        aliases = {
            "linea_prod": "linea_productiva",
            "linea_productiva_": "linea_productiva",
            "telefono_contacto": "telefono",
            "tel": "telefono",
            "e_mail": "email",
            "correo": "email",
            "fecha_de_registro": "fecha_registro",
            "sexo_genero": "sexo",
            "estrato_socioeconomico": "estrato",
        }
    new_cols = {}
    for c in df_pl.columns:
        sc = _slugify(c)
        new_cols[c] = aliases.get(sc, sc)
    return df_pl.rename(new_cols)

def run_refresh_from_workbook(
    file_bytes: bytes,
    sheet_map: dict,
    header_rows: dict | None = None,
    modules_to_process: list[str] | None = None
) -> dict:
    """
    Lee un Excel maestro (bytes), extrae hojas según sheet_map y publica parquet+duckdb.
    - Por ahora enfocada en 'ruea' (GENERAL).
    """
    modules_to_process = modules_to_process or ["ruea"]
    header_rows = header_rows or {"ruea": 1}

    ts = _ts()
    stg = os.path.join(paths.STAGING, ts)
    pq_dir = os.path.join(stg, "parquet")
    os.makedirs(pq_dir, exist_ok=True)

    xl = pd.ExcelFile(io.BytesIO(file_bytes))  # openpyxl por defecto

    written_modules = []
    # --- RUEA (GENERAL) ---
    if "ruea" in modules_to_process:
        sheet_ruea = sheet_map.get("ruea", "GENERAL")
        hdr = int(header_rows.get("ruea", 1)) - 1
        try:
            df_pd = pd.read_excel(xl, sheet_name=sheet_ruea, header=hdr)
        except Exception as e:
            raise ValueError(f"No pude leer la hoja '{sheet_ruea}' para RUEA: {e}")

        # Normalización en pandas (igual que ya tenías)
        df_pd = _normalize_df_ruea(df_pd)

        # --- VALIDACIÓN ---
        df_valid, errors_df = validate_df("ruea", df_pd)  # <= nuevo

        # Si hay errores, generamos reporte Excel en staging
        quality_path = os.path.join(stg, "quality_report_ruea.xlsx")
        if errors_df is not None and not errors_df.empty:
            with pd.ExcelWriter(quality_path, engine="openpyxl") as xw:
                # Hoja de errores
                errors_df.to_excel(xw, sheet_name="errores", index=False)
                # Muestra de datos
                df_valid.head(1000).to_excel(xw, sheet_name="muestra_datos", index=False)
        else:
            # Creamos un reporte mínimo para constancia
            with pd.ExcelWriter(quality_path, engine="openpyxl") as xw:
                pd.DataFrame([{"estado": "sin_errores_detectados"}]).to_excel(xw, sheet_name="resumen", index=False)

        # Escribir Parquet con DuckDB desde df_valid (no polars)
        pq_path = os.path.join(pq_dir, "ruea.parquet")
        con_tmp = duckdb.connect()
        con_tmp.register("df_ruea", df_valid)
        con_tmp.execute(f"COPY (SELECT * FROM df_ruea) TO '{pq_path}' (FORMAT PARQUET);")
        con_tmp.close()

        written_modules.append("ruea")



    # --- construir duckdb con lo disponible ---
    db_path = os.path.join(stg, "duckdb.db")
    con = duckdb.connect(db_path)
    con.execute("SET threads TO 4;")
    if "ruea" in written_modules:
        # usa la ruta ABSOLUTA del parquet y copia los datos a una tabla interna
        pq_path_abs = os.path.join(stg, "parquet", "ruea.parquet").replace("\\", "/")
        con.execute("CREATE OR REPLACE TABLE base_ruea AS SELECT * FROM read_parquet(?);", [pq_path_abs])
        con.execute("CREATE OR REPLACE VIEW v_ruea AS SELECT * FROM base_ruea;")

        # ejemplo de vista materializada ligera (conteos por corregimiento)
        con.execute("""
            CREATE OR REPLACE TABLE mv_ruea_corregimiento AS
            SELECT COALESCE(corregimiento,'') AS corregimiento, COUNT(*) AS total
            FROM v_ruea GROUP BY 1 ORDER BY 2 DESC;
        """)
    con.close()

    # meta.json
    meta = {"version": ts, "created_at": ts, "modules": written_modules}
    with open(os.path.join(stg, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    _atomic_swap(stg)
    return {"status": "ok", "version": ts, "modules": written_modules,
        "reports": {"ruea_quality": os.path.join(paths.CURRENT, "quality_report_ruea.xlsx")}}

