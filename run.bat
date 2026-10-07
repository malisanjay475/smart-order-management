@echo off
REM One-click start for Windows. Opens on http://127.0.0.1:8000
cd /d "%~dp0backend"
if not exist venv (
  python -m venv venv
)
call venv\Scripts\activate
pip install -q -r requirements.txt
echo.
echo   Smart Order Management is starting: open http://127.0.0.1:8000
echo   Admin login:    admin@smartorders.local / admin123
echo   Customer login: customer@smartorders.local / customer123
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
