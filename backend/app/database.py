"""
数据库配置模块

使用 SQLAlchemy 连接 PostgreSQL
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库连接配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tcm_user:***@localhost:5433/tcm_agent"
)

# Supabase 需要 SSL 连接
connect_args = {}
if "supabase.com" in DATABASE_URL:
    connect_args["sslmode"] = "require"

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args if connect_args else None
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    from app.models.user import User  # noqa
    from app.models.conversation import Conversation, Message  # noqa
    Base.metadata.create_all(bind=engine)
