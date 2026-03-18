import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ADMIN_WEBHOOK  = os.getenv("ADMIN_WEBHOOK", "")

AUTHORIZATION_TIMEOUT = int(os.getenv("AUTH_TIMEOUT_SECONDS", "600"))
MAX_SHORT_TERM        = int(os.getenv("MAX_SHORT_TERM_EXCHANGES", "20"))
TOP_K_MEMORY          = int(os.getenv("TOP_K_MEMORY", "3"))

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY is not set in .env")
if not TAVILY_API_KEY:
    raise EnvironmentError("TAVILY_API_KEY is not set in .env")