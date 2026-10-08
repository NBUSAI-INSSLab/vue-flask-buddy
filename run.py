"""开发/生产统一启动入口。

    python run.py                 # 开发模式（默认 127.0.0.1:5000，热重载）
    python run.py --port 8000     # 指定端口
    python run.py --host 0.0.0.0  # 局域网可访问
    python run.py --prod          # 生产模式（waitress，多线程，无热重载）

环境变量：FWB_DATA_DIR 可把数据目录挪到别处（默认 ./data）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend import create_app  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="高校教师工作台（Vue + Flask）")
    p.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p.add_argument("--port", type=int, default=5000, help="监听端口（默认 5000）")
    p.add_argument("--prod", action="store_true", help="生产模式（waitress，无热重载）")
    p.add_argument("--debug", action="store_true", help="强制开启调试模式")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    dev = (not args.prod) and (args.debug or os.environ.get("FWB_DEBUG", "1") == "1")

    banner = f"""
  ┌────────────────────────────────────────────────┐
  │  高校教师工作台 · Vue 3 + Flask                │
  │  访问地址：http://{args.host}:{args.port:<5}              │
  │  运行模式：{'开发（热重载）' if dev else '生产（waitress）':<28}│
  └────────────────────────────────────────────────┘
"""
    print(banner)

    if args.prod:
        try:
            from waitress import serve
        except ImportError:
            print("未安装 waitress，回退到 Flask 内置服务器。安装：pip install waitress")
            app.run(host=args.host, port=args.port, debug=False, threaded=True)
            return
        serve(app, host=args.host, port=args.port, threads=8)
    else:
        app.run(host=args.host, port=args.port, debug=dev, use_reloader=dev)


if __name__ == "__main__":
    main()
