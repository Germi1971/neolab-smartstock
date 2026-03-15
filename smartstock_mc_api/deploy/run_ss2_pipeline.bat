@echo off
REM Pipeline SS2 completo: MC -> Policy -> Scoring
REM Asegurar que la API corre en http://127.0.0.1:8000 (o cambiar puerto abajo)
set API_URL=http://127.0.0.1:8000

echo [%date% %time%] Iniciando pipeline SS2...
echo.

echo 1. Demand Engine (Monte Carlo)...
curl -s -X POST %API_URL%/mc/run -H "Content-Type: application/json" -d "{}"
echo.

echo 2. Policy Engine...
curl -s -X POST %API_URL%/policy/run -H "Content-Type: application/json" -d "{}"
echo.

echo 3. Purchase Scoring...
curl -s -X POST %API_URL%/scoring/run -H "Content-Type: application/json" -d "{}"
echo.

echo [%date% %time%] Pipeline SS2 finalizado.
pause
