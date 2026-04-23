from transcript_reader import extract_from_file
from video_pipeline import generate_videos_from_points

def run():
    print("Step 1: Extracting learning points...")
    extract_from_file("sample.txt", "fire safety")

    print("\nStep 2: Generating videos...")
    generate_videos_from_points()

    print("\n✅ Everything ready!")

if __name__ == "__main__":
    run()