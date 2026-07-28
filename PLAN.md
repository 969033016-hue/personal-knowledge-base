# 阶段一与阶段二技术方案

## 阶段一目标

阶段一只升级底层知识模型和工具能力，不接入飞书，不增加前端页面。目标是把原先“所有内容混在一张知识表”的 V1 形态，升级为可持续演进的四层结构，并补齐导入、质检和关联能力。

## 阶段一范围

阶段一改动限定在当前本地目录内，围绕 Python MCP Server、SQLite 数据层、命令行演示脚本、Skill 说明和单测进行二次开发。保持项目依赖轻量，继续优先使用 Python 标准库。

## 阶段一四层知识结构

第一层是来源层，表名为 `knowledge_sources`，用于记录原始材料的标题、来源类型、来源地址、采集时间和元信息。它解决“这条知识从哪里来”的问题。

第二层是知识域层，表名为 `knowledge_domains`，用于承载业务知识、项目知识、测试方法、排障案例等分类。它解决“这条知识属于哪个领域”的问题，并为后续扩展父子分类预留字段。

第三层是知识卡片层，表名仍为 `knowledge_items`，但新增 `domain_id`、`knowledge_type`、`status` 等字段。它解决“可被检索和回答的最小知识单元是什么”的问题，同时保留原有 add/search/ask 使用方式，降低迁移成本。

第四层是证据与关系层，包含 `knowledge_evidence`、`knowledge_links` 和原有 `item_tags`。证据表承载来源片段、定位信息和置信度；关系表承载知识之间的引用、补充、冲突、重复等关系。它解决“这条知识为什么可信、和其他知识有什么关系”的问题。

## 阶段一新增工具

`ingest_source`：导入来源材料，创建来源记录，并可按段落切分生成知识卡片和证据。适合把文档摘要、排障记录、项目说明一次性沉淀进库。

`lint_knowledge`：扫描知识库质量问题，重点检查无来源、无证据、标题过短、正文过短、摘要缺失、置信度非法、孤立来源等问题，并输出统计和问题清单。

`link_knowledge`：在两条知识之间建立关系，支持 related、depends_on、duplicates、conflicts、supersedes、supplements 等关系类型，用于把碎片知识连成网络。

## 阶段二目标

阶段二在阶段一 `KnowledgeService` 基础上增加云端服务化能力，目标是让知识库既能继续作为 MCP Server 使用，也能作为普通 HTTP 服务被飞书机器人、自动化脚本或其他服务调用。

阶段二重点实现三件事：第一，用 FastAPI 把现有 MCP 工具包装为 REST API；第二，接入飞书机器人入口，完成事件回调、消息解析、知识库问答和消息回复；第三，服务端预留模型 API 调用能力，不依赖客户端工具生成增强答案。

## 阶段二范围

阶段二新增 `knowledge_mcp/api` 模块，集中放置 HTTP 应用、请求模型、配置加载、飞书机器人处理、飞书客户端和模型客户端。原有 MCP Server、SQLite 数据结构和核心服务方法保持兼容，不做大规模重构。

## 阶段二接口设计

REST API 以 `/api` 为前缀，提供 `GET /api/categories`、`POST /api/knowledge`、`PATCH /api/knowledge/{item_id}`、`GET /api/knowledge/{item_id}`、`POST /api/knowledge/search`、`POST /api/knowledge/ask`、`POST /api/sources/ingest`、`GET /api/lint`、`POST /api/links` 和 `POST /api/lark/events`。

其中新增、更新、导入来源和建立关系都属于写操作，必须显式传入 `confirm_write=true`。如果调用方没有确认，接口只返回 `need_confirm=true` 和操作名称，不会写入数据库。这样可以避免机器人或脚本误调用导致知识库被污染。

## 阶段二飞书机器人设计

飞书事件入口支持 URL verification 和消息事件。普通文本会被当成问题，默认调用知识库问答；`/ask` 用于显式问答；`/search` 只返回检索摘要；`/help` 返回帮助说明。聊天入口暂不开放写入命令，收到 `/add`、`/update`、`/ingest`、`/link` 时只返回风险提示。

飞书 AppID、Secret、Verification Token 和 Encrypt Key 都通过环境变量读取。未配置真实凭证时，代码不会调用飞书 OpenAPI，只返回本次拟回复内容，方便本地测试。

## 阶段二模型调用设计

模型调用封装在 `ModelClient` 中，按兼容 `/chat/completions` 的协议请求模型网关。只有 `MODEL_API_BASE`、`MODEL_API_KEY`、`MODEL_NAME` 都配置时才启用模型增强。未配置或调用失败时，问答接口会自动回退到本地规则答案，保证知识库基础能力稳定可用。

## 阶段二验证策略

单测覆盖 REST 主链路、写操作确认机制、搜索问答接口、飞书 URL verification、飞书消息解析和机器人命令分发。验证时执行 `python3 -m unittest discover -s tests -p "test_*.py"`，并检查代码和文档中不出现禁止关键字。
