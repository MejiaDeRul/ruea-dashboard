# API (FastAPI + DuckDB)

Servicio backend **read-only** para publicar datos provenientes de un **Excel maestro** ("macro madre"). Expone endpoints públicos para consulta/descarga y un endpoint de **administración** para refrescar la publicación.

---

## ⚙️ Requisitos

* **Python 3.11+** (recomendado)
* Windows / macOS / Linux
* (Opcional) `curl` o PowerShell para pruebas de endpoints

---

## 📦 Instalación y arranque local

```bash
cd api
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

uvicorn app.main:app --reload
```

Salud de la API:

```
GET http://localhost:8000/health  → {"status":"ok"}
```

---

## 🔒 Variables de entorno (`api/.env`)

```ini
APP_NAME=Dani Alcaldia API
LOG_LEVEL=info

# Token del endpoint de administración (/api/v1/admin/refresh-xlsx)
ADMIN_TOKEN=CAMBIA_ESTE_TOKEN

# Dominios permitidos para CORS (separados por coma)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Carpeta base de datos publicada y staging
DATA_DIR=./data
```

> El proyecto usa `DATA_DIR/current` (versión publicada) y `DATA_DIR/staging` (versión en construcción). El **swap** a producción es atómico: staging → current.

---

## 🗂️ Estructura (carpeta `api/`)

```
api/
├─ pyproject.toml            # Dependencias y metadatos del paquete Python
├─ .env.example              # Ejemplo de variables de entorno
├─ data/
│  ├─ current/               # Publicado: *.duckdb, parquet, reportes de calidad
│  └─ staging/               # En construcción: parquet temporales, meta.json
└─ src/app/
   ├─ main.py                # App FastAPI, CORS, routers
   ├─ routers/
   │  ├─ public.py           # Endpoints públicos (ruea, facetas, summary, downloads)
   │  └─ admin.py            # Endpoint admin para refresh desde Excel
   ├─ services/
   │  ├─ etl.py              # ETL desde Excel → parquet → DuckDB (swap)
   │  ├─ validators.py       # Esquemas Pandera + reporter (no detiene publicación)
   │  └─ textnorm.py         # Normalizaciones (acentos, prefijos, regex SQL)
   ├─ core/
   │  ├─ config.py           # Carga de .env, settings
   │  ├─ paths.py            # Paths canónicos (current/staging)
   │  └─ security.py         # Auth simple Bearer para /admin
   ├─ db/duck.py             # Conexiones DuckDB (lectura/escritura)
   └─ utils/
      ├─ http.py             # ETag, cache-control, streaming
      └─ io.py               # Lectura/escritura CSV/XLSX
```

---

## 🧪 Flujo ETL (alto nivel)

```
Excel (.xlsx) → pandas (normalize) → Pandera (validación + reporte) → parquet staging
             → DuckDB (tablas base_*, vistas v_*, materializadas mv_*) → meta.json
             → SWAP staging → current (publicación atómica)
```

* **Validación**: errores de tipado o celdas atípicas se registran en un **reporte de calidad** (`quality_report_*.xlsx`) pero no abortan el refresh.
* **Normalización**: minúsculas, sin acentos, espacios compactados; limpieza de prefijos tipo `NN-` y encabezados verbales en `corregimiento`/`vereda`.

---

## 🔌 Endpoints

### 1) Salud y meta

* `GET /health` → `{ "status": "ok" }`
* `GET /api/v1/meta` → versión publicada, módulos activos, reportes disponibles.

### 2) Administración (refresco desde Excel)

* `POST /api/v1/admin/refresh-xlsx` (**protegido** por Bearer `ADMIN_TOKEN`)

  * Form-data:

    * `file`: archivo Excel (mime: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)
    * `sheet_map`: JSON con el mapeo módulo→hoja. Ej.: `{ "ruea": "GENERAL" }`
    * `header_rows`: JSON con filas de encabezado. Ej.: `{ "ruea": 1 }`

**PowerShell (Windows, 1 línea):**

```powershell
& curl.exe -X POST "http://localhost:8000/api/v1/admin/refresh-xlsx" -H "Authorization: Bearer <TU_TOKEN>" -F "file=@D:/ruta/MACRO MADRE SDR.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" --form-string "sheet_map={\"ruea\":\"GENERAL\"}" --form-string "header_rows={\"ruea\":1}"
```

**Bash (macOS/Linux):**

```bash
curl -X POST "http://localhost:8000/api/v1/admin/refresh-xlsx" \
  -H "Authorization: Bearer <TU_TOKEN>" \
  -F "file=@/ruta/MACRO_MADRE_SDR.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  --form-string 'sheet_map={"ruea":"GENERAL"}' \
  --form-string 'header_rows={"ruea":1}'
```

**Respuesta (ejemplo):**

```json
{
  "status": "ok",
  "version": "2025-11-24T21-00-38Z",
  "modules": ["ruea"]
}
```

### 3) Consulta RUEA

* `GET /api/v1/ruea`

  * **Filtros** (cadenas, opcionales): `corregimiento`, `vereda`, `linea_productiva`, `escolaridad`, `sexo`
  * **Paginación**: `limit` (por defecto 50), `offset` (por defecto 0)
  * **Selección de columnas**: `campos` (ej. `campos=documento,corregimiento,vereda`)
  * **Ordenamiento**: `order_by` (ej. `documento`), `order_dir` (`asc`|`desc`)

**Ejemplo:**

```
GET /api/v1/ruea?corregimiento=san%20cristobal&vereda=la%20loma&limit=25&order_by=documento&order_dir=asc
```

**Respuesta (forma):**

```json
{
  "total": 1234,
  "limit": 25,
  "offset": 0,
  "items": [ { "documento": "...", "corregimiento": "..." }, ... ]
}
```

### 4) Facetas (listas para filtros)

* `GET /api/v1/ruea/facetas`

  * Devuelve arrays con valores **normalizados**.
  * Es **tolerante** a columnas faltantes: si una no existe, retorna `[]`.

```json
{
  "corregimiento": ["san cristobal", ...],
  "vereda": ["la loma", ...],
  "linea_productiva": ["agrícola", ...],
  "escolaridad": ["secundaria", ...],
  "sexo": ["femenino", ...]
}
```

### 5) Resumen

* `GET /api/v1/ruea/summary`

  * Estadísticos generales + Top-5 por corregimiento y vereda (respetando filtros).

### 6) Descargas

* `GET /api/v1/ruea/download.csv`
* `GET /api/v1/ruea/download.xlsx`

Admiten **los mismos filtros** que `/ruea`.

---

## 🧯 Errores comunes y soluciones

1. **`ImportError: pyarrow is required ...`**
   Instala `pyarrow` (necesario cuando pandas → polars):

   ```bash
   pip install pyarrow
   ```

2. **`ArrowInvalid: Could not convert '3505873465-3122312184' with type str: tried to convert to int64`**
   Alguna columna numérica viene con guiones o caracteres. El ETL la convierte a **texto** para no romper. Revisa `_normalize_df_ruea()` si quieres coerción más estricta.

3. **`IO Error: No files found that match 'parquet/ruea.parquet'`**
   Aún no has publicado (no existe staging/current). Ejecuta **refresh**.

4. **`Invalid Input Error: No open result set`** al pedir columnas
   Evita `SELECT * ... LIMIT 0` para descubrir columnas. Usa:

   ```sql
   PRAGMA table_info('v_ruea');
   -- o desde DuckDB-Python: con.table("v_ruea").columns
   ```

5. **CORS** en local

   * Opción A (recomendada): **proxy de Vite** (`/api` → `http://localhost:8000`).
   * Opción B: añadir `CORSMiddleware` en `main.py` y configurar `CORS_ORIGINS`.

---

## 🔐 Seguridad

* Endpoint de administración protegido con **Bearer** (token en `ADMIN_TOKEN`).
* Endpoints públicos **read-only**.
* Ajusta `CORS_ORIGINS` para despliegue.

---

## 🧰 Desarrollo (opcional)

* Lint/format: **ruff** / **black** (añadir en `pyproject.toml` si se desea).
* Tests: **pytest** (pendiente incluir casos de contrato para cada endpoint).
* CI: workflows de GitHub Actions para `lint + test` (opcional).

---

## 📝 Notas para Windows (PowerShell)

* Usa `curl.exe` explícito (evita confusión con `Invoke-WebRequest`).
* En `--form-string` escapa comillas con `\"` como en los ejemplos.
* Rutas con `@D:/...` (usa `/` o escapa `\`).

---
