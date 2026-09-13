from __future__ import annotations
from typing import Any
from openai import OpenAI
from .config import OPENAI_API_KEY, OPENAI_MODEL

SYSTEM_PROMPT = """You are the ETDS Operations AI, an electricity theft detection monitoring assistant.
Use only the telemetry and incident context supplied to you. Do not invent live readings, incidents, meter locations, or metrics.
Explain whether a condition indicates possible theft, normal operation, or a sensor/quality problem. Distinguish evidence from inference.
For confirmed or strongly suspected theft, recommend immediate human inspection and safe electrical isolation procedures by qualified personnel; do not instruct a user to touch live electrical equipment.
Keep answers concise, professional, and useful to an operator."""


def ask_ai(question: str, context: dict[str, Any]) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError('OPENAI_API_KEY is not configured on the backend.')
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"{SYSTEM_PROMPT}\n\nLIVE ETDS CONTEXT:\n{context}\n\nOPERATOR QUESTION:\n{question}"
    response = client.responses.create(model=OPENAI_MODEL, input=prompt)
    text = getattr(response, 'output_text', None)
    if text:
        return text.strip()
    return 'The AI service returned no text response.'
