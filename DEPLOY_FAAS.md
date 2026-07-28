# 火山引擎函数计算部署方案

## 1. 部署目标

本项目是 FastAPI + SQLite 的个人知识库服务。函数计算实例本身是无状态环境，本地文件可能因冷启动、实例回收或扩缩容丢失，因此不能把 `data/knowledge.db` 作为生产持久化数据源。

本次方案保留 SQLite 表结构和查询逻辑，把 SQLite 数据库文件托管到火山引擎 TOS。服务启动和每次访问数据库前会从 TOS 拉取数据库文件到 `/tmp/knowledge.db`，写事务提交后立即把本地数据库文件回传到 TOS。

该方案适合个人知识库、机器人问答、低并发后台管理等轻量场景。若后续出现高并发写入或强事务要求，建议迁移到 RDS、veDB 或其他托管数据库。

## 2. 架构说明

请求进入函数计算 HTTP 服务后，由 `knowledge_mcp.api.app` 创建 FastAPI 应用。配置层读取环境变量，当 `KNOWLEDGE_STORAGE_BACKEND=tos` 时创建 TOS 同步适配器。业务层仍通过 `KnowledgeService` 调用 `KnowledgeStorage`，核心 SQL 和数据模型不变。存储层在连接 SQLite 前执行 TOS 拉取，在写入提交后执行 TOS 回传。

整体链路为：函数计算 HTTP 入口接收请求，FastAPI 路由解析请求，知识库服务执行新增、检索、问答、导入来源等操作，SQLite 本地临时文件完成事务处理，TOS 保存最终数据库文件。

## 3. TOS 准备

需要提前创建一个 TOS Bucket，并准备一个对象 Key 用于保存 SQLite 文件，例如 `knowledge/knowledge.db`。首次部署时该对象可以不存在，服务会在首次初始化数据库后自动上传。

建议为函数计算绑定最小权限的访问凭证，只授予目标 Bucket 下数据库对象的读取和写入权限。AccessKey、SecretKey、临时 Token 等敏感信息必须通过函数计算环境变量或密钥管理能力注入，不要写入仓库。

## 4. 环境变量

本地开发默认使用 SQLite 文件模式：

```bash
KNOWLEDGE_STORAGE_BACKEND=sqlite
KNOWLEDGE_DB_PATH=data/knowledge.db
```

函数计算部署建议使用 TOS 模式：

```bash
KNOWLEDGE_STORAGE_BACKEND=tos
KNOWLEDGE_DB_PATH=/tmp/knowledge.db
TOS_ENDPOINT=https://tos-cn-beijing.volces.com
TOS_REGION=cn-beijing
TOS_BUCKET=your_tos_bucket
TOS_OBJECT_KEY=knowledge/knowledge.db
TOS_ACCESS_KEY_ID=your_tos_access_key_id
TOS_SECRET_ACCESS_KEY=your_tos_secret_access_key
TOS_SECURITY_TOKEN=
```

如需接入飞书机器人或模型增强回答，继续通过环境变量注入对应占位配置：

```bash
LARK_APP_ID=your_lark_app_id
LARK_APP_SECRET=your_lark_app_secret
LARK_VERIFICATION_TOKEN=your_lark_verification_token
LARK_ENCRYPT_KEY=your_lark_encrypt_key
MODEL_API_BASE=https://example.com/v1
MODEL_API_KEY=your_model_api_key
MODEL_NAME=your_model_name
MODEL_TIMEOUT_SECONDS=20
```

## 5. 镜像部署方式

仓库已提供 `Dockerfile`，用于构建函数计算自定义镜像。镜像启动命令会运行：

```bash
uvicorn knowledge_mcp.api.app:app --host 0.0.0.0 --port 8000
```

本地构建命令示例：

```bash
docker build -t knowledge-service-faas:latest .
```

本地运行验证命令示例：

```bash
docker run --rm -p 8000:8000 \
  -e KNOWLEDGE_STORAGE_BACKEND=tos \
  -e KNOWLEDGE_DB_PATH=/tmp/knowledge.db \
  -e TOS_ENDPOINT=https://tos-cn-beijing.volces.com \
  -e TOS_REGION=cn-beijing \
  -e TOS_BUCKET=your_tos_bucket \
  -e TOS_OBJECT_KEY=knowledge/knowledge.db \
  -e TOS_ACCESS_KEY_ID=your_tos_access_key_id \
  -e TOS_SECRET_ACCESS_KEY=your_tos_secret_access_key \
  knowledge-service-faas:latest
```

验证健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回中应包含 `storage_backend=tos` 和 `tos_enabled=true`。

## 6. 函数计算配置建议

函数类型选择 HTTP 服务或自定义镜像 HTTP 入口，容器监听端口配置为 `8000`。超时时间建议先设置为 30 秒以上，内存建议不低于 512 MB。若模型回答链路较慢，可按实际情况提高超时时间。

环境变量中必须配置 TOS 相关参数。`KNOWLEDGE_DB_PATH` 建议固定为 `/tmp/knowledge.db`，不要指向项目目录下的 `data/knowledge.db`，避免误以为函数实例本地文件可持久保存。

## 7. 接口验证流程

部署后先访问 `/health`，确认服务可用、TOS 模式已开启。然后调用新增知识接口时必须传 `confirm_write=true`，这是服务端写操作安全阀。新增成功后再调用检索和问答接口，确认数据能写入并从 TOS 恢复。

可重点验证：首次 TOS 对象不存在时服务能自动初始化；新增知识后 TOS 对象更新时间变化；重启函数实例后历史知识仍可查询；未传 `confirm_write=true` 时写接口不会落库。

## 8. 风险与后续演进

当前方案本质上是“SQLite 单文件 + TOS 对象存储”的轻量持久化方案。优点是改造小、成本低、部署简单；主要风险是对象存储不提供数据库级行锁和事务隔离，高并发写入时可能出现覆盖写。

如果服务从个人低频使用升级为多人高频写入，应优先演进为托管数据库，并保留当前 `DatabaseSyncAdapter` 边界作为迁移点。
