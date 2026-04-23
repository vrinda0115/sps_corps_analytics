import json
import os
from groq import Groq
from quiz_generator import generate_quiz, grade_short_answer, load_prompts
from dotenv import load_dotenv
load_dotenv()
# ── Groq client ────────────────────────────────────────────────────────────────
MODEL = "llama-3.1-8b-instant"

prompts = load_prompts()
sessions: dict = {}


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    return Groq(api_key=api_key)


def _call_groq(prompt: str, temperature: float = 0.3) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL,
        temperature=temperature,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _generate_question(learning_point: str) -> str:
    """Generate a Socratic question from the learning point."""
    prompt = (
        prompts["socratic_question"]
        .replace("{learning_point}", learning_point)
    )
    return _call_groq(prompt, temperature=0.5)


def _evaluate_answer(answer: str, learning_point: str) -> bool:
    """Return True if the employee's answer shows understanding."""
    prompt = (
        prompts["evaluate_answer"]
        .replace("{learning_point}", learning_point)
        .replace("{answer}", answer)
    )
    result = _call_groq(prompt, temperature=0.1)
    return "YES" in result.upper()


def _get_nudge(strike: int, learning_point: str, last_answer: str) -> str:
    """Return a one-sentence nudge tailored to their wrong answer."""
    prompt = (
        prompts["socratic_nudge"]
        .replace("{learning_point}", learning_point)
        .replace("{answer}", last_answer)
    )
    return _call_groq(prompt, temperature=0.4)


# ── Session management ────────────────────────────────────────────────────────

def get_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = {
            "state": "idle",        # idle | watching | questioning | quizzing | done
            "learning_points": [],
            "current_index": 0,
            "strikes": 0,
            "last_answer": "",
            "topic": None,
            "quiz_questions": None,
            "quiz_index": 0,
            "quiz_scores": []
        }
    return sessions[session_id]


def load_learning_points(path: str = "learning_points.json") -> dict:
    with open(path) as f:
        return json.load(f)


# ── Training flow ─────────────────────────────────────────────────────────────

def start_training(session_id: str, learning_points_path: str = "learning_points.json") -> dict:
    """
    Call this to kick off a training session.
    Pass a path to a learning_points.json produced by transcript_reader.py.
    """
    session = get_session(session_id)
    data = load_learning_points(learning_points_path)
    session["learning_points"] = data["learning_points"]
    session["topic"] = data["topic"]
    session["current_index"] = 0
    session["strikes"] = 0
    session["state"] = "watching"
    return _play_video(session)


def start_training_from_data(session_id: str, data: dict) -> dict:
    """
    Start a session directly from in-memory learning point data.
    Expected format: {"topic": str, "learning_points": list[str]}
    """
    session = get_session(session_id)
    session["learning_points"] = data["learning_points"]
    session["topic"] = data["topic"]
    session["current_index"] = 0
    session["strikes"] = 0
    session["state"] = "watching"
    session["quiz_questions"] = None
    session["quiz_index"] = 0
    session["quiz_scores"] = []
    return _play_video(session)


def video_finished(session_id: str) -> dict:
    """
    Call this when the video player fires its 'ended' event.
    Returns the Socratic question for the current learning point.
    """
    session = get_session(session_id)
    session["state"] = "questioning"
    current_point = session["learning_points"][session["current_index"]]
    return {
        "state": "questioning",
        "learning_point": current_point,
        "question": _generate_question(current_point),
        "point_number": session["current_index"] + 1,
        "total_points": len(session["learning_points"])
    }


def handle_answer(session_id: str, answer: str) -> dict:
    """
    Submit the employee's answer to the current Socratic question.
    Handles strike logic: nudge → nudge → replay video.
    """
    session = get_session(session_id)
    if session["state"] != "questioning":
        return {"error": "Not currently in questioning state."}

    current_point = session["learning_points"][session["current_index"]]
    session["last_answer"] = answer
    is_correct = _evaluate_answer(answer, current_point)

    if is_correct:
        session["strikes"] = 0
        return _advance(session)

    session["strikes"] += 1

    if session["strikes"] < 3:
        nudge = _get_nudge(session["strikes"], current_point, answer)
        return {
            "state": "questioning",
            "correct": False,
            "strike": session["strikes"],
            "message": nudge
        }

    # Strike 3 — replay the video
    session["strikes"] = 0
    session["state"] = "watching"
    return {
        "state": "watching",
        "correct": False,
        "strike": 3,
        "message": "No worries — let's watch the video one more time.",
        "video_trigger": True,
        "video_path": _get_video_path(session),
        "replay": True
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _advance(session: dict) -> dict:
    """Move to the next learning point, or start the quiz if all done."""
    session["current_index"] += 1

    if session["current_index"] >= len(session["learning_points"]):
        session["state"] = "quizzing"
        session["quiz_questions"] = generate_quiz(session["topic"], prompts)
        session["quiz_index"] = 0
        session["quiz_scores"] = []
        return {
            "state": "ready_to_quiz",
            "message": "Great job! You've covered all the key points. Ready for a quick quiz?",
            "quiz_ready": True
        }

    session["state"] = "watching"
    session["strikes"] = 0
    return _play_video(session)


def _play_video(session: dict) -> dict:
    current_point = session["learning_points"][session["current_index"]]
    return {
        "state": "watching",
        "video_trigger": True,
        "video_path": _get_video_path(session),
        "learning_point": current_point,
        "point_number": session["current_index"] + 1,
        "total_points": len(session["learning_points"])
    }


def _get_video_path(session: dict) -> str:
    return f"videos/point_{session['current_index'] + 1}.mp4"


# ── Quiz flow ─────────────────────────────────────────────────────────────────

def start_quiz(session_id: str) -> dict:
    session = get_session(session_id)
    session["state"] = "quizzing"
    return _next_question(session)


def submit_quiz_answer(session_id: str, answer: str) -> dict:
    session = get_session(session_id)
    if session["state"] != "quizzing":
        return {"error": "Not currently in quiz mode."}

    questions = session["quiz_questions"]
    idx = session["quiz_index"]
    current_q = questions[idx]

    if current_q["type"] == "mcq":
        passed = answer.strip().upper() == current_q["answer"].strip().upper()
        feedback = "Correct!" if passed else f"The correct answer was {current_q['answer']}."

    elif current_q["type"] == "truefalse":
        trainee = answer.strip().lower() in ("true", "yes", "1")
        passed = trainee == current_q["answer"]
        feedback = "Correct!" if passed else f"The correct answer was {current_q['answer']}."

    else:  # short answer — LLM graded
        result = grade_short_answer(
            question=current_q["question"],
            expected=current_q["answer"],
            trainee_answer=answer,
            prompts=prompts
        )
        passed = result["pass"]
        feedback = result["feedback"]

    session["quiz_scores"].append({
        "question": current_q["question"],
        "passed": passed,
        "feedback": feedback
    })
    session["quiz_index"] += 1

    if session["quiz_index"] >= len(questions):
        return _finish_quiz(session)

    return {"feedback": feedback, "passed": passed, **_next_question(session)}


def _next_question(session: dict) -> dict:
    q = session["quiz_questions"][session["quiz_index"]]
    return {
        "state": "quizzing",
        "question_number": session["quiz_index"] + 1,
        "total_questions": len(session["quiz_questions"]),
        "question": q["question"],
        "type": q["type"],
        "options": q.get("options")
    }


def _finish_quiz(session: dict) -> dict:
    session["state"] = "done"
    scores = session["quiz_scores"]
    passed = sum(1 for s in scores if s["passed"])
    return {
        "state": "done",
        "score": f"{passed}/{len(scores)}",
        "passed": passed,
        "total": len(scores),
        "breakdown": scores,
        "message": "Quiz complete! Training session finished."
    }


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    test_data = {
        "topic": "fire safety evacuation procedures",
        "learning_points": [
            "Employees must evacuate immediately upon hearing the fire alarm.",
            "The designated assembly point is located outside the main entrance."
        ]
    }
    with open("learning_points.json", "w") as f:
        json.dump(test_data, f)

    sid = "test-001"

    print("=== Starting training ===")
    print(start_training(sid))

    print("\n=== Video finished — ask question ===")
    print(video_finished(sid))

    print("\n=== Wrong answer (Strike 1) ===")
    print(handle_answer(sid, "I don't know"))

    print("\n=== Wrong answer (Strike 2) ===")
    print(handle_answer(sid, "maybe run outside?"))

    print("\n=== Wrong answer (Strike 3 — replay) ===")
    print(handle_answer(sid, "not sure"))

    print("\n=== Video finished again ===")
    print(video_finished(sid))

    print("\n=== Correct answer ===")
    print(handle_answer(sid, "Stop everything and evacuate the building immediately when the alarm goes off."))
