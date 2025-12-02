import argparse
import random
from typing import List, Dict, Any, Tuple

from PIL import Image, ImageFilter, ImageDraw

import main as word_main
from generate_variations import get_style_presets


def build_base_image(input_path: str, max_width: int) -> Image.Image:
    """Load and upscale/scale the input image to max_width."""
    img = Image.open(input_path).convert("RGB")
    w, h = img.size
    scale = max_width / float(w)
    img = img.resize((max_width, int(h * scale)), Image.LANCZOS)
    return img


def generate_layer_targets(
    img_gray: Image.Image,
    font_path: str,
    layer: Dict[str, Any],
    words: List[str],
    density_multiplier: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Generate target positions and word settings for a layer
    (without drawing them yet). This mirrors the logic in draw_layer
    but returns a list of glyph descriptions we can animate.
    """
    w, h = img_gray.size
    step = layer["step"]
    font_size = layer["font_size"]
    base_alpha = layer["base_alpha"]
    alpha_boost_dark = layer["alpha_boost_dark"]
    density_scale = layer["density_scale"] * density_multiplier
    color = layer["color"]

    base_font = word_main.load_font(font_path, font_size)

    targets: List[Dict[str, Any]] = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            lum = word_main.sample_region_luminance(img_gray, x, y, step)
            alpha, density = word_main.luminance_to_alpha_and_density(
                lum,
                base_alpha=base_alpha,
                alpha_boost_dark=alpha_boost_dark,
                density_scale=density_scale,
            )

            if random.random() > density:
                continue

            word = word_main.choose_word(words)

            jitter_x = (random.random() - 0.5) * 2 * step * 0.4
            jitter_y = (random.random() - 0.5) * 2 * step * 0.4
            px = x + step / 2 + jitter_x
            py = y + step / 2 + jitter_y

            size_variation = random.uniform(0.9, 1.2)
            fsize = max(6, int(font_size * size_variation))
            font = base_font if fsize == font_size else word_main.load_font(
                font_path, fsize
            )

            bbox = font.getbbox(word)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            targets.append(
                dict(
                    word=word,
                    font=font,
                    width=tw,
                    height=th,
                    target_pos=(px, py),
                    alpha=alpha,
                    color=color,
                )
            )

    return targets


def random_offscreen_start(w: int, h: int) -> Tuple[float, float]:
    """Pick a random starting point just outside the canvas."""
    side = random.choice(["left", "right", "top", "bottom"])
    if side == "left":
        return -w * random.uniform(0.1, 0.5), random.uniform(0, h)
    if side == "right":
        return w * (1 + random.uniform(0.1, 0.5)), random.uniform(0, h)
    if side == "top":
        return random.uniform(0, w), -h * random.uniform(0.1, 0.5)
    # bottom
    return random.uniform(0, w), h * (1 + random.uniform(0.1, 0.5))


def accumulate_layers_animation(
    input_path: str,
    font_path: str,
    output_gif: str,
    max_width: int = 800,
    background=(255, 255, 255),
    frames_per_layer: int = 4,
    final_original_frames: int = 6,
) -> None:
    """
    Build an animation that starts from an empty canvas and gradually adds
    word layers in this order:

        subtle_soft -> graphic_bold -> fade into original

    Each new layer is animated as words 'flying in' from outside the frame
    to their final positions, increasing the total word count over time.
    """
    base_img = build_base_image(input_path, max_width)
    img_gray = base_img.convert("L")
    w, h = img_gray.size

    # This holds all *settled* words from previous layers.
    settled_canvas = Image.new("RGBA", (w, h), background + (255,))

    presets = get_style_presets()
    subtle_layers: List[Dict[str, Any]] = presets["subtle_soft"]
    bold_layers: List[Dict[str, Any]] = presets["graphic_bold"]

    # Only go up to graphic_bold as requested.
    combined_layers: List[Dict[str, Any]] = list(subtle_layers) + list(bold_layers)

    chinese_words = list("天地人和山水风云日月星辰光影黑白虚实梦境文字重叠层次深浅变化")

    frames: List[Image.Image] = []

    for idx, layer in enumerate(combined_layers):
        print(f"Preparing layer {idx + 1}/{len(combined_layers)}...")

        # Generate target glyphs for this layer.
        targets = generate_layer_targets(
            img_gray=img_gray,
            font_path=font_path,
            layer=layer,
            words=chinese_words,
            density_multiplier=1.0,
        )

        # Give each glyph a random off-screen start point.
        for t in targets:
            start_x, start_y = random_offscreen_start(w, h)
            t["start_pos"] = (start_x, start_y)

        # Animate them flying toward their targets.
        for f in range(frames_per_layer):
            t_norm = (f + 1) / float(frames_per_layer)

            # Start from the settled canvas so far.
            frame_rgba = settled_canvas.copy()
            draw = ImageDraw.Draw(frame_rgba)

            for glyph in targets:
                sx, sy = glyph["start_pos"]
                tx, ty = glyph["target_pos"]
                cx = sx + (tx - sx) * t_norm
                cy = sy + (ty - sy) * t_norm

                tw = glyph["width"]
                th = glyph["height"]
                x = int(cx - tw / 2)
                y = int(cy - th / 2)

                r, g, b = glyph["color"]
                a = glyph["alpha"]
                draw.text(
                    (x, y),
                    glyph["word"],
                    font=glyph["font"],
                    fill=(r, g, b, a),
                )

            # Slight blur after compositing to emphasize motion,
            # then convert for GIF.
            blur_radius = 1.2 * (1.0 - t_norm)
            if blur_radius > 0.1:
                frame_rgba = frame_rgba.filter(
                    ImageFilter.GaussianBlur(radius=blur_radius)
                )
            frames.append(frame_rgba.convert("P", palette=Image.ADAPTIVE))

        # After the flight, permanently add this layer's glyphs to the settled canvas.
        settled_draw = ImageDraw.Draw(settled_canvas)
        for glyph in targets:
            tx, ty = glyph["target_pos"]
            tw = glyph["width"]
            th = glyph["height"]
            x = int(tx - tw / 2)
            y = int(ty - th / 2)
            r, g, b = glyph["color"]
            a = glyph["alpha"]
            settled_draw.text(
                (x, y),
                glyph["word"],
                font=glyph["font"],
                fill=(r, g, b, a),
            )

    # Final phase: fade into the original image using blending.
    original_rgba = base_img.convert("RGBA")
    for i in range(final_original_frames):
        alpha = (i + 1) / float(final_original_frames)
        blended = Image.blend(settled_canvas, original_rgba, alpha)
        # Slight blur at the beginning, then sharper.
        blur_radius = max(0.0, 1.5 - 1.5 * alpha)
        if blur_radius > 0:
            blended = blended.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        frames.append(blended.convert("P", palette=Image.ADAPTIVE))

    # Save as GIF animation.
    if not frames:
        print("No frames generated; nothing to save.")
        return

    # Duration is ms per frame; tweak for speed.
    duration_ms = 120
    frames[0].save(
        output_gif,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
    print(f"Saved animation GIF to {output_gif}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an animated GIF that adds word layers over time:\n"
            "subtle_soft -> graphic_bold -> deep_dense -> original, "
            "with a bit of blur at each step."
        )
    )
    parser.add_argument(
        "--input",
        default="example.jpg",
        help="Input image path (default: example.jpg in this folder)",
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
        help="Target width of the animation frames (image is scaled).",
    )
    parser.add_argument(
        "--output-gif",
        default="depth_transition.gif",
        help="Output GIF filename (default: depth_transition.gif)",
    )
    parser.add_argument(
        "--frames-per-layer",
        type=int,
        default=2,
        help="How many frames to emit after each new word layer is added.",
    )
    parser.add_argument(
        "--final-original-frames",
        type=int,
        default=6,
        help="How many frames to use when fading into the original image.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    accumulate_layers_animation(
        input_path=args.input,
        font_path=args.font,
        output_gif=args.output_gif,
        max_width=args.max_width,
        frames_per_layer=args.frames_per_layer,
        final_original_frames=args.final_original_frames,
    )


if __name__ == "__main__":
    main()


