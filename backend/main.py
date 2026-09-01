"""
中医多智能体诊断系统 - FastAPI 入口
精简版：去除 Redis、JWT、GraphRAG 等依赖，保留核心 LangGraph 架构
"""

import os
import time
from dotenv import load_dotenv

# 加载环境变量（必须在其他导入之前）
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.controller.chat_controller import router as chat_router
from app.controller.auth_controller import router as auth_router
from app.controller.data_controller import router as data_router
from app.database import init_db

# 创建 FastAPI 应用
app = FastAPI(
    title="中医多智能体诊断系统",
    description="基于 LangGraph 的中医问诊诊断系统",
    version="2.0.0",
)

# CORS 配置（生产环境应设置 CORS_ORIGINS 环境变量为逗号分隔的域名白名单）
_cors_origins_str = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()] if _cors_origins_str else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(data_router)

# 静态文件目录
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    try:
        init_db()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"⚠️ 数据库初始化失败: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页 - 返回用户界面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return {"service": "my-tcm-agent", "version": "2.0.0", "status": "healthy"}


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
