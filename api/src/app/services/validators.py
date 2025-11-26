import pandas as pd
import pandera as pa
from pandera import Column, Check

# --- esquema (igual que antes) ---
ruea_schema = pa.DataFrameSchema(
    {
        "documento": Column(object, nullable=False),
        "nombres": Column(object, nullable=True),
        "apellidos": Column(object, nullable=True),
        "sexo": Column(object, nullable=True, checks=Check.isin(["F","M","X","O","OTRO","NO REPORTA",""])),
        "edad": Column(pa.Int64, nullable=True, checks=Check.in_range(0, 120)),
        "estrato": Column(pa.Int64, nullable=True, checks=Check.isin([0,1,2,3,4,5,6])),
        "escolaridad": Column(object, nullable=True),
        "corregimiento": Column(object, nullable=True),
        "vereda": Column(object, nullable=True),
        "linea_productiva": Column(object, nullable=True),
        "fecha_registro": Column(object, nullable=True),
        "telefono": Column(object, nullable=True),
        "email": Column(object, nullable=True),
    },
    coerce=True,
    strict=False,
    name="ruea",
)

def _coerce_best_effort(df: pd.DataFrame) -> pd.DataFrame:
    """Coerciona tipos básicos sin fallar si hay valores mixtos."""
    d = df.copy()
    for col in ("edad", "estrato"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").astype("Int64")
    # fechas ya vienen parseadas en el ETL; si no, forzamos aquí también:
    for c in d.columns:
        if str(c).startswith("fecha"):
            d[c] = pd.to_datetime(d[c], errors="coerce")
    # todo lo “textual” queda como object/str
    text_cols = ["documento","telefono","email","corregimiento","vereda","linea_productiva","nombres","apellidos","escolaridad","sexo"]
    for c in text_cols:
        if c in d.columns:
            d[c] = d[c].astype(str).str.strip()
    return d

def validate_ruea(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Valida RUEA: devuelve (df_coercionado, errores|None).
    No usamos .to_schema(); primero coercion best-effort y luego validación.
    """
    df_coerced = _coerce_best_effort(df)
    try:
        df_valid = ruea_schema.validate(df_coerced, lazy=True)  # devuelve df si pasa
        return df_valid, None
    except pa.errors.SchemaErrors as e:
        fc = e.failure_cases.copy()
        fc["schema"] = "ruea"
        cols = [c for c in ["schema","column","check","failure_case","index"] if c in fc.columns] + \
               [c for c in fc.columns if c not in {"schema","column","check","failure_case","index"}]
        fc = fc[cols]
        # devolvemos el df coercionado (aunque tenga errores) + el detalle de errores
        return df_coerced, fc

def validate_df(module: str, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    if module == "ruea":
        return validate_ruea(df)
    return df, None
