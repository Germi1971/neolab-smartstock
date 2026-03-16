# Paso a paso: SmartStock con sugerencias de 6 meses

Para que el modal del HUD muestre "Policy Engine" y sugerencias de 6 meses en lugar de "parametros_sku".

---

## Paso 1: Verificar dónde corre el pipeline

El pipeline escribe en **neobd** (190.228.29.65). Puede correr en:

- **neobd** (servidor 190.228.29.65)
- **AWS** (MC API con MYSQL_HOST=190.228.29.65)
- **Tu PC** (si tenés acceso a neobd)

**Pregunta:** ¿Dónde tenés la MC API corriendo ahora? (neobd, AWS, o ambos)

---

## Paso 2: Ejecutar el pipeline (llenar neobd)

Desde el servidor donde corre la MC API (puerto 8001):

```bash
# 1. Classification (opcional si la tabla existe)
curl -X POST "http://localhost:8001/classification/run" -H "Content-Type: application/json" -d '{}'

# 2. Monte Carlo (6 meses = review_days 120)
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'

# 3. Policy Engine
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'

# 4. Scoring
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```

Esto escribe en **neobd** (ss2_demand_cache, ss2_policy_results, ss2_purchase_scores).

---

## Paso 3: Sync neobd → ss2_staging (en AWS)

En la instancia AWS (SSH):

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
source venv/bin/activate
python deploy/sync_neobd_to_aws.py
```

El `.env` en AWS debe tener:
- `MYSQL_HOST=190.228.29.65` (origen: neobd)
- `AWS_MYSQL_HOST=127.0.0.1` (destino: ss2_staging local)

---

## Paso 4: Verificar que el HUD lee de ss2_staging

Tu SCANNER_REPO/.env tiene:
- `SMARTSTOCK_DB_NAME=ss2_staging` ✓
- `MYSQL_HOST=190.228.29.65` → el HUD se conecta a neobd para MySQL

**Importante:** Si el HUD corre en **AWS**, debe leer ss2_staging que está en **127.0.0.1** (MySQL local en AWS). Entonces en AWS el .env del SCANNER_REPO debería tener:
- `MYSQL_HOST=127.0.0.1` (MySQL local en AWS)
- `SMARTSTOCK_DB_NAME=ss2_staging`

Si el HUD corre en **tu PC** y se conecta a neobd: ss2_staging está en neobd o en AWS. Si ss2_staging está solo en AWS, el HUD en tu PC no puede leerla (a menos que apuntes MYSQL_HOST a la IP de AWS y abras el puerto 3306).

**Resumen:** El HUD debe conectarse a la base donde está ss2_staging. Si el sync corre en AWS, ss2_staging está en AWS. Entonces el HUD en AWS usa MYSQL_HOST=127.0.0.1.

---

## Paso 5: Probar el modal

1. Abrir el Stock HUD
2. Buscar un SKU (ej. M524-100L)
3. Abrir el modal → pestaña SmartStock
4. Debería mostrar "Policy Engine" o "Monte Carlo" en lugar de "parametros_sku"
5. Si hay sugerencia de compra (qty_recomendada > 0), se verá el bloque naranja

---

## Checklist rápido

- [ ] MC API corriendo (localhost:8001)
- [ ] Pipeline ejecutado (mc, policy, scoring)
- [ ] Sync ejecutado en AWS
- [ ] HUD apunta a la base correcta (ss2_staging)
- [ ] Reiniciar Stock HUD si cambiaste .env
