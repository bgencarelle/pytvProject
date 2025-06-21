import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.VideoClip import VideoClip

# CONFIGURATION
WIDTH, HEIGHT = 640, 480
FPS = 30
DURATION = 60  # seconds
TOTAL_FRAMES = FPS * DURATION

# Make font roughly 80% of one-third of the height
FONT_SIZE = int((HEIGHT / 4) * 0.8)
# On macOS, Arial lives here; on Linux you might use DejaVuSans:
FONT_PATH = "/Library/Fonts/Arial.ttf"
OUTPUT_FILE = "timer_green.mp4"

def format_time(frames_count):
    seconds_total, frames = divmod(frames_count, FPS)
    minutes, seconds = divmod(seconds_total, 60)
    return minutes, seconds, frames

def make_frame(t):
    idx = int(t * FPS)
    elapsed = idx
    remaining = TOTAL_FRAMES - idx
    total = TOTAL_FRAMES

    em, es, ef = format_time(elapsed)
    rm, rs, rf = format_time(remaining)
    tm, ts, tf = format_time(total)

    lines = [
        f"{rm:02d}:{rs:02d}:{rf:02d} rem",
        f"{em:02d}:{es:02d}:{ef:02d} el",
        f"{tm:02d}:{ts:02d}:{tf:02d} to"
    ]

    img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try to load a TrueType font at the computed size
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except IOError:
        # Fallback if the TTF isn’t found
        font = ImageFont.load_default()
        print("⚠️  Could not load TTF font; using default bitmap font.")

    # Centers of each third: 1/6, 3/6, 5/6
    y_centers = [HEIGHT * (2*i + 1) / 6 for i in range(3)]

    for text, yc in zip(lines, y_centers):
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (WIDTH - w) / 2
        y = yc - h / 2
        draw.text((x, y), text, font=font, fill=(0, 255, 255))

    return np.array(img)

def main():
    clip = VideoClip(make_frame, duration=DURATION)
    clip.write_videofile(
        OUTPUT_FILE,
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=4
    )

if __name__ == "__main__":
    main()
