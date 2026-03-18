# with this
import os
import requests
from dotenv import load_dotenv
from models.schemas import SearchResult

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"
FETCH_TIMEOUT = 10
MAX_FETCH_CHARS = 5000


def web_search(query: str) -> list[dict]:
    """
    Calls Tavily search API. Returns list of SearchResult dicts.
    Falls back to empty list on failure — never crashes the loop.
    """
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not set in environment")

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": 5,
        "search_depth": "basic",
        "include_answer": False,
    }

    response = requests.post(TAVILY_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()

    results = []
    for r in data.get("results", []):
        results.append(SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", "")[:500],
            source=r.get("url", "")
        ).model_dump())

    return results


def url_fetch(url: str) -> str:
    """
    Fetches plain text content from a URL.
    Truncated to MAX_FETCH_CHARS before sanitization.
    """
    headers = {"User-Agent": "ResearchAgent/1.0"}
    response = requests.get(url, headers=headers,
                            timeout=FETCH_TIMEOUT)
    response.raise_for_status()

    # Strip HTML tags simply — no heavy dependency
    text = response.text
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:MAX_FETCH_CHARS]