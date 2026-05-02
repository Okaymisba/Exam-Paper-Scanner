"""
OBE Exam Sheet OCR Processor — GPT-4o Vision

Sends the exam sheet image to GPT-4o and extracts the achieved marks
for each question using structured JSON prompting.

Why GPT-4o:
  - Handles handwritten marks (red/blue pen) reliably
  - No local model, no PyTorch, no memory issues
  - Returns structured JSON directly, no parsing heuristics needed
  - Temperature=0 keeps results deterministic
"""

import base64
import json
import os
from pathlib import Path

from openai import OpenAI

# Singleton client — created once on first use
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _encode_image(image_path: str) -> tuple[str, str]:
    """Read image file and return (base64_string, media_type)."""
    suffix = Path(image_path).suffix.lower()
    media_types = {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
        ".gif":  "image/gif",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return encoded, media_type


def _build_system_prompt() -> str:
    return (
        "You are an expert at reading OBE (Outcome-Based Education) exam answer sheets. "
        "Your only job is to extract numbers from handwritten marks tables in exam images. "
        "You always respond with valid JSON and nothing else. "
        "You never hallucinate values — if a cell is empty or unreadable, you return 0."
    )


def _build_user_prompt(questions: list) -> str:
    """
    Build a precise extraction prompt tailored to the specific exam questions.
    The prompt tells GPT exactly what to look for and what to return.
    """
    question_list = "\n".join(
        f"  Question {q['no']}: maximum marks = {q['maxMarks']}"
        for q in questions
    )
    num_q = len(questions)

    return f"""Examine this OBE exam sheet image carefully.

The sheet contains a marks table with these rows:
1. Question numbers row:    "Q1", "Q2", ... or just "1", "2", ...
2. Maximum Marks row:       printed numbers showing the max marks per question
3. Achieved Marks row:      handwritten numbers (usually in red or blue pen) — THIS is what you must extract

The exam has {num_q} question(s):
{question_list}

Instructions:
- Find the "Achieved Marks", "Obtained Marks", or "Marks Obtained" row (it contains handwritten values)
- Do NOT read the "Maximum Marks" row — those are printed, not handwritten
- Extract the achieved mark for each question in order
- Each value must be between 0 and the maximum for that question; if it exceeds the max, cap it at the max
- If a cell is blank, crossed out, or illegible, use 0
- Provide a confidence score (0 to 100) for each value: 95+ means clearly readable, 70-94 means somewhat clear, below 70 means guessed

Respond with ONLY this JSON structure, no markdown, no explanation:
{{
  "marks": [
    {{"questionNo": 1, "obtained": <number>, "confidence": <0-100>}},
    {{"questionNo": 2, "obtained": <number>, "confidence": <0-100>}}
  ]
}}

Include exactly {num_q} entries in order. All values must be numbers, not strings."""


def process_image(image_path: str, setup: dict) -> dict:
    """
    Extract achieved marks from one OBE exam sheet image.

    Args:
        image_path: Path to the uploaded image file.
        setup:      Exam config dict with a "questions" list, each containing
                    keys: no, clo, maxMarks.

    Returns:
        {
          "marks": [
            {"questionNo": int, "clo": int, "maxMarks": float,
             "obtained": float, "confidence": float},
            ...
          ]
        }

    Raises:
        ValueError: If the image cannot be read or the API returns unexpected output.
    """
    questions = setup.get("questions", [])
    if not questions:
        return {"marks": []}

    image_data, media_type = _encode_image(image_path)
    client = _get_client()

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": _build_system_prompt(),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": _build_user_prompt(questions),
                    },
                ],
            },
        ],
    )

    raw_json = response.choices[0].message.content
    parsed = json.loads(raw_json)
    raw_marks = parsed.get("marks", [])

    # Build lookup: questionNo -> {obtained, confidence}
    gpt_map = {
        int(m["questionNo"]): {
            "obtained":   float(m.get("obtained", 0)),
            "confidence": float(m.get("confidence", 80)),
        }
        for m in raw_marks
    }

    marks = []
    for q in questions:
        q_no  = int(q.get("no", 0))
        q_max = float(q.get("maxMarks", 0))
        entry = gpt_map.get(q_no, {"obtained": 0.0, "confidence": 0.0})

        obtained = entry["obtained"]
        if q_max > 0 and obtained > q_max:
            obtained = q_max

        marks.append({
            "questionNo": q_no,
            "clo":        int(q.get("clo", 1)),
            "maxMarks":   q_max,
            "obtained":   obtained,
            "confidence": entry["confidence"],
        })

    return {"marks": marks}
