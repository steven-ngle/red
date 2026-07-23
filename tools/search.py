from tavily import TavilyClient
import config
from ui import error

_client = None


def _tavily():
    global _client
    if _client is None:
        _client = TavilyClient(api_key=config.TAVILY_API_KEY)
    return _client


def web_search(query):
    try:
        raw = _tavily().search(
            query=query,
            search_depth="advanced",
            include_answer=True, # tavily gibt selber noch ne kurzantwort mit
            max_results=config.TAVILY_MAX_RESULTS,
        )
    except Exception as e:
        # tavily wirft je nach fehler unterschiedliche exceptions
        # TODO vlt retry einbauen
        error(f"Tavily-Suche fehlgeschlagen ({type(e).__name__}): {e}")
        return {"answer": "", "results": []}

    return {
        "answer": raw.get("answer") or "",
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": (r.get("content") or "")[:1500], # nicht den ganzen prompt zumüllen
            }
            for r in raw.get("results", [])
        ],
    }
