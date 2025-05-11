# engine/gpt.py
# Async OpenAI call with retries and truncation
# engine/gpt.py – OpenAI SDK >= 1.0.0 compatible

import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4.1-mini"
TEMPERATURE = 0.7
MAX_TOKENS = 1024
API_RETRIES = 3
BACKOFF_SEC = 2
CONTEXT_LIMIT = 7000

def truncate(text, limit=CONTEXT_LIMIT):
    truncated = text if len(text) <= limit else text[:limit] + "\n[...truncated...]"
    if truncated != text:
        with open("logs/truncation_warnings.log", "a") as f:
            f.write(f"Truncation occurred for text: {text[:120]}...\n")
    return truncated

async def call_gpt(system_prompt, user_prompt, temperature=TEMPERATURE, seed=None, max_tokens=MAX_TOKENS):
    for attempt in range(API_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": truncate(user_prompt)}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed
            )
            # Optionally, log token usage: response.usage.total_tokens
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == API_RETRIES - 1:
                with open("logs/gpt_errors.log", "a") as f:
                    f.write(f"GPT call failed after {attempt+1} attempts. Error: {repr(e)}\nPrompt:\n{user_prompt[:200]}\n")
                raise
            await asyncio.sleep(BACKOFF_SEC * (attempt + 1))