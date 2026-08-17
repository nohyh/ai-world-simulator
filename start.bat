@echo off
chcp 65001 >nul
cd /d %~dp0

REM 一键启动：后端 8000 端口托管已构建的前端（frontend/dist）
if not exist backend\.venv (
  echo [初始化] 创建 Python 虚拟环境...
  python -m venv backend\.venv || goto :err
  backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || goto :err
)
if not exist frontend\dist (
  echo [初始化] 构建前端...
  cd frontend && call npm install --no-fund --no-audit && call npm run build && cd ..
)

echo 启动中... 浏览器打开 http://localhost:8000
start "" http://localhost:8000
cd backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000
goto :eof

:err
echo 初始化失败，请检查 Python / Node 是否已安装。
pause
