import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 飞书配置
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")

# Claude API 配置（可选，如果需要 AI 理解指令）
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

# 路径配置（相对于脚本所在目录）
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "5cun-print"

IMAGE_INPUT_DIR = str(DATA_DIR / "input_images")
WORD_OUTPUT_DIR = str(DATA_DIR / "output")
WORD_SCRIPT_PATH = str(SCRIPT_DIR / "5cun-docx-cli.py")

# 保持向后兼容
BASE_DIR = str(DATA_DIR)

# Python 解释器
PYTHON_PATH = os.getenv("PYTHON_PATH", "python3")

# 打印机配置
PRINTER_NAME = os.getenv("PRINTER_NAME", None)  # 不指定则使用默认打印机

# 超时配置
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "120"))
