import re, unicodedata

def _unaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _norm_base(value: str) -> str:
    s = _unaccent(str(value or "")).lower().strip()
    # quita prefijo numérico con guion: "80-" o "80 - "
    s = re.sub(r"^\s*\d+\s*-\s*", "", s)
    # compacta espacios
    s = re.sub(r"\s+", " ", s)
    return s

def norm_corregimiento_py(value: str) -> str:
    s = _norm_base(value)
    # quita prefijo "corregimiento de "
    s = re.sub(r"^\s*corregimiento(\s+de)?\s+", "", s)
    return s

def norm_vereda_py(value: str) -> str:
    s = _norm_base(value)
    # quita prefijos frecuentes en las bases
    s = re.sub(r"^\s*veredas?(\s+de)?\s+", "", s)                 # "vereda ", "veredas de "
    s = re.sub(r"^\s*area\s+de\s+expansion\s+", "", s)            # "area de expansion "
    s = re.sub(r"^\s*sector(es)?\s+", "", s)                      # "sector ", opcional
    s = re.sub(r"^\s*zona(s)?\s+", "", s)                         # "zona ", opcional
    return s
