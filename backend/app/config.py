"""全局配置与常量。"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "worlds.db"

# ---- 默认模型配置（DeepSeek，OpenAI 兼容协议） ----
DEFAULT_PROVIDER = "deepseek"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_AUX_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 0.85
DEFAULT_AUX_TEMPERATURE = 0.3

# ---- 游戏节奏 ----
RECENT_RAW_TURNS = 6          # 进入 prompt 的近期原始回合数（更早的靠记忆结晶）
CRYSTAL_INTERVAL = 4          # 每 N 个回合结晶一次 short 层
CASCADE_BATCH = 4             # N 个 short 合 1 medium，依此类推
FEELING_DECAY_TURNS = 5       # NPC 表面情绪 N 回合后淡出
WORLD_TICK_MIN_MINUTES = 60   # 叙事时间跳跃超过该值才触发世界推进
PLOT_PRESSURE_TURNS = 10      # 主线 N 回合无进展时注入压力提示
MAX_NPC_UPDATE = 5            # 单回合最多更新的在场 NPC 数

# ---- 记忆检索预算（字符数，近似 token 的两倍中文占比） ----
MEMORY_BUDGET_CHARS = 2400
PER_LAYER_TOP_K = 3

META_SENTINEL = "[[META]]"
META_END = "[[END]]"
