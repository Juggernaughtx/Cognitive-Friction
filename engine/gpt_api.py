# engine/gpt_api.py
# Async OpenAI call with retries and truncation
# engine/gpt_api.py – OpenAI SDK >= 1.0.0 compatible

import logging
import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini") # update as needed

def force_json_instruction(prompt) -> str:
    # Adds a hard "return ONLY valid JSON" line
    return (
        prompt.strip() + "\n\n"
        "OUTPUT INSTRUCTIONS: Output ONLY a valid JSON object. "
        "Do NOT include markdown/codefences, preamble, or explanation. "
        "If you do not output valid JSON, your work will be discarded. "
        "This instruction is mandatory."
    )

async def call_gpt(
    system_prompt,
    user_prompt,
    temperature=0.7,
    seed=None,
    max_tokens=1024,
    expect_json=False
):
    tries = 2
    user_message = user_prompt
    use_response_format = {}
    if expect_json:
        user_message = force_json_instruction(user_prompt)
        use_response_format = {"type": "json_object"}
    for attempt in range(tries):
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                **({"response_format": use_response_format} if expect_json else {})
            )
            # [OpenAI guarantees JSON if you do the above right]
            resp = response.choices[0].message.content.strip()
            if expect_json:
                try:
                    return json.loads(resp)
                except Exception as e:
                    # Fail fast: log the problem and raise for the caller to decide
                    logging.error(f"LLM JSON parse error: {e}\n---RAW OUTPUT BEGIN---\n{resp}\n---RAW OUTPUT END---")
                    raise
            return resp
        except json.JSONDecodeError:
            # Retry: If first attempt fails, send LLM its own output and ask for valid JSON conversion
            if attempt == tries - 1:
                raise
            # Re-prompt: ask GPT to fix its own output
            fix_prompt = (
                "You previously responded with invalid JSON.\n"
                "Here is your previous output:\n\n"
                f"{resp}\n\n"
                "Repair this so it is ONLY valid JSON (no codefence, no preamble, no explanation)."
            )
            user_message = fix_prompt
        except Exception as e:
            # log and re-raise
            with open("logs/gpt_api_errors.log", "a") as log:
                log.write(f"GPT API failure: {repr(e)}\nPrompt: {user_prompt[:200]}\n")
            if attempt == tries - 1:
                raise
