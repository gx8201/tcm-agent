# 中医智能问诊系统 - Railway 部署 Dockerfile
FROM python:3.12-slim

# 安装 uv
RUN pip install uv

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装依赖
RUN uv sync

# 暴露端口
EXPOSE 8080

# 启动应用
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
