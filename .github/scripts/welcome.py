import os
from PIL import Image, ImageSequence

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

SOURCE = os.path.join(REPO_ROOT, ".github", "assets", "bearu.gif")
OUTPUT = os.path.join(REPO_ROOT, "welcome.gif")
TARGET_WIDTH = 830  

def load_frames(path):
    im = Image.open(path)
    frames, durations = [], []
    for frame in ImageSequence.Iterator(im):
        frames.append(frame.convert("RGBA").copy())
        durations.append(frame.info.get("duration", 70))
    return frames, durations, im.info.get("loop", 0)


def tile_horizontally(frames, n):
    bear_w, bear_h = frames[0].size
    canvas_w = bear_w * n
    tiled = []
    for f in frames:
        canvas = Image.new("RGBA", (canvas_w, bear_h), (0, 0, 0, 0))
        for i in range(n):
            canvas.alpha_composite(f, (i * bear_w, 0))
        tiled.append(canvas)
    return tiled, canvas_w, bear_h


def save_animated_gif(frames_rgba, out_path, durations, loop=0):
    base = frames_rgba[0]
    combined = Image.new("RGBA", (base.width * len(frames_rgba), base.height))
    for i, f in enumerate(frames_rgba):
        combined.paste(f, (i * base.width, 0))
    pal_source = combined.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT)
    palette = pal_source.getpalette()

    quantized_frames = []
    for f in frames_rgba:
        rgb = f.convert("RGB").quantize(palette=pal_source, dither=Image.FLOYDSTEINBERG)
        rgb.putpalette(palette)
        alpha = f.split()[-1]
        mask = alpha.point(lambda a: 255 if a < 128 else 0)
        rgb.paste(255, mask) 
        quantized_frames.append(rgb)

    quantized_frames[0].save(
        out_path,
        save_all=True,
        append_images=quantized_frames[1:],
        duration=durations,
        loop=loop,
        disposal=2,
        transparency=255,
        optimize=True,
    )


if __name__ == "__main__":
    frames, durations, loop = load_frames(SOURCE)
    bear_w, bear_h = frames[0].size
    n = max(1, round(TARGET_WIDTH / bear_w))
    tiled_frames, out_w, out_h = tile_horizontally(frames, n)
    save_animated_gif(tiled_frames, OUTPUT, durations, loop)
    print(f"bear width: {bear_w}px, repeats: {n}, output width: {out_w}px (target was {TARGET_WIDTH}px)")
