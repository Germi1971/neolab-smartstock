# Revisión de tu setup actual – Espejado de servidores

Basado en tus archivos `.env` locales.

---

## 1. MC API – smartstock_mc_api/.env

### ✅ Correcto
- `MYSQL_HOST=190.228.29.65` – neobd remoto
- `MYSQL_DB=neobd`
- `MC_REVIEW_DAYS=120` – cobertura 6 meses

### ⚠️ Corregir

| Variable | Valor actual | Acción |
|----------|--------------|--------|
| `AWS_MYSQL_HOST` | `tu-ip-aws-lightsail` | **Reemplazar por la IP pública de tu instancia Lightsail** (donde corre MySQL con ss2_staging). Ej: `3.xxx.xxx.xxx` |

Sin esto, el sync a AWS no funciona cuando ejecutás `run_full_pipeline.py` desde tu PC o desde neobd.

**Verificar:** que el puerto 3306 de MySQL en Lightsail esté abierto en el firewall (Networking en Lightsail) si el sync se ejecuta desde fuera de la instancia.

---

## 2. SCANNER_REPO/.env (Stock HUD)

### Configuración actual
- `MYSQL_HOST=190.228.29.65`
- `MYSQL_DB=neobd`
- `SMARTSTOCK_DB_NAME=ss2_staging` ← **override: el HUD lee de ss2_staging**
- `SMARTSTOCK_MC_API_URL=http://127.0.0.1:8001`

### ⚠️ Posible inconsistencia

El HUD intenta conectarse a **190.228.29.65** con base **ss2_staging**.

- Si `ss2_staging` existe en neobd (190.228.29.65) → está bien.
- Si `ss2_staging` solo existe en AWS → el HUD local no puede leer sugerencias. En ese caso:
  - Opción A: usar `MYSQL_DB=neobd` y quitar `SMARTSTOCK_DB_NAME` (si las vistas están en neobd).
  - Opción B: apuntar el HUD local a AWS para MySQL (MYSQL_HOST=IP_AWS) si querés leer ss2_staging remoto.

**Recomendación:** Confirmar dónde están las tablas/vistas `v_sugerencias_compra` y `ss2_v_purchase_suggestions_v2`. Si están en neobd, usar `neobd`. Si están en ss2_staging (AWS), el HUD en tu PC necesitaría conectarse a AWS.

---

## 3. Configuración por servidor (resumen)

### Servidor 1 – neobd (190.228.29.65)

| Componente | MYSQL_HOST | MYSQL_DB | Notas |
|------------|------------|----------|-------|
| MC API | `127.0.0.1` o `190.228.29.65` | `neobd` | Según dónde corre MySQL |
| Stock HUD | `127.0.0.1` o `190.228.29.65` | `neobd` o `ss2_staging` | Según dónde estén las vistas |
| SMARTSTOCK_MC_API_URL | - | - | `http://localhost:8001` |

### Servidor 2 – AWS Lightsail

| Componente | MYSQL_HOST | MYSQL_DB | Notas |
|------------|------------|----------|-------|
| MC API | `190.228.29.65` | `neobd` | Lee de neobd remoto |
| Stock HUD | `127.0.0.1` | `ss2_staging` | Lee ss2_staging local (tras sync) |
| SMARTSTOCK_MC_API_URL | - | - | `http://localhost:8001` |

**Sync:** neobd → ss2_staging (AWS). Debe ejecutarse tras el pipeline (run_full_pipeline lo hace si AWS_MYSQL_* está bien configurado).

---

## 4. Checklist de acciones

- [ ] Reemplazar `AWS_MYSQL_HOST=tu-ip-aws-lightsail` por la IP real de Lightsail
- [ ] Confirmar si `ss2_staging` existe en neobd o solo en AWS
- [ ] Si el HUD local usa ss2_staging y solo existe en AWS: abrir puerto 3306 en Lightsail y usar `MYSQL_HOST=IP_AWS` en SCANNER_REPO/.env (o usar neobd si las vistas están ahí)
- [ ] En AWS: verificar ruta `neolab-smartstock` (con guión) en crontab y systemd
- [ ] Ejecutar una vez el pipeline + sync para repoblar ss2_staging en AWS

---

## 5. Comando para probar sync

```bash
cd C:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock\smartstock_mc_api
python deploy/sync_neobd_to_aws.py
```

Si `AWS_MYSQL_HOST` está bien configurado y MySQL en AWS acepta conexiones, debería sincronizar las tablas SS2.
