import json
import re
import os
from groq import Groq
from dotenv import load_dotenv
load_dotenv()
# ── Groq client ────────────────────────────────────────────────────────────────
# Set your key once: export GROQ_API_KEY="gsk_..."
# Get a free key at: https://console.groq.com
MODEL = "llama-3.1-8b-instant"   # free, fast, matches original spec


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    return Groq(api_key=api_key)


def _call_groq(prompt: str, temperature: float = 0.3) -> str:
    """Single-turn completion via Groq. Returns raw response text."""
    response = _get_client().chat.completions.create(
        model=MODEL,
        temperature=temperature,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str):
    """
    Robustly parse JSON from LLM output that may contain:
    - markdown fences (```json ... ```)
    - leading/trailing prose
    - unescaped newlines inside string values
    """
    # Strip markdown fences
    clean = re.sub(r"```json|```", "", text).strip()

    # Find where the JSON structure starts
    start = min(
        (clean.index(c) for c in ("[", "{") if c in clean),
        default=0
    )
    clean = clean[start:]

    # Find where it ends (last ] or })
    for end_char in ("]", "}"):
        last = clean.rfind(end_char)
        if last != -1:
            clean = clean[:last + 1]
            break

    # Remove unescaped control characters that break JSON parsing
    clean = re.sub(r'(?<!\\)\n', ' ', clean)
    clean = re.sub(r'(?<!\\)\r', ' ', clean)
    clean = re.sub(r'(?<!\\)\t', ' ', clean)

    return json.loads(clean)


# ── Public functions ───────────────────────────────────────────────────────────

def generate_quiz(topic: str, prompts: dict) -> list:
    """Generate 5 quiz questions (2 MCQ, 2 T/F, 1 short) for a given topic."""
    prompt = prompts["quiz_generate"].replace("{topic}", topic)
    raw = _call_groq(prompt, temperature=0.4)
    questions = _extract_json(raw)

    # Safety check — Groq is reliable but validate structure
    if not isinstance(questions, list) or len(questions) != 5:
        raise ValueError(f"Expected 5 questions, got {len(questions) if isinstance(questions, list) else 'non-list'}")

    return questions


def grade_short_answer(question: str, expected: str, trainee_answer: str, prompts: dict) -> dict:
    """Use LLM to grade a free-text answer. Returns {pass: bool, feedback: str}."""
    prompt = (
        prompts["quiz_grade_short"]
        .replace("{question}", question)
        .replace("{expected}", expected)
        .replace("{trainee_answer}", trainee_answer)
    )
    raw = _call_groq(prompt, temperature=0.1)  # low temp for consistent grading
    result = _extract_json(raw)
    return result


def load_prompts(path: str = "prompts.json") -> dict:
    with open(path) as f:
        return json.load(f)


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    prompts = load_prompts()
    topic = "workplace fire safety evacuation procedures"

    print("Generating quiz questions...\n")
    questions = generate_quiz(topic, prompts)

    for i, q in enumerate(questions, 1):
        print(f"Q{i} [{q['type']}]: {q['question']}")
        if q["type"] == "mcq":
            for opt in q["options"]:
                print(f"   {opt}")
        print(f"   Answer: {q['answer']}\n")

    print("Testing short answer grader...\n")
    short_q = next(q for q in questions if q["type"] == "short")
    result = grade_short_answer(
        question=short_q["question"],
        expected=short_q["answer"],
        trainee_answer="I'm not sure what to do",
        prompts=prompts
    )
    print(f"Grade result: {result}")
