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

    格式：`id|名称|类型|厂商`，可选第 5 位标记是否支持 function calling：
    `deepseek-chat|DeepSeek-V3|text|deepseek|tools`
    """
    raw = os.getenv("AI_MODELS", "")
    models = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split("|")
        if len(parts) >= 4:
            # 阶段 20：第 5 位 = 是否支持工具调用（缺省 False，宁可降级不可报错）
            tools_flag = parts[4].strip().lower() if len(parts) >= 5 else ""
            models.append({
                "id": parts[0],
                "name": parts[1],
                "type": parts[2],
                "provider": parts[3],
                "tools": tools_flag in ("1", "true", "yes", "tools"),
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

# AI 任务配置（阶段 16：长任务异步化）
# 同时在跑的任务上限，超出的排队等待（避免无限并发压垮上游模型 API）
AI_TASK_CONCURRENCY = int(os.getenv("AI_TASK_CONCURRENCY", "3"))
# 图生图上游超时（秒）
AI_EDIT_TIMEOUT = float(os.getenv("AI_EDIT_TIMEOUT", "300"))

# AI 助手工具调用（阶段 20）
# 单次对话内最多允许的工具循环步数（防止模型反复调用同一工具而失控）
AGENT_MAX_TOOL_STEPS = int(os.getenv("AGENT_MAX_TOOL_STEPS", "5"))
# 工具检索类结果返回条数上限
AGENT_TOOL_RESULT_LIMIT = int(os.getenv("AGENT_TOOL_RESULT_LIMIT", "10"))

# 文件存储配置（阶段 17：测试环境隔离）
# 上传文件根目录。默认 src/uploads；测试/E2E 可用 UPLOAD_ROOT 覆盖，
# 避免测试产物写进真实 uploads（历史问题：pytest/E2E 只隔离了 DB 未隔离磁盘）
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT") or os.path.join(SRC_DIR, "uploads")
