# Personal Knowledge Base

一个可本地运行、也可部署为 HTTP 服务的个人知识库项目，采用 **Skill + MCP + REST API + 飞书机器人** 的组合思路：

- **知识服务层**：使用 Python 实现轻量级 MCP 服务和统一 `KnowledgeService`，负责知识写入、来源导入、质量检查、关系维护、检索与问答。
- **HTTP 接入层**：阶段二新增 FastAPI 服务，把 MCP 工具包装为可云端部署的 REST API。
- **飞书入口层**：阶段二新增飞书机器人事件回调，支持消息解析、知识库问答和飞书消息回复。
- **模型增强层**：阶段二新增服务端模型调用抽象，可接入 Claude、豆包或兼容 `/chat/completions` 的模型网关。
- **数据层**：使用 SQLite 保存长期知识，阶段一已升级为“来源、知识域、知识卡片、证据与关系”四层结构。

## 功能概览

- 自动分类：根据知识内容自动判断主分类
- 自动打标签：从输入内容抽取高频关键词与业务标签
- 新增知识：把零散经验沉淀成结构化知识卡片
- 来源导入：把原始材料导入为来源记录，并生成知识卡片与证据片段
- 质量检查：扫描无证据、摘要缺失、标题过短、正文过短、非法置信度等问题
- 知识关联：维护知识之间的补充、依赖、冲突、重复等关系
- 更新知识：按知识 ID 追加或覆盖内容
- 关键词检索：按标题、摘要、正文、标签进行匹配
- 问答回答：先检索，再按“结论 + 依据 + 延伸建议”组织答案
- 类别管理：读取内置分类清单，并同步到知识域表
- REST API：通过 HTTP 接口调用知识库能力
- 飞书机器人：接收飞书消息并回复知识库答案
- 模型增强：在服务端调用模型 API，不依赖客户端工具

## 阶段一数据结构

阶段一采用四层结构：

1. **来源层 `knowledge_sources`**：记录原始材料标题、来源类型、地址、采集时间和元信息。
2. **知识域层 `knowledge_domains`**：记录业务知识、项目知识、测试方法、排障案例等分类，并预留父子分类能力。
3. **知识卡片层 `knowledge_items`**：记录可被检索和问答使用的最小知识单元，保留原有知识写入体验。
4. **证据与关系层 `knowledge_evidence` / `knowledge_links` / `item_tags`**：记录证据片段、来源定位、知识关系和标签。

## 阶段二服务架构

阶段二不重写阶段一核心逻辑，而是在 `KnowledgeService` 外围增加三类入口：

1. **FastAPI REST API**：面向云端部署、自动化脚本和机器人调用。
2. **飞书机器人回调**：面向 IM 对话入口，默认只做读取和问答，写入操作不在聊天入口自动执行。
3. **模型 API 客户端**：服务端统一读取模型配置，配置缺失或调用失败时自动回退本地规则答案。

写操作统一带确认机制：新增知识、更新知识、来源导入、知识关联都必须显式传 `confirm_write=true`，否则接口只返回确认提示，不会写入 SQLite。

## 目录结构

```text
personal-knowledge-base/
├── .env.example
├── PLAN.md
├── data/
│   └── bootstrap_categories.json
├── knowledge_mcp/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── lark_bot.py
│   │   ├── lark_client.py
│   │   ├── model_client.py
│   │   └── models.py
│   ├── core/
│   │   ├── answerer.py
│   │   ├── classifier.py
│   │   ├── retriever.py
│   │   ├── schema.py
│   │   └── storage.py
│   ├── __init__.py
│   ├── service.py
│   └── server.py
├── scripts/
│   ├── demo_cli.py
│   ├── init_db.py
│   └── run_api.py
├── skill/
│   └── knowledge-companion/
│       ├── assets/
│       ├── references/
│       └── SKILL.md
└── tests/
    ├── test_api_flow.py
    ├── test_kb_flow.py
    └── test_lark_bot.py
```

## 快速开始

### 1. 安装依赖

```bash
cd personal-knowledge-base
python3 -m pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python3 scripts/init_db.py
```

### 3. 运行命令行演示

新增知识：

```bash
python3 scripts/demo_cli.py add --title "导量空结果排查" --content "当 crossZoneTaskList 为空时，优先检查互斥规则、频控和实验位。"
```

导入来源材料：

```bash
python3 scripts/demo_cli.py ingest-source --title "接口联调记录" --content "接口返回空列表时先看实验位和配置。\n\n发奖链路要校验金额精度和幂等。" --source-type note --uri local://debug-note
```

提问检索：

```bash
python3 scripts/demo_cli.py ask --question "导量任务空结果先看什么？"
```

### 4. 启动 MCP 服务

```bash
python3 -m knowledge_mcp.server
```

### 5. 启动 REST API 服务

```bash
python3 scripts/run_api.py
```

启动后可访问：

```bash
curl http://127.0.0.1:8000/health
```

新增知识示例：

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge \
  -H 'Content-Type: application/json' \
  -d '{"title":"接口空结果排查","content":"优先检查实验位、配置、频控和互斥规则。","confirm_write":true}'
```

如果不传 `confirm_write=true`，接口会返回确认提示，不会写库。

## 环境变量

复制 `.env.example` 后，在部署环境注入真实配置。仓库内只保留占位符，不保存真实密钥。

- `KNOWLEDGE_DB_PATH`：SQLite 数据库路径
- `KNOWLEDGE_CATEGORIES_PATH`：分类配置路径
- `LARK_APP_ID`：飞书应用 ID
- `LARK_APP_SECRET`：飞书应用密钥
- `LARK_VERIFICATION_TOKEN`：飞书事件校验 Token
- `LARK_ENCRYPT_KEY`：飞书事件加密 Key，当前预留
- `MODEL_API_BASE`：模型网关地址
- `MODEL_API_KEY`：模型 API Key
- `MODEL_NAME`：模型名称
- `MODEL_TIMEOUT_SECONDS`：模型调用超时时间

## REST API 列表

- `GET /health`
- `GET /api/categories`
- `POST /api/knowledge`
- `PATCH /api/knowledge/{item_id}`
- `GET /api/knowledge/{item_id}`
- `POST /api/knowledge/search`
- `POST /api/knowledge/ask`
- `POST /api/sources/ingest`
- `GET /api/lint`
- `POST /api/links`
- `POST /api/lark/events`

## 飞书机器人用法

飞书事件回调地址配置为：

```text
https://your-domain.example.com/api/lark/events
```

机器人支持：

- 直接发送问题：自动检索知识库并回答。
- `/ask 问题`：显式问答。
- `/search 关键词`：只返回检索摘要。
- `/help`：查看帮助。

为避免误写知识库，飞书入口暂不执行 `/add`、`/update`、`/ingest`、`/link` 等写入命令。

## 支持的 MCP 工具

知识服务默认暴露以下工具：

- `add_knowledge`
- `update_knowledge`
- `get_knowledge`
- `search_knowledge`
- `ask_knowledge`
- `list_categories`
- `ingest_source`
- `lint_knowledge`
- `link_knowledge`

## 设计取舍

阶段一优先保证本地可运行、保留 V1 工具、补来源证据和关系骨架。阶段二优先保证服务端可部署、写操作安全可控、飞书入口最小闭环、模型能力可插拔。模型和飞书均属于增强能力，配置缺失或调用失败时不影响本地知识库检索问答。

## 测试

```bash
cd personal-knowledge-base
python3 -m unittest discover -s tests -p "test_*.py"
```
