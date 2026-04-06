import os
import soundfile as sf
import textwrap
from PIL import Image, ImageDraw, ImageFont
from kokoro import KPipeline
 
pipeline = KPipeline(lang_code='a')
 
def generate_video(text: str, output_path: str) -> str:
    base = output_path.replace('.mp4', '')
    audio_path = base + '.wav'
    slide_path = base + '.png'
 
    # Step 1: Generate audio
    generator = pipeline(text, voice='af_heart', speed=1.1)
    for i, (gs, ps, audio) in enumerate(generator):
        sf.write(audio_path, audio, 24000)
 
    # Step 2: Create slide image
    width, height = 1920, 1080
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 120)
    wrapper = textwrap.TextWrapper(width=25)
    wrapped_text = wrapper.fill(text=text)
    draw.multiline_text((width/2, height/2), wrapped_text, font=font,
                        fill=(255, 255, 255), anchor='mm',
                        align='center', spacing=30)
    img.save(slide_path)
 
    # Step 3: Merge into .mp4
    os.system(f'ffmpeg -y -loop 1 -i "{slide_path}" -i "{audio_path}"'
              f' -c:v libx264 -tune stillimage -c:a aac -b:a 192k'
              f' -pix_fmt yuv420p -shortest "{output_path}"')
 
    return output_path
 
if __name__ == '__main__':
    os.makedirs('videos', exist_ok=True)
    result = generate_video(
        text='Employees must evacuate immediately upon hearing the fire alarm.',
        output_path='videos/test_point.mp4'
    )
    print(f'Video saved at: {result}')
