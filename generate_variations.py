import argparse
import os
from typing import List, Dict, Any, Optional

from PIL import Image, ImageDraw, ImageFont

import main as word_main


def render_with_layers(
    input_path: str,
    output_path: str,
    font_path: str,
    layers: List[Dict[str, Any]],
    max_width: int = 800,
    background=(255, 255, 255),
    words: str = "天地人和山水风云日月星辰光影黑白虚实梦境文字重叠层次深浅变化",
) -> None:
    """Render a single variant with a custom layer configuration."""
    img = Image.open(input_path).convert("RGB")
    w, h = img.size
    # Always scale to max_width so variants can be larger than the source
    # and show more word detail.
    scale = max_width / float(w)
    img = img.resize((max_width, int(h * scale)), Image.LANCZOS)

    img_gray = img.convert("L")
    w, h = img_gray.size

    canvas = Image.new("RGBA", (w, h), background + (255,))
    chinese_words = list(words)

    for layer in layers:
        word_main.draw_layer(
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
            random_jitter=layer.get("random_jitter", 0.4),
            allow_rotation=layer.get("allow_rotation", False),
        )

    canvas.save(output_path)
    print(f"Saved variant to {output_path}")


def get_style_presets() -> Dict[str, List[Dict[str, Any]]]:
    """Define multiple visual 'depth' styles via layer presets."""
    return {
        # Softer, more photographic, less noisy.
        "subtle_soft": [
            dict(font_size=52, step=56, base_alpha=20, alpha_boost_dark=130, density_scale=0.5, color=(0, 0, 0)),
            dict(font_size=30, step=32, base_alpha=30, alpha_boost_dark=140, density_scale=0.9, color=(0, 0, 0)),
            dict(font_size=18, step=18, base_alpha=40, alpha_boost_dark=150, density_scale=1.2, color=(0, 0, 0)),
        ],
        # Strong contrast, very visible characters, graphic poster look.
        "graphic_bold": [
            dict(font_size=64, step=60, base_alpha=40, alpha_boost_dark=200, density_scale=0.8, color=(0, 0, 0)),
            dict(font_size=32, step=30, base_alpha=60, alpha_boost_dark=190, density_scale=1.6, color=(0, 0, 0)),
            dict(font_size=16, step=14, base_alpha=70, alpha_boost_dark=190, density_scale=1.8, color=(0, 0, 0)),
        ],
        # Very dense in dark areas, almost engraved look.
        "deep_dense": [
            dict(font_size=40, step=40, base_alpha=25, alpha_boost_dark=210, density_scale=1.0, color=(0, 0, 0)),
            dict(font_size=26, step=22, base_alpha=40, alpha_boost_dark=210, density_scale=1.8, color=(0, 0, 0)),
            dict(font_size=14, step=10, base_alpha=50, alpha_boost_dark=210, density_scale=2.2, color=(0, 0, 0)),
        ],
        # Sparse, airy, more abstract impression of the image.
        "minimal_airy": [
            dict(font_size=60, step=70, base_alpha=15, alpha_boost_dark=120, density_scale=0.4, color=(0, 0, 0)),
            dict(font_size=32, step=46, base_alpha=20, alpha_boost_dark=130, density_scale=0.6, color=(0, 0, 0)),
            dict(font_size=18, step=30, base_alpha=25, alpha_boost_dark=140, density_scale=0.8, color=(0, 0, 0)),
        ],
    }


def stitch_side_by_side(
    image_paths: List[str],
    output_path: str,
    labels: Optional[List[str]] = None,
) -> None:
    """
    Combine multiple images horizontally for comparison.

    If labels are provided, they are drawn under each image to make
    the differences more understandable when viewed together.
    """
    images = [Image.open(p).convert("RGBA") for p in image_paths]
    if not images:
        return

    heights = [im.height for im in images]
    max_height = max(heights)
    total_width = sum(im.width for im in images)

    # Extra space at the bottom for labels (if any).
    label_height = 0
    if labels:
        label_height = 40

    canvas_height = max_height + label_height
    canvas = Image.new("RGBA", (total_width, canvas_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    font = ImageFont.load_default()

    x_offset = 0
    for idx, im in enumerate(images):
        y_offset = (max_height - im.height) // 2
        canvas.alpha_composite(im, dest=(x_offset, y_offset))

        # Optional label under each panel.
        if labels and idx < len(labels):
            label = labels[idx]
            # Measure text using textbbox (modern Pillow)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = x_offset + (im.width - tw) // 2
            ty = max_height + (label_height - th) // 2
            draw.text((tx, ty), label, fill=(0, 0, 0, 255), font=font)

        x_offset += im.width

    canvas.save(output_path)
    print(f"Saved comparison image to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate multiple 'depth look' variations (subtle, graphic, dense, minimal) "
            "and stitch them side by side for comparison."
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
        help="Maximum width of each variant image (height is scaled).",
    )
    parser.add_argument(
        "--out-dir",
        default="variations",
        help="Directory to store the generated variant images.",
    )
    parser.add_argument(
        "--styles",
        nargs="*",
        default=["subtle_soft", "graphic_bold", "deep_dense", "minimal_airy"],
        help="List of style names to generate. Defaults to all presets.",
    )
    parser.add_argument(
        "--comparison-output",
        default="comparison.png",
        help="Filename for the stitched comparison image.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    presets = get_style_presets()

    # Filter to only known styles
    selected_styles = [s for s in args.styles if s in presets]
    if not selected_styles:
        raise SystemExit(
            f"No valid styles requested. Available styles: {', '.join(presets.keys())}"
        )

    os.makedirs(args.out_dir, exist_ok=True)

    variant_paths: List[str] = []
    for style_name in selected_styles:
        style_layers = presets[style_name]
        out_path = os.path.join(args.out_dir, f"{style_name}.png")
        print(f"Rendering style '{style_name}'...")
        render_with_layers(
            input_path=args.input,
            output_path=out_path,
            font_path=args.font,
            layers=style_layers,
            max_width=args.max_width,
        )
        variant_paths.append(out_path)

    # 1) "Evaluation sheet": original + key styles side by side with labels.
    #    This tends to read more like a progression / evaluation than single images.
    key_order = ["subtle_soft", "graphic_bold", "deep_dense"]
    key_styles = [s for s in key_order if s in selected_styles]

    if key_styles:
        # Save a resized version of the original for direct comparison.
        original = Image.open(args.input).convert("RGB")
        ow, oh = original.size
        if ow > args.max_width:
            scale = args.max_width / float(ow)
            original = original.resize((args.max_width, int(oh * scale)), Image.LANCZOS)
        original_rgba = original.convert("RGBA")
        original_path = os.path.join(args.out_dir, "original.png")
        original_rgba.save(original_path)

        eval_paths = [original_path]
        eval_labels = ["original"]
        for style_name in key_styles:
            eval_paths.append(os.path.join(args.out_dir, f"{style_name}.png"))
            eval_labels.append(style_name)

        evaluation_path = os.path.join(args.out_dir, "evaluation.png")
        stitch_side_by_side(eval_paths, evaluation_path, labels=eval_labels)

        # 2) Standard comparison strip, but with the evaluation sheet
        #    placed at the 4th spot (instead of a 4th separate style),
        #    to emphasise the progression you liked.
        comparison_path = os.path.join(args.out_dir, args.comparison_output)
        comp_paths = []
        comp_labels = []

        # Use first three selected styles as-is.
        for style_name in selected_styles[:3]:
            comp_paths.append(os.path.join(args.out_dir, f"{style_name}.png"))
            comp_labels.append(style_name)

        # Put evaluation sheet as the 4th panel.
        comp_paths.append(evaluation_path)
        comp_labels.append("evaluation")

        stitch_side_by_side(comp_paths, comparison_path, labels=comp_labels)
    else:
        # Fallback: if no key styles, just compare selected styles directly.
        comparison_path = os.path.join(args.out_dir, args.comparison_output)
        stitch_side_by_side(variant_paths, comparison_path, labels=selected_styles)


if __name__ == "__main__":
    main()


