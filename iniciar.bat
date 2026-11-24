@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set PY=python) else (set PY=py)
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Abra http://127.0.0.1:8000 no navegador.
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
:fail
pause
