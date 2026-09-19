import os
from pathlib import Path
from dotenv import load_dotenv

# Load root .env and local .env
root_env = Path("e:/.env")
if root_env.exists():
    load_dotenv(dotenv_path=root_env)

local_env = Path(__file__).resolve().parent.parent / ".env"
if local_env.exists():
    load_dotenv(dotenv_path=local_env)

class Config:
    # Base paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"

    # AI Model Arsenal
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-coder:32b")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-coder-v2:16b")
    FAST_CHAT_MODEL = os.getenv("FAST_CHAT_MODEL", "qwen3:latest")
    KIMI_CLUSTER_URL = os.getenv("KIMI_CLUSTER_URL", "http://10.25.32.13:8080")
    KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k3:cloud")
    HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes3:8b")

    # Hugging Face Token Cluster for Llama 3.3 70B & Sentiment
    HF_TOKENS = [
        os.getenv("HF_TOKEN_1", ""),
        os.getenv("HF_TOKEN_2", ""),
        os.getenv("HF_TOKEN_3", ""),
        os.getenv("HF_TOKEN_4", ""),
        os.getenv("HF_TOKEN_5", ""),
        os.getenv("HF_TOKEN_6", ""),
        os.getenv("HF_TOKEN_7", ""),
    ]
    HF_TOKENS = [t for t in HF_TOKENS if t.strip()]

    # Exchange & Trading Settings
    DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "binance")
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
    BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
    BYBIT_SECRET = os.getenv("BYBIT_SECRET", "")
    
    # Trading Mode: 'paper' or 'live'
    TRADING_MODE = os.getenv("TRADING_MODE", "paper")
    INITIAL_PAPER_BALANCE = float(os.getenv("INITIAL_PAPER_BALANCE", "10000.0"))

    # Risk Management Parameters
    MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "1.5"))  # 1.5% max account risk
    MAX_DAILY_DRAWDOWN_PCT = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "3.0"))  # 3% circuit breaker
    DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "1"))
    MAKER_FEE_PCT = float(os.getenv("MAKER_FEE_PCT", "0.00075")) # 0.075% standard fee
    TAKER_FEE_PCT = float(os.getenv("TAKER_FEE_PCT", "0.00075"))
    SLIPPAGE_PCT = float(os.getenv("SLIPPAGE_PCT", "0.0005"))

    # Consensus & Strategy Parameters
    AI_CONSENSUS_THRESHOLD = float(os.getenv("AI_CONSENSUS_THRESHOLD", "0.75")) # 75% quorum
    DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "15m")
    DEFAULT_SYMBOLS = [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
        "XAU/USD",  # Gold
        "EUR/USD",  # Forex
        "NVDA",     # Stock
    ]

    # Notifications
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    ALERT_PHONE = os.getenv("ALERT_PHONE", "")

    # Server / Dashboard
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8888"))

# Ensure directories exist
Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
