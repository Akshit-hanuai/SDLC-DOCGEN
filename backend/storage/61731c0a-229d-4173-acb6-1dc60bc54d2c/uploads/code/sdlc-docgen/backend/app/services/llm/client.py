import httpx

from app.config import settings

GROUNDING_MARKER = "GROUNDING CHUNKS:"


class LLMClient:
    name: str = "base"

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class VLLMClient(LLMClient):
    name = "vllm"

    def __init__(self) -> None:
        self.url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        self.headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 1500,
        }
        response = httpx.post(
            self.url, headers=self.headers, json=payload, timeout=settings.llm_timeout_s
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class MockLLMClient(LLMClient):
    name = "mock"

    def complete(self, system: str, user: str) -> str:
        chunks = _extract_chunks(user)
        if chunks:
            body = "\n".join(
                f"- {hit['text']}  [source: {hit['source_file']} / {hit['heading']}]"
                for hit in chunks[:5]
            )
            return f"DRAFT (mock, grounded on {len(chunks)} retrieved chunks):\n{body}"
        return "DRAFT (mock, no grounding chunks retrieved): please review and expand."


def _extract_chunks(user: str) -> list[dict]:
    if GROUNDING_MARKER not in user:
        return []
    payload = user.split(GROUNDING_MARKER, 1)[1]
    chunks: list[dict] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            parts = ["", "", " | ".join(parts)]
        source_file, heading, text = parts
        chunks.append({"source_file": source_file.strip(), "heading": heading.strip(), "text": text.strip()[:500]})
    return chunks


def probe_vllm() -> bool:
    try:
        response = httpx.get(settings.llm_base_url.rstrip("/") + "/models", timeout=settings.llm_probe_s)
        return response.status_code == 200
    except Exception:
        return False


_cache: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _cache
    if _cache is not None:
        return _cache
    mode = settings.llm_mode.lower()
    if mode == "vllm":
        _cache = VLLMClient()
    elif mode == "mock":
        _cache = MockLLMClient()
    else:
        _cache = VLLMClient() if probe_vllm() else MockLLMClient()
    return _cache
