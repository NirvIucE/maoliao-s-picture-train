"""
负责从 .env 读取所有配置，集中管理
"""

import os

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST","localhost")
DB_PORT= int(os.getenv("DB_PORT","3306"))
DB_USER = os.getenv("DB_USER","root")
DB_PASSWORD = os.getenv("DB_PASSWORD","")
DB_NAME = os.getenv("DB_NAME","cat_pic")

# 拼接数据库连接 URL (SQLAlchemy 格式)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# JWT 配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# REDIS 配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# AI 模型配置
PROVIDER_CONFIG = {
    "deepseek": {
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    },
    "siliconflow": {
        "api_key": os.getenv("SILICONFLOW_API_KEY", ""),
        "base_url": os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
    },
}

# AI模型注册表
def _parse_models() -> list[dict]:
    """
    解析 AI_MODELS 环境变量为模型列表
    """
    raw = os.getenv("AI_MODELS", "")
    models = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split("|")
        if len(parts) >= 4:
            models.append({
                "id": parts[0],
                "name": parts[1],
                "type": parts[2],
                "provider": parts[3],
            })
    return models

MODEL_REGISTRY = _parse_models()

# AI 搜索配置
AI_SEARCH_BATCH_SIZE = int(os.getenv("AI_SEARCH_BATCH_SIZE", "50"))
AI_SEARCH_VISION_TOP_N = int(os.getenv("AI_SEARCH_VISION_TOP_N", "5"))

# AI 应用配置（阶段 14：上下文管理 / 成本参数化）
# 多轮对话上下文上限（估算 token，超出滑动窗口裁剪）
CHAT_MAX_CONTEXT_TOKENS = int(os.getenv("CHAT_MAX_CONTEXT_TOKENS", "4096"))
LLM_DEFAULT_TEMPERATURE = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0.7"))
LLM_DEFAULT_MAX_TOKENS = int(os.getenv("LLM_DEFAULT_MAX_TOKENS", "1024"))
