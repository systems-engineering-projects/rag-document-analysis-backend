

class LLMServiceError(Exception):
    """LLM or embedding API returned an error (4xx/5xx)."""

class LLMTimeoutError(Exception):
    """LLM request timed out."""

class LLMRateLimitedError(Exception):
    """API returned 429 rate limit."""

class LLMUpstreamTimeoutError(Exception):
    """Embedding request timed out."""