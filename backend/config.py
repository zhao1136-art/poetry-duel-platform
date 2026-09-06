"""配置管理：从 .env 读取云端/本地模型配置"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # 云端
    cloud_base_url: str = os.getenv("CLOUD_BASE_URL", "").strip().rstrip("/")
    cloud_api_key: str = os.getenv("CLOUD_API_KEY", "").strip()
    cloud_model: str = os.getenv("CLOUD_MODEL", "").strip()

    # 本地
    local_base_url: str = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1").strip().rstrip("/")
    local_model: str = os.getenv("LOCAL_MODEL", "qwen2.5:7b").strip()

    # 请求参数
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "60"))
    health_timeout: float = float(os.getenv("HEALTH_TIMEOUT", "3"))

    # 静态资源
    frontend_dir: Path = BASE_DIR / "frontend"
    data_dir: Path = BASE_DIR / "data"

    @property
    def cloud_available(self) -> bool:
        return bool(self.cloud_api_key and self.cloud_base_url and self.cloud_model)


config = Config()
