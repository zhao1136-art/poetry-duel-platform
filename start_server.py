"""AI 对诗平台启动脚本：优先从本地依赖目录加载依赖"""
import os
import sys
from pathlib import Path

LIBS = Path(os.environ.get("POETRY_DUEL_LIBS", "libs"))
if LIBS.is_dir():
    sys.path.insert(0, str(LIBS))
PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)
