#!/usr/bin/env bash
# One-click start for Mac / Linux. Opens on http://127.0.0.1:8000
set -e
cd "$(dirname "$0")/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo
echo "  Smart Order Management is starting: open http://127.0.0.1:8000"
echo "  Admin login:    admin@smartorders.local / admin123"
echo "  Customer login: customer@smartorders.local / customer123"
echo
python -m uvicorn main:app --host 127.0.0.1 --port 8000
