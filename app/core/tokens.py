"""Estimates token counts for storage in chat_history.token_count."""

try:
    import tiktoken

    _encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_encoding.encode(text or ""))

except Exception:
    # tiktoken may be installed but unable to populate its model cache on an
    # offline first run. Token counts are bookkeeping only, so this must not
    # prevent the assistant from starting.
    def count_tokens(text: str) -> int:
        return max(1, len((text or "").split()))
