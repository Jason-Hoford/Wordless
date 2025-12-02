import argparse
import random
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TTF/TTC font at a given size."""
    return ImageFont.truetype(font_path, size=size)


def sample_region_luminance(img_gray: Image.Image, x: int, y: int, step: int) -> float:
    """
    Return average luminance (0=black, 255=white) in a step x step block
    with top-left at (x, y), clamped to image bounds.
    """
    x2 = min(x + step, img_gray.width)
    y2 = min(y + step, img_gray.height)

    region = img_gray.crop((x, y, x2, y2))
    pixels = list(region.getdata())
    if not pixels:
        return 255.0

    return sum(pixels) / len(pixels)


def choose_word(words: List[str]) -> str:
    """Randomly choose a word/character."""
    return random.choice(words)


def luminance_to_alpha_and_density(
    lum: float,
    base_alpha: int,
    alpha_boost_dark: int,
    density_scale: float,
) -> Tuple[int, float]:
    """
    Convert luminance to (alpha, density_factor).

    - Darker areas -> higher alpha & more density.
    - Lighter areas -> lower alpha & less density.
    """
    t = lum / 255.0  # 0=black, 1=white

    alpha = int(base_alpha + (1.0 - t) * alpha_boost_dark)
    alpha = max(0, min(255, alpha))

    density = (1.0 - t) * density_scale
    return alpha, density


def draw_layer(
    canvas: Image.Image,
    img_gray: Image.Image,
    font_path: str,
    font_size: int,
    words: List[str],
    step: int,
    base_alpha: int,
    alpha_boost_dark: int,
    density_scale: float,
    color: Tuple[int, int, int],
    random_jitter: float = 0.3,
    allow_rotation: bool = False,
) -> None:
    """
    Draw one layer of words over the canvas.

    - `step`: grid spacing for sampling and positioning.
    - `font_size`: base font size for this layer.
    - `density_scale`: how many words on this layer; higher => denser.
    - `random_jitter`: fraction of `step` used to jitter positions.
    """
    w, h = img_gray.size
    base_font = load_font(font_path, font_size)

    for y in range(0, h, step):
        for x in range(0, w, step):
            lum = sample_region_luminance(img_gray, x, y, step)
            alpha, density = luminance_to_alpha_and_density(
                lum,
                base_alpha=base_alpha,
                alpha_boost_dark=alpha_boost_dark,
                density_scale=density_scale,
            )

            if random.random() > density:
                continue

            word = choose_word(words)

            jitter_x = (random.random() - 0.5) * 2 * step * random_jitter
            jitter_y = (random.random() - 0.5) * 2 * step * random_jitter
            px = x + step / 2 + jitter_x
            py = y + step / 2 + jitter_y

            size_variation = random.uniform(0.9, 1.2)
            fsize = max(6, int(font_size * size_variation))
            font = base_font if fsize == font_size else load_font(font_path, fsize)

            # Measure text using getbbox (compatible with modern Pillow)
            bbox = font.getbbox(word)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = int(px - tw / 2)
            ty = int(py - th / 2)

            if allow_rotation:
                angle = random.uniform(-25, 25)
                tmp = Image.new("RGBA", (tw * 2, th * 2), (0, 0, 0, 0))
                tmp_draw = ImageDraw.Draw(tmp)
                tmp_draw.text(
                    (tw / 2, th / 2),
                    word,
                    font=font,
                    fill=(color[0], color[1], color[2], alpha),
                    anchor="mm",
                )
                tmp = tmp.rotate(angle, expand=1)
                bbox = tmp.getbbox()
                if bbox:
                    rw, rh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    cx = int(px - rw / 2)
                    cy = int(py - rh / 2)
                    canvas.alpha_composite(tmp, dest=(cx, cy))
            else:
                draw = ImageDraw.Draw(canvas)
                draw.text(
                    (tx, ty),
                    word,
                    font=font,
                    fill=(color[0], color[1], color[2], alpha),
                )


def build_word_image(
    input_path: str,
    output_path: str,
    font_path: str,
    max_width: int = 800,
    background: Tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Build the multi-layer word-based recreation of an image."""
    img = Image.open(input_path).convert("RGB")
    w, h = img.size
    # Always scale to max_width so the generated image can be larger than
    # the original and carry more visible word detail.
    scale = max_width / float(w)
    img = img.resize((max_width, int(h * scale)), Image.LANCZOS)

    img_gray = img.convert("L")
    w, h = img_gray.size

    canvas = Image.new("RGBA", (w, h), background + (255,))

    chinese_words = list("天地人和山水风云日月星辰光影黑白虚实梦境文字重叠层次深浅变化")

    layers = [
        dict(
            font_size=50,
            step=50,
            base_alpha=10,
            alpha_boost_dark=180,
            density_scale=0.7,
            color=(0, 0, 0),
            allow_rotation=False,
        ),
        dict(
            font_size=30,
            step=26,
            base_alpha=20,
            alpha_boost_dark=150,
            density_scale=1.2,
            color=(0, 0, 0),
            allow_rotation=True,
        ),
        dict(
            font_size=18,
            step=14,
            base_alpha=40,
            alpha_boost_dark=160,
            density_scale=1.6,
            color=(0, 0, 0),
            allow_rotation=True,
        ),
        dict(
            font_size=12,
            step=10,
            base_alpha=30,
            alpha_boost_dark=200,
            density_scale=1.3,
            color=(0, 0, 0),
            allow_rotation=False,
        ),
    ]

    for layer in layers:
        draw_layer(
            canvas=canvas,
            img_gray=img_gray,
            font_path=font_path,
            font_size=layer["font_size"],
            words=chinese_words,
            step=layer["step"],
            base_alpha=layer["base_alpha"],
            alpha_boost_dark=layer["alpha_boost_dark"],
            density_scale=layer["density_scale"],
            color=layer["color"],
            random_jitter=0.4,
            allow_rotation=layer["allow_rotation"],
        )

    canvas.save(output_path)
    print(f"Saved word-based image to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recreate an image using layered Chinese words with varying size and alpha."
    )
    parser.add_argument(
        "--input",
        default="example.jpg",
        help="Input image path (default: example.jpg in this folder)",
    )
    parser.add_argument(
        "--output",
        default="output.png",
        help="Output image path (PNG recommended, default: output.png)",
    )
    parser.add_argument(
        "--font",
        required=True,
        help="Path to a Chinese-supporting font file (e.g. C:/Windows/Fonts/simhei.ttf)",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=800,
        help="Maximum width of output image (height is scaled).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_word_image(
        input_path=args.input,
        output_path=args.output,
        font_path=args.font,
        max_width=args.max_width,
    )
