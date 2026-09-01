#!/bin/bash
# GitHub 仓库初始化脚本

echo "=== 初始化 Git 仓库 ==="

# 进入项目目录
cd "E:/自用/RenShu-AI-study/my-tcm-agent"

# 初始化 Git
git init

# 添加所有文件
git add .

# 创建初始提交
git commit -m "feat: 初始化中医智能问诊系统

- 多智能体架构（LangGraph）
- 知识图谱（Neo4j + 1610味药材）
- 用户认证（JWT）
- 对话历史隔离
- 数据收集机制
- Railway 部署配置"

# 设置主分支
git branch -M main

echo "=== Git 仓库初始化完成 ==="
echo ""
echo "下一步："
echo "1. 在 GitHub 创建新仓库"
echo "2. 运行：git remote add origin https://github.com/your-username/tcm-agent.git"
echo "3. 运行：git push -u origin main"
echo ""
echo "然后："
echo "1. 访问 railway.app"
echo "2. 连接 GitHub 仓库"
echo "3. 添加 PostgreSQL 服务"
echo "4. 配置环境变量"
echo "5. 自动部署完成！"
