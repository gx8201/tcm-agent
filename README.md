# 🏥 中医智能问诊系统

基于多智能体与知识图谱的中医辅助诊断系统，为用户提供专业的中医辨证分析和调理建议。

## ✨ 核心功能

- 💬 **智能问诊** - 多轮对话，自动追问，精准辨证
- 👅 **舌苔分析** - 上传舌苔图片，AI舌诊分析
- 📚 **知识图谱** - 1610味药材、266个方剂、540种症状
- 📋 **对话历史** - 用户隔离，隐私保护
- 🏥 **医案积累** - 自动提取，相似医案推荐

## 🛠️ 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | FastAPI + LangGraph + DeepSeek |
| 前端 | React + TypeScript |
| 数据库 | PostgreSQL + Neo4j + Qdrant |
| AI模型 | DeepSeek API / Ollama 本地部署 |
| 部署 | Docker + Railway.app |

## 🚀 快速开始

### 方式一：本地部署

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/tcm-agent.git
cd tcm-agent

# 2. 启动数据库
docker compose up -d

# 3. 安装依赖
cd backend
uv sync

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 5. 启动服务
uv run uvicorn main:app --reload

# 6. 访问 http://localhost:8001
```

### 方式二：Railway 一键部署

1. Fork 本仓库
2. 访问 [Railway.app](https://railway.app)
3. 连接 GitHub 仓库
4. 添加 PostgreSQL 服务
5. 配置环境变量
6. 自动部署完成！

## 📊 数据统计

| 数据类型 | 数量 |
|---|---|
| 药材数据 | 1610 味 |
| 方剂数据 | 266 个 |
| 症状数据 | 540 种 |
| 知识图谱关系 | 3000+ 条 |

## 🔒 隐私保护

- ✅ 用户对话数据完全隔离
- ✅ 问诊数据脱敏后用于模型优化
- ✅ 不收集个人身份信息
- ✅ 符合《个人信息保护法》要求

## 📖 使用指南

### 智能问诊
1. 登录/注册账号
2. 描述您的症状（如：失眠多梦、胃痛、咳嗽）
3. 系统自动追问，收集更多信息
4. 获取中医辨证分析和调理建议

### 舌苔分析
1. 切换到"舌苔分析"功能
2. 上传舌苔图片（自然光下拍摄）
3. 获取AI舌诊分析结果

### 医案参考
1. 问诊完成后，系统自动提取医案
2. 在"医案库"中查看相似案例
3. 参考历史诊疗经验

## 🤝 贡献指南

欢迎贡献代码、数据或反馈！

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### 数据贡献
- 中医古籍数据
- 药材方剂数据
- 医案案例数据
- 翻译校对

## 📝 开源协议

本项目采用 [MIT 协议](LICENSE) 开源。

## ⚠️ 免责声明

**本系统仅供参考学习，不能替代专业医疗诊断。**

- 中医讲究"望闻问切"四诊合参，AI无法完全替代医师诊断
- 如有严重症状，请及时就医
- 方剂推荐仅供参考，需在医师指导下使用
- 本系统不承担任何医疗责任

## 📞 联系我们

- GitHub Issues: 提交问题和建议
- 微信公众号: [待添加]
- 小红书: [待添加]

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - 多智能体框架
- [DeepSeek](https://deepseek.com) - AI模型支持
- [Neo4j](https://neo4j.com) - 知识图谱数据库
- 所有贡献者和用户

---

**如果这个项目对您有帮助，请给我们一个 ⭐ Star！**
