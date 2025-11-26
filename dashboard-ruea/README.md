# Frontend (Vite + React + TypeScript)

Interfaz pública **informativa** (sin autenticación) para explorar el módulo **RUEA**: filtros, resumen y tabla con descargas. Construida con **Vite + React + TS**.

---

## ⚙️ Requisitos

* Node.js 18+ (recomendado 20+)
* npm 9+ o pnpm/yarn (ejemplos con npm)

---

## ▶️ Arranque en desarrollo

```bash
cd dashboard-ruea
npm i
npm run dev
```

Abre: `http://localhost:5173`

> En DEV, usamos **proxy** a la API para evitar CORS. No necesitas definir `VITE_API_BASE_URL`.

---

## 🗂️ Estructura (carpeta `dashboard-ruea/`)

```
dashboard-ruea/
├─ index.html
├─ vite.config.ts          # Proxy /api → http://localhost:8000 (DEV)
├─ .env.example            # Variables de entorno para PROD (opcional en DEV)
└─ src/
   ├─ api.ts               # Cliente API (fetch + utilidades + fallbacks)
   ├─ App.tsx              # Página principal (filtros, resumen, tabla, descargas)
   ├─ index.css            # Estilos base del dashboard (variables + utilidades)
   └─ components/
      ├─ Filters.tsx       # Selectores: corregimiento, vereda, etc.
      └─ Table.tsx         # Tabla paginada + ordenamiento por columna
```

---

## 🌐 Configuración de red

### DEV — Proxy (recomendado)

`vite.config.ts` debe incluir algo como:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

El cliente usa `baseURL = import.meta.env.VITE_API_BASE_URL || '/api'`.

### PROD — API externa

Define `VITE_API_BASE_URL` con la URL pública del backend y habilita CORS en la API.

`.env.example` (copiar a `.env` en despliegue):

```ini
# Si sirves front y API en dominios distintos, apunta aquí
VITE_API_BASE_URL=https://api.midominio.com
```

---

## 🔌 Endpoints consumidos

* `GET /api/v1/ruea` — datos paginados/ordenados (tabla)
* `GET /api/v1/ruea/facetas` — listas para filtros (normalizadas)
* `GET /api/v1/ruea/summary` — totales y Top-5 (resumen)
* `GET /api/v1/ruea/download.csv|xlsx` — descargas con filtros

Parámetros de filtros (query string): `corregimiento`, `vereda`, `linea_productiva`, `escolaridad`, `sexo`.

---

## 🧠 Flujo de datos en la UI

1. Carga **facetas** al iniciar.
2. Si **facetas** viene vacío o falla, el cliente usa **fallback**: toma una muestra de `/ruea?limit=1000` y construye las listas locales (función `getFacetasWithFallback()` en `api.ts`).
3. Al cambiar filtros/orden, se consulta `/ruea` y se actualiza la tabla.
4. Descargas (`CSV/XLSX`) usan los mismos filtros activos.

---

## 🎨 Estilos y componentes

* **`index.css`** expone variables y utilidades tipo *tailwind-lite* (`border`, `rounded`, `px-2`, `grid`, `md:grid-cols-3`, etc.).
* **Tarjetas**: usa `.card` con `.metric` para KPIs.
* **Botones**: `.btn` y `.btn.primary`.
* **Tabla**: contenedor `.table-wrap` para scroll; `thead` sticky.
* **Modo oscuro**: respeta `prefers-color-scheme`.

> Ajusta colores institucionales en `:root { --primary: #006c67; ... }`.

---

## 🧪 Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 5173"
  }
}
```

* `npm run dev` → servidor Vite con HMR
* `npm run build` → genera `dist/`
* `npm run preview` → sirve `dist/` para pruebas locales

---

## 🚀 Despliegue

### Opción A — Servidor estático (Nginx)

1. Construye:

   ```bash
   npm run build
   ```
2. Copia `dist/` al servidor web.
3. Si backend está en otra URL, define `VITE_API_BASE_URL` en build o usa variables de entorno en el reverse proxy.

**Ejemplo Nginx (SPA + API externa):**

```nginx
server {
  listen 80;
  server_name dashboard.midominio.com;

  root /var/www/dashboard/dist;
  index index.html;

  location / {
    try_files $uri /index.html; # SPA fallback
  }

  # (Opcional si sirves API por el mismo dominio)
  location /api/ {
    proxy_pass https://api.midominio.com/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

### Opción B — GitHub Pages / S3 + CloudFront

* Publica `dist/` como sitio estático.
* Asegura el **fallback** a `index.html` (SPA).
* API debe permitir CORS y usarse vía `VITE_API_BASE_URL`.

---

## 🧯 Solución de problemas

* **CORS en consola**: en DEV usa el proxy; en PROD configura `CORS_ORIGINS` en la API.
* **404 al refrescar URL**: configura servidor estático con `try_files $uri /index.html`.
* **`fetch` bloqueado**: revisa `VITE_API_BASE_URL` y que la API esté accesible.
* **Filtros vacíos**: confirma `/ruea/facetas`; si viene vacío, `getFacetasWithFallback()` debe poblar desde `/ruea`.

---

## ♿ Accesibilidad y UX

* Labels en selects y textos alternativos en iconos.
* Estados de carga/errores (`.state-loading`, `.state-error`).
* Navegación por teclado en tabla y filtros.

---

## 🧹 Calidad (opcional)

* Linter/Format: `eslint` + `prettier` (añadir config si se adopta).
* Pruebas: `vitest` + `@testing-library/react` (no incluidas por defecto).

---

## 🔖 Convenciones

* Nombres en `kebab-case` para archivos, `PascalCase` para componentes.
* Commits tipo Conventional: `feat:`, `fix:`, `chore:`, `docs:`, etc.

---

## 📎 Notas

* El front **no** guarda estado servidor; toda lógica de filtrado/ordenamiento se resuelve en la API.
* Si en el futuro se agregan módulos además de RUEA, duplicar el patrón de `api.ts` y componentes.
