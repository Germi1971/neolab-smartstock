# Arquitectura NeoLab SmartStock (Unificada)

**Última actualización:** Marzo 2026

---

## 1. Sistema único: neolab_smartstock

NeoLab SmartStock es el **sistema canónico** de predicción de reposición. Toda la funcionalidad está centralizada en este repositorio.

```
neolab_smartstock/
├── frontend/          # UI React (Vite) — ÚNICO FRONTEND
├── backend/           # API principal (FastAPI, puerto 8000)
├── smartstock_mc_api/ # Motor Monte Carlo (FastAPI, puerto 8010)
├── ss2/               # Scripts batch
└── database/          # Esquemas SQL
```

---

## 2. Flujo de datos

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                          │
│  Tabs: Stock | Compras | Parámetros | ML                                │
│  Botón: "Descargar reporte CSV" (header)                                │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                                 │ VITE_API_URL (default: :8000)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI, puerto 8000)                        │
│  /api/stock, /api/purchases/*, /api/parameters, /api/ml/*               │
│  /api/purchases/export → CSV descargable                                │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
┌──────────────────────────────┐  ┌──────────────────────────────────────┐
│  MySQL (neobd)               │  │  MC API (puerto 8010)                │
│  v_sugerencias_compra        │  │  POST /mc/run, GET /mc/cache/{sku}    │
│  parametros_sku              │  │  Escribe sku_mc_cache                 │
│  v_analisis_sku_excel_mc     │  │  /dashboard/sugerencias (alternativo) │
└──────────────────────────────┘  └──────────────────────────────────────┘
```

---

## 3. Componentes

| Componente | Puerto | Descripción |
|------------|--------|-------------|
| **Frontend** | 3000 (dev) | React + Vite. Consume backend en 8000. |
| **Backend** | 8000 | API principal. Stock, compras, parámetros, ML, export CSV. |
| **MC API** | 8010 | Motor Monte Carlo. Simula demanda, escribe cache. |
| **MySQL** | 3306 | Base de datos. Vistas: v_sugerencias_compra, v_analisis_sku_excel_mc. |

---

## 4. Endpoints clave

### Backend (8000)
- `GET /api/purchases/suggestions` — Lista sugerencias
- `GET /api/purchases/export` — CSV descargable (reporte completo)
- `GET /api/ml/sku/{sku}` — Detalle SKU para modal
- `POST /api/purchases/approve/{sku}` — Aprobar sugerencia

### MC API (8010)
- `POST /mc/run` — Regenerar cache Monte Carlo
- `GET /mc/cache/{sku}` — Cache por SKU
- `GET /dashboard/sugerencias/export` — Export alternativo (si frontend apunta aquí)

---

## 5. Configuración frontend

```env
# .env o variables de entorno
VITE_API_URL=http://localhost:8000   # Backend principal
```

En producción, apuntar a la URL del backend (ej. `http://tu-servidor:8000`).

---

## 6. Despliegue

### Orden de arranque
1. MySQL (base de datos)
2. Backend (8000)
3. MC API (8010) — opcional si solo usas reglas/ML del backend
4. Frontend — build estático en `frontend/dist/` servido por nginx

### Build frontend
```bash
cd frontend
npm install
npm run build
# dist/ → servir con nginx o similar
```

---

## 7. Nota sobre BOLT

BOLT SmartStock (Next.js) fue una UI alternativa. **A partir de ahora, el frontend canónico es neolab_smartstock/frontend.** La MC API expone `/dashboard/*` por compatibilidad; el frontend principal usa el backend en 8000.
