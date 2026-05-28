# Personal Knowledge Base

一个可本地运行的知识库项目，采用 **Skill + MCP** 的组合思路：

- **知识服务层**：使用 Python 标准库实现一个轻量级 MCP 服务，负责知识写入、更新、检索与问答。
- **交互编排层**：提供一个可复用的技能目录，用来约束输入格式、提问方式和回答风格。
- **数据层**：使用 SQLite 保存长期知识条目，并维护标签与分类信息。

## 功能概览

- 自动分类：根据知识内容自动判断主分类
- 自动打标签：从输入内容抽取高频关键词与业务标签
- 新增知识：把零散经验沉淀成结构化知识卡片
- 更新知识：按知识 ID 追加或覆盖内容
- 关键词检索：按标题、摘要、正文、标签进行匹配
- 问答回答：先检索，再按“结论 + 依据 + 延伸建议”组织答案
- 类别管理：读取内置分类清单

## 目录结构

```text
personal-knowledge-base/
├── data/
│   └── bootstrap_categories.json
├── knowledge_mcp/
│   ├── core/
│   │   ├── answerer.py
│   │   ├── classifier.py
│   │   ├── retriever.py
│   │   ├── schema.py
│   │   └── storage.py
│   ├── __init__.py
│   └── server.py
├── scripts/
│   ├── demo_cli.py
│   └── init_db.py
├── skill/
│   └── knowledge-companion/
│       ├── assets/
│       ├── references/
│       └── SKILL.md
└── tests/
    └── test_kb_flow.py
```

## 快速开始

### 1. 初始化数据库

```bash
cd personal-knowledge-base
python3 scripts/init_db.py
```

### 2. 运行命令行演示

```bash
cd personal-knowledge-base
python3 scripts/demo_cli.py add --title "导量空结果排查" --content "当 crossZoneTaskList 为空时，优先检查互斥规则、频控和实验位。"
python3 scripts/demo_cli.py ask --question "导量任务空结果先看什么？"
```

### 3. 启动知识服务

```bash
cd personal-knowledge-base
python3 -m knowledge_mcp.server
```

## 支持的工具

知识服务默认暴露以下工具：

- `add_knowledge`
- `update_knowledge`
- `get_knowledge`
- `search_knowledge`
- `ask_knowledge`
- `list_categories`

## 设计取舍

V1 版本优先保证：

1. 本地可运行
2. 结构清晰，便于后续替换检索策略
3. 不依赖第三方库，方便快速验证

后续可升级方向：

- 语义检索
- 相似知识去重
- 多版本知识条目
- Web 管理界面
- 知识导入导出

## 测试

```bash
cd personal-knowledge-base
python3 -m unittest discover -s tests -p "test_*.py"
```
