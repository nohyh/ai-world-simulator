@echo off
chcp 65001 >nul
cd /d %~dp0

REM 开发模式：后端 8000（热重载）+ 前端 Vite 5173（热更新，/api 代理到 8000）
if not exist backend\.venv (
  python -m venv backend\.venv
  backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt
)
start "backend" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload"
start "frontend" cmd /k "cd frontend && npm run dev"
timeout /t 3 >nul
start "" http://localhost:5173
