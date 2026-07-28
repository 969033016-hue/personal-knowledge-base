from __future__ import annotations

import sys
from pathlib import Path


# 当前脚本位于 scripts/run_api.py。
# 直接执行 `python3 scripts/run_api.py` 时，Python 默认只会把 scripts 目录加入 sys.path，
# 不会自动把项目根目录加入 sys.path，导致无法导入同级目录下的 knowledge_mcp 包。
#
# 函数计算的公共 Python 镜像也不会自动安装 requirements.txt 中的依赖。
# 打包脚本会把依赖安装到项目根目录下的 vendor/ 目录，因此启动前需要同时把：
# 1. 项目根目录：用于导入 knowledge_mcp 等项目源码；
# 2. vendor 目录：用于导入 uvicorn、fastapi 等第三方依赖；
# 加入 sys.path。
#
# 注意：必须先调整 sys.path，再 import uvicorn。
# 否则函数计算环境会在导入 uvicorn 时直接报 ModuleNotFoundError。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"

for path in (VENDOR_DIR, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        # 插入 sys.path 头部：优先使用随 zip 包一起上传的项目源码和依赖，
        # 避免误命中运行环境中其他同名包或旧版本依赖。
        sys.path.insert(0, path_str)

import uvicorn


if __name__ == "__main__":
    # 本地启动脚本保持尽量薄，真实配置统一由 knowledge_mcp.api.config 从环境变量读取。
    uvicorn.run("knowledge_mcp.api.app:app", host="0.0.0.0", port=8001, reload=False)
