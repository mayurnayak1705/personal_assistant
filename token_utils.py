"""Estimates token counts for storage in chat_history.token_count."""

try:
    import tiktoken

    _encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_encoding.encode(text or ""))

except ImportError:
    # Fallback if tiktoken isn't installed: rough word-based estimate.
    def count_tokens(text: str) -> int:
        return max(1, len((text or "").split()))