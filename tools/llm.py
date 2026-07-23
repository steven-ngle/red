import time
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError
import config
from ui import warn

_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)
    return _client


def _chat(model, messages, *, thinking, json_mode=False, max_retries=3):
    kwargs = {"model": model, "messages": messages}
    if thinking:
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(1, max_retries + 1):
        try:
            resp = client().chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            reasoning = getattr(msg, "reasoning_content", None) or ""
            return msg.content or "", reasoning, _reasoning_tokens(resp)
        except AuthenticationError:
            raise RuntimeError(
                "Authentifizierung fehlgeschlagen, DEEPSEEK_API_KEY in .env prüfen."
            ) from None
        except (RateLimitError, APIConnectionError) as e:
            if attempt == max_retries:
                raise RuntimeError(f"DeepSeek nach {max_retries} Versuchen nicht erreichbar: {e}") from e
            wait = 2 ** attempt
            warn(f"DeepSeek {type(e).__name__}, Retry {attempt}/{max_retries} in {wait}s ...")
            time.sleep(wait)
        except APIStatusError as e:
            raise RuntimeError(f"DeepSeek API-Fehler (HTTP {e.status_code}): {e.message}") from e
    raise RuntimeError("unreachable")


def _reasoning_tokens(resp):
    details = getattr(getattr(resp, "usage", None), "completion_tokens_details", None)
    return getattr(details, "reasoning_tokens", None) or 0


def chat_pro(messages):
    return _chat(config.MODEL_THINKING, messages, thinking=True)


def chat_flash(messages, *, json_mode=False):
    content, _, _ = _chat(config.MODEL_FAST, messages, thinking=False, json_mode=json_mode)
    return content
