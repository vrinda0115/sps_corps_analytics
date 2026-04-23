from text_to_video import generate_video
import json
import os

def generate_videos_from_points(json_path="learning_points.json"):
    with open(json_path) as f:
        data = json.load(f)

    os.makedirs("videos", exist_ok=True)

    for i, point in enumerate(data["learning_points"], 1):
        print(f"Generating video {i}: {point[:50]}...")
        generate_video(
            text=point,
            output_path=f"videos/point_{i}.mp4"
        )
    print("✅ All videos ready!")

if __name__ == "__main__":
    generate_videos_from_points()