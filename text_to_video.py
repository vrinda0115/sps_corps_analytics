import os
import subprocess
import soundfile as sf
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from kokoro import KPipeline

pipeline = None


def _get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = KPipeline(lang_code='a')
    return pipeline


def generate_video(text: str, output_path: str) -> str:
    base = output_path.replace('.mp4', '')
    audio_path = base + '.wav'
    slide_path = base + '.png'

    # Step 1: Generate audio — collect ALL chunks then write once
    generator = _get_pipeline()(text, voice='af_heart', speed=1.1)
    all_audio = []
    for i, (gs, ps, audio) in enumerate(generator):
        all_audio.append(audio)

    if not all_audio:
        raise RuntimeError(f"Kokoro returned no audio for: {text[:50]}")

    sf.write(audio_path, np.concatenate(all_audio), 24000)
    print(f"  ✓ Audio written: {audio_path}")

    # Step 2: Create slide image
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 120)
    wrapper = textwrap.TextWrapper(width=25)
    wrapped_text = wrapper.fill(text=text)
    draw.multiline_text(
        (width / 2, height / 2), wrapped_text, font=font,
        fill=(255, 255, 255), anchor='mm', align='center', spacing=30
    )
    img.save(slide_path)
    print(f"  ✓ Slide written: {slide_path}")

    # Step 3: Merge into .mp4 using subprocess.run (WAITS for ffmpeg to finish)
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", slide_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        # Print ffmpeg error so you can debug
        print("  ✗ ffmpeg error:")
        print(result.stderr.decode())
        raise RuntimeError(f"ffmpeg failed for {output_path}")

    print(f"  ✓ Video written: {output_path}")

    # Step 4: Cleanup — only AFTER ffmpeg is confirmed done
    os.remove(audio_path)
    os.remove(slide_path)

    return output_path


if __name__ == '__main__':
    os.makedirs('videos', exist_ok=True)
    result = generate_video(
        text='Employees must evacuate immediately upon hearing the fire alarm.',
        output_path='videos/test_point.mp4'
    )
    print(f'\nVideo saved at: {result}')
