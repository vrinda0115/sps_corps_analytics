import os
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from socratic_logic import (
    get_session,
    handle_answer,
    start_quiz,
    start_training_from_data,
    submit_quiz_answer,
    video_finished,
)
from text_to_video import generate_video
from transcript_reader import extract_from_file


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="SPS Corps Analytics API",
    description="Backend API for transcript extraction, training sessions, and quiz flow.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")


class LearningPointsPayload(BaseModel):
    topic: str
    learning_points: List[str] = Field(min_length=1)


class CreateSessionPayload(BaseModel):
    topic: str
    learning_points: List[str] = Field(min_length=1)
    session_id: Optional[str] = None
    generate_videos: bool = False


class AnswerPayload(BaseModel):
    answer: str = Field(min_length=1)


def _normalize_video_url(video_path: str) -> str:
    filename = Path(video_path).name
    return f"/videos/{filename}"


def _with_video_url(payload: dict) -> dict:
    if payload.get("video_path"):
        payload["video_url"] = _normalize_video_url(payload["video_path"])
    return payload


def _create_videos(learning_points: List[str]) -> List[str]:
    urls = []
    for index, point in enumerate(learning_points, start=1):
        output_path = VIDEOS_DIR / f"point_{index}.mp4"
        generate_video(point, str(output_path))
        urls.append(_normalize_video_url(str(output_path)))
    return urls


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/api/learning-points/extract")
async def extract_learning_points(
    file: UploadFile = File(...),
    topic: str = Form(...),
) -> dict:
    suffix = Path(file.filename or "transcript.txt").suffix or ".txt"

    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await file.read())
        temp_path = temp_file.name

    try:
        data = extract_from_file(
            file_path=temp_path,
            topic=topic,
            output_path=str(BASE_DIR / "learning_points.json"),
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/videos/generate")
def generate_videos(payload: LearningPointsPayload) -> dict:
    try:
        return {"videos": _create_videos(payload.learning_points)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/sessions")
def create_session(payload: CreateSessionPayload) -> dict:
    session_id = payload.session_id or str(uuid.uuid4())

    try:
        result = start_training_from_data(
            session_id=session_id,
            data={
                "topic": payload.topic,
                "learning_points": payload.learning_points,
            },
        )
        response = {"session_id": session_id, **_with_video_url(result)}

        if payload.generate_videos:
            response["videos"] = _create_videos(payload.learning_points)

        return response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}")
def get_session_state(session_id: str) -> dict:
    return get_session(session_id)


@app.post("/api/sessions/{session_id}/video-finished")
def mark_video_finished(session_id: str) -> dict:
    try:
        return video_finished(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/answers")
def submit_answer(session_id: str, payload: AnswerPayload) -> dict:
    result = handle_answer(session_id, payload.answer)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return _with_video_url(result)


@app.post("/api/sessions/{session_id}/quiz/start")
def begin_quiz(session_id: str) -> dict:
    try:
        return start_quiz(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/quiz/answer")
def submit_quiz(session_id: str, payload: AnswerPayload) -> dict:
    result = submit_quiz_answer(session_id, payload.answer)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
