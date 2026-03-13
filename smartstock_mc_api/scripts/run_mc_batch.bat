@echo off
echo Ejecutando Monte Carlo SmartStock...
curl -X POST http://127.0.0.1:8000/mc/run ^
  -H "Content-Type: application/json" ^
  -d "{\"n_sims\":8000,\"review_days\":30}"
echo.
echo Listo. Revisar Excel.
pause
