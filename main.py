"""项目根目录启动入口：``python main.py serve``（全部子命令见 ``python main.py --help``）。"""

from app.main import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)