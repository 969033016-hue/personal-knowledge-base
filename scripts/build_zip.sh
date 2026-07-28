#!/usr/bin/env bash
set -euo pipefail

# 当前脚本用于生成函数计算可直接上传的完整 zip 包。
# 函数计算的公共 Python 镜像不会自动安装项目依赖，因此需要先把 requirements.txt
# 中声明的依赖安装到项目根目录下的 vendor/，再把 vendor/ 与项目代码一起打包。

# 通过脚本所在目录反推出项目根目录，避免用户从不同目录执行脚本时路径错乱。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDOR_DIR="${PROJECT_ROOT}/vendor"
OUTPUT_ZIP="${PROJECT_ROOT}/wiki-llm-app.zip"

cd "${PROJECT_ROOT}"

# 每次打包前清理旧依赖目录，避免历史残留依赖影响本次产物。
rm -rf "${VENDOR_DIR}"
mkdir -p "${VENDOR_DIR}"

# 将项目运行依赖安装到 vendor/ 目录。
# 函数计算启动时会通过 scripts/run_api.py 把该目录加入 sys.path，
# 从而可以正常导入 uvicorn、fastapi 等第三方包。
pip3 install -r requirements.txt -t "${VENDOR_DIR}"

# 清理旧 zip，确保最终上传的是本次新生成的产物。
rm -f "${OUTPUT_ZIP}"

# 打包项目代码与 vendor/ 依赖目录。
# 排除本地开发、缓存、数据库、环境变量和无关安装包，避免包体过大或泄露本地配置。
zip -r "${OUTPUT_ZIP}" . \
  -x ".git/*" \
  -x "*.pyc" \
  -x "*/__pycache__/*" \
  -x "*.db" \
  -x ".env" \
  -x "*.dmg" \
  -x "wiki-llm-app.zip"

echo "打包完成：${OUTPUT_ZIP}"
