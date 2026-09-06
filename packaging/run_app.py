"""对诗平台打包入口：启动服务并自动打开浏览器"""
import logging
import socket
import sys
import threading
import webbrowser
from pathlib import Path

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


def log_file():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "poetry-duel.log"
    return Path(__file__).resolve().parent.parent / "poetry-duel.log"


def setup_logging():
    try:
        handlers = [logging.FileHandler(log_file(), encoding="utf-8")]
        if sys.stderr is not None:
            handlers.append(logging.StreamHandler())
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=handlers,
        )
    except Exception:
        # 日志不可写时降级为控制台输出，绝不阻塞服务启动
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser():
    webbrowser.open(URL)


def main():
    setup_logging()
    logging.info("对诗平台启动，Python frozen=%s", getattr(sys, "frozen", False))
    if port_in_use(PORT):
        logging.info("端口 %s 已被占用，直接打开浏览器", PORT)
        open_browser()
        return

    import uvicorn

    from backend.main import app

    threading.Timer(1.5, open_browser).start()
    logging.info("服务监听 %s", URL)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_config=None)


if __name__ == "__main__":
    main()
