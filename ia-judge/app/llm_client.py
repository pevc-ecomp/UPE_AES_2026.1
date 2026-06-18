from openai import OpenAI
from app.config import settings


client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)


def ask_llm(prompt: str) -> str:
    """Send a prompt to the local LLM and return the raw text response."""

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict but simple academic AI judge for systematic literature reviews. "
                    "You must answer only with valid JSON. "
                    "Do not include markdown, comments, or explanations outside the JSON. "
                    "When evidence is insufficient, be conservative and recommend human review."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    return response.choices[0].message.content or ""
