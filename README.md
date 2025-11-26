# Dashboard RUEA

Plataforma informativa tipo **dashboard** (sin usuarios) para la Alcaldía.
Backend en **FastAPI + DuckDB**, frontend en **Vite (React + TS)**.
Las fuentes son archivos **Excel** (macro madre) y la publicación es **read-only** sobre una base generada.

---

## 📁 Estructura de carpetas

```
.
├─ api/                      # Backend FastAPI (paquete Python)
│  ├─ pyproject.toml
│  ├─ .env.example          # Variables de entorno (ejemplo, sin credenciales)
│  ├─ data/
│  │  ├─ current/           # Versión publicada (DB + reportes)  ← NO se versiona
│  │  └─ staging/           # Versión en preparación (ETL)       ← NO se versiona
│  └─ src/
│     └─ app/
│        ├─ main.py         # App FastAPI, middlewares, CORS, routers
│        ├─ routers/
│        │  ├─ public.py    # Endpoints públicos (ruea, descargas, facetas, summary)
│        │  └─ admin.py     # Endpoints de administración (refresh-xlsx)
│        ├─ services/
│        │  ├─ etl.py       # Proceso ETL: lee Excel madre, normaliza, valida, publica
│        │  ├─ validators.py# Esquemas Pandera (calidad de datos)
│        │  └─ textnorm.py  # Normalizaciones (corregimiento/vereda, acentos, prefijos)
│        ├─ core/
│        │  ├─ config.py    # Config/ENV (ADMIN_TOKEN, CORS, DATA_DIR, etc.)
│        │  ├─ paths.py     # Rutas canónicas (data/current, data/staging)
│        │  └─ security.py  # Helpers de seguridad (Bearer admin, etc.)
│        ├─ db/
│        │  └─ duck.py      # Conexiones DuckDB (lectura/escritura)
│        └─ utils/
│           ├─ http.py      # Utilidades HTTP (ETag, cache headers, streaming)
│           └─ io.py        # Utilidades de I/O (CSV/XLSX streaming, etc.)
│
├─ dashboard-ruea/           # Frontend (Vite + React + TypeScript)
│  ├─ index.html
│  ├─ vite.config.ts         # Proxy /api → http://localhost:8000 (dev)
│  ├─ .env.example
│  └─ src/
│     ├─ api.ts              # Cliente de API (fetch + utilidades)
│     ├─ App.tsx             # Página principal (filtros, resumen, tabla, descargas)
│     ├─ index.css           # Estilos base del dashboard
│     └─ components/
│        ├─ Filters.tsx      # Selectores: corregimiento, vereda, etc. (con fallback)
│        └─ Table.tsx        # Tabla paginada + ordenamiento por columna
│
├─ .gitignore                # Ignora entornos, artefactos y data publicada
├─ .gitattributes            # Normaliza finales de línea y marca binarios
└─ README.md                 # Este archivo
```

> ✅ `api/data/current/` y `api/data/staging/` se mantienen en el repo con un `.gitkeep`, pero **no** se suben datos reales (están en `.gitignore`).

---

## 🔌 API (resumen rápido)

* `GET /health` → `{"status":"ok"}`

* `GET /api/v1/meta` → versión publicada, módulos y reportes

* `POST /api/v1/admin/refresh-xlsx` (Bearer `ADMIN_TOKEN`)
  Sube el Excel madre y publica (atomic swap):

  * `file` (multipart, .xlsx)
  * `sheet_map` JSON, p.ej. `{"ruea":"GENERAL"}`
  * `header_rows` JSON, p.ej. `{"ruea":1}`

* `GET /api/v1/ruea`
  Filtros: `corregimiento`, `vereda`, `linea_productiva`, `escolaridad`, `sexo`
  Extras: `limit`, `offset`, `campos`, `order_by`, `order_dir`

* `GET /api/v1/ruea/facetas`
  Listas de valores limpias (tolerante a columnas faltantes)

* `GET /api/v1/ruea/summary`
  Total y Top-5 por corregimiento y vereda

* `GET /api/v1/ruea/download.csv|xlsx`
  Descargas con los mismos filtros de `/ruea`

**Normalizaciones clave (backend):**

* `corregimiento`: ignora prefijos numéricos `NN-` y “corregimiento (de) …”
* `vereda`: ignora `NN-`, “vereda(s) (de) …”, “área de expansión …”
* Comparaciones sin acentos, en minúsculas y con espacios compactados

---

## 🧪 Flujo ETL (alto nivel)

```
Excel madre → pandas (normalize) → Pandera (validación + reporte) → DuckDB
          └→ parquet staging → base_* y vistas v_* → mv_* → meta.json
          └→ SWAP staging → current  (publicación atómica)
```

* **staging** se puede borrar sin afectar la versión publicada en `current`.
* Se generan reportes de calidad (`quality_report_*.xlsx`) en la versión activa.

---

## ▶️ Ejecución local

### Backend

```bash
cd api
python -m venv .venv
.venv\\Scripts\\activate            # Windows
pip install -e .
copy .env.example .env            # edita ADMIN_TOKEN y CORS
uvicorn app.main:app --reload
```

**Refresh (PowerShell, 1 línea):**

```powershell
& curl.exe -X POST "http://localhost:8000/api/v1/admin/refresh-xlsx" -H "Authorization: Bearer <TU_TOKEN>" -F "file=@D:/ruta/MACRO MADRE SDR.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" --form-string "sheet_map={\"ruea\":\"GENERAL\"}" --form-string "header_rows={\"ruea\":1}"
```

### Frontend

```bash
cd dashboard-ruea
npm i
# En dev, usamos proxy de Vite:
#  - vite.config.ts ya envía /api → http://localhost:8000
#  - puedes dejar VITE_API_BASE_URL vacío
npm run dev
```

Abre `http://localhost:5173`.

---

## 🔒 Variables de entorno

**api/.env**

```
APP_NAME=Dani Alcaldia API
LOG_LEVEL=info
ADMIN_TOKEN=CAMBIA_ESTE_TOKEN
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DATA_DIR=./data
```

**dashboard-ruea/.env** (dev con proxy → puede ir vacío)

```
VITE_API_BASE_URL=
```

---

## 🧱 Convenciones de módulos (backend)

* `services/etl.py`

  * `_normalize_df_ruea()` limpia encabezados y valores (snake_case, coerción, fechas)
  * `run_refresh_from_workbook()` orquesta lectura, validación, parquet, vistas/tablas y swap
* `services/validators.py`

  * Esquemas **Pandera** con `coerce` + reporter de errores (no rompe el refresh)
* `services/textnorm.py`

  * Normalizadores reutilizables (Python y expresiones SQL equivalentes)
* `routers/public.py`

  * Endpoints públicos (filtros, summary, descargas) con **ordenamiento** y **facetas robustas**
* `db/duck.py`

  * Conexiones DuckDB modo lectura/escritura (`Duck.ro()`, `Duck.rw()`)

---

## 🧭 Ramas recomendadas

* `main` (estable), `dev` (integración)
* `feature/...` por tarea (PR → `dev`, y de `dev` → `main` para releases)
* Reglas de rama en GitHub: proteger `main`, requerir PR y squash merge

---
