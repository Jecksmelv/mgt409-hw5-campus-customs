"""The single model definition shared by all five agents.

Every AI call in this project goes through Portkey with PORTKEY_API_KEY and the
model named in MODEL_NAME. There is deliberately no fallback model.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

PROJECT_DIR = Path(__file__).resolve().parent.parent

# The only model allowed anywhere in this assignment.
MODEL_NAME = "gpt-6-luna"

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PORTKEY_PROVIDER = "openai"

# hw5/.env first (copy .env.example), then a .env in up to two parent folders. Values are never printed.
for folder in (PROJECT_DIR, PROJECT_DIR.parent, PROJECT_DIR.parent.parent):
    load_dotenv(folder / ".env")


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    api_key = os.environ.get("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Copy .env.example to .env in the hw5 folder and add your key.")
    client = AsyncOpenAI(
        api_key="not-used-directly",  # Portkey authenticates with the header below
        base_url=PORTKEY_BASE_URL,
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": PORTKEY_PROVIDER,
        },
        max_retries=2,
        timeout=90,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
