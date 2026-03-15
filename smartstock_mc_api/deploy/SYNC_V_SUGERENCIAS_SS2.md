# Sincronizar v_sugerencias_compra en ss2_staging

Para que el export CSV de Stock HUD devuelva datos cuando usa `SMARTSTOCK_DB_NAME=ss2_staging`, la vista `v_sugerencias_compra` debe existir y tener datos.

## Clonar datos desde neobd

**neobd** (190.228.29.65:3306) y **ss2_staging** (127.0.0.1:3307 en Lightsail) están en servidores distintos. Usa el script remoto:

```bash
cd smartstock_mc_api/deploy
chmod +x sync_neobd_to_ss2_remote.sh

# Con variables de entorno (recomendado)
export NEOBD_HOST=190.228.29.65 NEOBD_USER=neolab NEOBD_PASS='tu_pass_neobd'
export SS2_HOST=127.0.0.1 SS2_PORT=3307 SS2_USER=ss2 SS2_PASS='tu_pass_ss2'
./sync_neobd_to_ss2_remote.sh

# O editar el script con las contraseñas (menos seguro)
```

Sincroniza: `parametros_sku`, `tablaprecios`, `sku_mc_cache`. Si `sku_mc_cache` no existe en neobd, se omite.

**Importante:** Para que el CSV coincida con el HUD, también sincroniza `tabla1` (stock/inventario). Sin ella, `v_stock_estado_unidades` usa datos viejos o vacíos y el CSV mostrará stock distinto al modal.

**Mismo servidor:** si ambas DBs estuvieran en el mismo MySQL, usa `sync_neobd_to_ss2_staging.sql`.

## Requisitos previos en ss2_staging

Deben existir estas tablas/vistas:

| Objeto | Tipo |
|--------|------|
| `parametros_sku` | tabla |
| `tablaprecios` | tabla |
| `sku_mc_cache` | tabla |
| `v_stock_estado_unidades` | vista |
| `v_sku_features_12m` | vista |

Si falta `sku_mc_cache`:
```bash
mysql -h TU_HOST -u TU_USER -p ss2_staging < app/sql/ddl_sku_mc_cache.sql
```

## Crear la vista

```bash
cd smartstock_mc_api
mysql -h TU_MYSQL_HOST -u TU_USER -p ss2_staging < deploy/ddl_v_sugerencias_compra_ss2_staging.sql
```

**Si falla** (ej. "v_stock_estado_unidades doesn't exist"): esas vistas deben crearse antes. Revisa `setup_vistas.sql` o scripts equivalentes en tu repo.

## Verificar

```sql
USE ss2_staging;
SELECT COUNT(*) FROM v_sugerencias_compra;
```

## Después de crear la vista

1. Reinicia Stock HUD: `sudo systemctl restart stock-hud`
2. Prueba el export CSV desde la barra del Stock HUD
