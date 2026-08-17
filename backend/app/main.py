"""FastAPI 入口。

开发模式：
  后端  uvicorn app.main:app --port 8000 --reload  （在 backend/ 目录）
  前端  npm run dev  （Vite 5173，代理 /api 到 8000）
一体化模式：先 npm run build，后端自动托管 frontend/dist，只跑 8000 一个端口。
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config as C
from .db import Database
from . import routes

app = FastAPI(title="AI 世界模拟器")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

routes.db = Database(C.DB_PATH)
app.include_router(routes.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# 托管前端构建产物（存在才挂载）
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
