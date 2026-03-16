# Deploy de gráficos de situación SKU en AWS

Los gráficos (stock vs umbrales, demanda histórica, proyección) se despliegan junto con el resto del frontend y backend.

---

## Requisitos en AWS

1. **Vistas/tablas** para que el endpoint `/api/ml/sku/{sku}/chart_data` funcione:
   - `v_hist_ventas` (demanda histórica mensual) o `v_ml_eventos_50`
   - `ss2_v_purchase_suggestions_v2` o `v_sugerencias_compra` (stock, umbrales)
   - `ss2_demand_cache` (percentiles, P(stockout))
   - `v_sku_features_12m` (demanda prom fallback)

2. **Sync de datos** si usás `ss2_staging` en AWS:
   ```bash
   cd smartstock_mc_api
   python deploy/sync_neobd_to_aws.py
   ```

---

## Deploy rápido (desde tu PC)

```powershell
# 1. Commit y push de los cambios (backend + frontend)
cd C:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock
git add backend/api/ml.py frontend/src/components/SKUCharts.tsx frontend/src/components/ModalSKU.tsx frontend/src/services/apiClient.ts deploy/
git commit -m "Gráficos situación SKU: stock, demanda, proyección"
git push origin main

# 2. Deploy en AWS (pull + rebuild + restart)
deploy\deploy_aws_full.bat ubuntu@TU_IP
# O: set AWS_SSH=ubuntu@TU_IP
#    deploy\deploy_aws_full.bat
```

---

## Deploy manual (SSH en AWS)

```bash
ssh ubuntu@TU_IP

# Pull
cd /home/ubuntu/neolab-smartstock
git pull origin main

# Rebuild frontend
cd frontend
npm install
npm run build
cd ..

# Reiniciar backend (el que sirve /api en 8000)
sudo systemctl restart stock-hud
# O el servicio que corresponda: smartstock-backend, etc.

# Reiniciar MC API (8001) si aplica
sudo systemctl restart smartstock-mc-api
```

---

## Verificación

1. **Endpoint chart_data:**
   ```bash
   curl "http://localhost:8000/api/ml/sku/TU_SKU/chart_data"
   ```
   Debe devolver JSON con `demanda_historica`, `proyeccion_meses`, `stock_actual`, etc.

2. **Frontend:** Abrir la app, ir a Stock o Compras, hacer clic en una fila. El modal debe mostrar la sección "Situación del SKU" con los gráficos.

---

## Si no hay datos en los gráficos

- **Demanda histórica vacía:** Verificar que `v_hist_ventas` o `v_ml_eventos_50` exista y tenga datos para el SKU.
- **Stock/umbrales en 0:** Verificar `ss2_v_purchase_suggestions_v2` o `v_sugerencias_compra`.
- **Percentiles en 0:** Ejecutar el pipeline MC para poblar `ss2_demand_cache`:
  ```bash
  cd smartstock_mc_api
  python run_full_pipeline.py --skip-rebuild
  ```
