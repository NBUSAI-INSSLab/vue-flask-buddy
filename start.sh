#!/usr/bin/env bash
# ============================================================
#  高校教师工作台（Vue + Flask）一键启动（macOS / Linux）
#  访问地址：http://127.0.0.1:5000
# ============================================================
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3，请先安装 Python 3.11 及以上版本。"
  exit 1
fi

if ! python3 -c "import flask, waitress, pypdf" >/dev/null 2>&1; then
  echo "[提示] 首次运行，正在安装依赖..."
  python3 -m pip install -r requirements.txt
fi

echo ""
echo "  高校教师工作台启动中：http://127.0.0.1:5000  （Ctrl+C 退出）"
echo ""
python3 run.py --port 5000
