"""
transcript_reader.py
────────────────────
Reads a real HR training transcript (.txt or .pdf text dump) and extracts
structured learning points using Groq's LLM API.

Usage (CLI):
    python transcript_reader.py --file my_transcript.txt --topic "fire safety"

Usage (import):
    from transcript_reader import extract_from_file
    data = extract_from_file("onboarding.txt", topic="employee onboarding")
"""

import json
import re
import os
import argparse
from groq import Groq
from quiz_generator import load_prompts
from dotenv import load_dotenv
load_dotenv()

# ── Groq client ────────────────────────────────────────────────────────────────
MODEL = "llama-3.1-8b-instant"

# Max characters to send per chunk (Groq context is large but keep it safe)
CHUNK_SIZE = 6000


# ── Core functions ─────────────────────────────────────────────────────────────

def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    return Groq(api_key=api_key)


def read_transcript(file_path: str) -> str:
    """Read a plain-text transcript file. Strips excessive whitespace."""
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()
    # Normalize whitespace but keep paragraph breaks
    raw = re.sub(r"\r\n", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _chunk_transcript(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split long transcripts into overlapping chunks so no content is missed.
    Splits on paragraph boundaries where possible.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = para  # start next chunk (no overlap needed for extraction)
        else:
            current += "\n\n" + para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _call_groq(prompt: str) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL,
        temperature=0.2,   # low temp = consistent structured extraction
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _extract_json_list(text: str) -> list:
    """Parse a JSON array from LLM output, stripping markdown fences."""
    clean = re.sub(r"```json|```", "", text).strip()
    start = clean.find("[")
    end = clean.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in response:\n{text}")
    clean = clean[start:end + 1]
    clean = re.sub(r'(?<!\\)\n', ' ', clean)
    return json.loads(clean)


def _deduplicate(points: list[str]) -> list[str]:
    """Remove near-duplicate learning points (case-insensitive first-word match)."""
    seen = set()
    unique = []
    for p in points:
        key = p.strip().lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(p.strip())
    return unique


def extract_concepts(transcript_text: str, topic: str, prompts: dict) -> dict:
    """
    Extract 3-5 learning points from a transcript.
    Handles long transcripts by chunking and merging results.
    """
    chunks = _chunk_transcript(transcript_text)
    all_points = []

    for i, chunk in enumerate(chunks):
        prompt = prompts["extract_learning_points"].replace("{content}", chunk)
        raw = _call_groq(prompt)
        try:
            points = _extract_json_list(raw)
            all_points.extend(points)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"  ⚠ Chunk {i+1} parse error: {e} — skipping")

    # Deduplicate and cap at 5
    all_points = _deduplicate(all_points)[:5]

    if not all_points:
        raise RuntimeError("No learning points could be extracted. Check the transcript content.")

    return {
        "topic": topic,
        "learning_points": all_points
    }


def save_learning_points(data: dict, output_path: str = "learning_points.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved {len(data['learning_points'])} learning points to {output_path}")


# ── Convenience wrapper ────────────────────────────────────────────────────────

def extract_from_file(
    file_path: str,
    topic: str,
    prompts_path: str = "prompts.json",
    output_path: str = "learning_points.json"
) -> dict:
    """
    Full pipeline: read transcript → extract → save → return data.

    Args:
        file_path:    Path to the .txt transcript file
        topic:        Short topic label e.g. "fire safety evacuation"
        prompts_path: Path to prompts.json
        output_path:  Where to write learning_points.json

    Returns:
        dict with keys 'topic' and 'learning_points'
    """
    prompts = load_prompts(prompts_path)
    print(f"Reading transcript: {file_path}")
    transcript = read_transcript(file_path)
    print(f"  → {len(transcript)} characters, extracting learning points...")

    data = extract_concepts(transcript, topic, prompts)

    print("\nExtracted learning points:")
    for i, point in enumerate(data["learning_points"], 1):
        print(f"  {i}. {point}")

    save_learning_points(data, output_path)
    return data


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract HR training learning points from a transcript file."
    )
    parser.add_argument("--file",   required=True, help="Path to transcript .txt file")
    parser.add_argument("--topic",  required=True, help="Short topic label (e.g. 'fire safety')")
    parser.add_argument("--output", default="learning_points.json", help="Output JSON path")
    args = parser.parse_args()

    extract_from_file(
        file_path=args.file,
        topic=args.topic,
        output_path=args.output
    )
