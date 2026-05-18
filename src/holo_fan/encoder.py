#!/usr/bin/env python3
"""
Encoder based on the decompiled 5D HoLo MediaConvert path.

This intentionally does not reuse fan_codec.py's RGB555 experiment. It follows
FUN_14000cb40:
  - sample BGR24 frames with bilinear interpolation
  - apply DAT_140026f50 LUT
  - pack colorDeep bitplanes from bits 7..3, MSB-first
  - append 1600 bytes of PCM u8 audio per frame
"""

import argparse
import math
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path


DATA_ROOT = files("holo_fan.data")
HEADER_HEX = DATA_ROOT / "official_header_5dholo_812.hex"
LUT_HEX = DATA_ROOT / "official_lut_5dholo_256.hex"

BLOCK_SIZE = 28600
VIDEO_SIZE = 27000
AUDIO_SIZE = 1600
LINES = 300
LIGHTS = 48
CHANNELS = 3
COLOR_DEEP = 5
BYTES_PER_BITPLANE = math.ceil(LIGHTS * CHANNELS / 8)
BYTES_PER_LINE = BYTES_PER_BITPLANE * COLOR_DEEP
OFFICIAL_PAD_MULTIPLE = 0x7080
FACTORY_PADDING_SIZE = 100000


def read_hex_bytes(path):
    text = path.read_text()
    values = bytes(int(part, 16) for part in text.split())
    return values


OFFICIAL_HEADER = read_hex_bytes(HEADER_HEX)
OFFICIAL_LUT = read_hex_bytes(LUT_HEX)


def bilinear_bgr(frame, width, height, x, y):
    x0 = int(x)
    y0 = int(y)
    x0 = min(max(x0, 0), width - 1)
    y0 = min(max(y0, 0), height - 1)
    x1 = min(max(int(x) + 1, 0), width - 1)
    y1 = min(max(int(y) + 1, 0), height - 1)

    fx = x - x0
    fy = y - y0
    w00 = (1.0 - fx) * (1.0 - fy)
    w10 = fx * (1.0 - fy)
    w01 = (1.0 - fx) * fy
    w11 = fx * fy

    p00 = (y0 * width + x0) * 3
    p10 = (y0 * width + x1) * 3
    p01 = (y1 * width + x0) * 3
    p11 = (y1 * width + x1) * 3

    return tuple(
        int(
            frame[p00 + channel] * w00
            + frame[p10 + channel] * w10
            + frame[p01 + channel] * w01
            + frame[p11 + channel] * w11
        )
        for channel in range(3)
    )


def apply_brightness(bgr, radius_index, brightness_values=(), gamma=None, min_brightness=None, change_brightness_lights=0):
    if brightness_values and radius_index < len(brightness_values):
        factor = brightness_values[radius_index]
    elif min_brightness is not None and gamma is not None and change_brightness_lights:
        if change_brightness_lights == 1 and radius_index == 0:
            factor = min_brightness
        elif change_brightness_lights > 1 and radius_index < change_brightness_lights:
            factor = (radius_index + 1) / change_brightness_lights
            factor = (factor ** gamma) * (1.0 - min_brightness) + min_brightness
        else:
            return bgr
    else:
        return bgr

    return tuple(min(255, max(0, int(value * factor + 0.5))) for value in bgr)


def pack_line(line_bgr, color_deep=COLOR_DEEP):
    packed = bytearray()
    for plane in range(color_deep):
        source_bit = 7 - plane
        out = bytearray(BYTES_PER_BITPLANE)
        bit_pos = 0
        current = 0
        byte_index = 0

        for bgr in line_bgr:
            for value in bgr:
                if (value >> source_bit) & 1:
                    current |= 1 << (7 - bit_pos)
                if bit_pos < 7:
                    bit_pos += 1
                else:
                    out[byte_index] = current
                    byte_index += 1
                    current = 0
                    bit_pos = 0

        if bit_pos:
            out[byte_index] = current
        packed.extend(out)
    return bytes(packed)


def encode_video_frame(
    frame,
    width,
    height,
    center_x,
    center_y,
    lights=LIGHTS,
    lines=LINES,
    color_deep=COLOR_DEEP,
    brightness_values=(),
    gamma=None,
    min_brightness=None,
    change_brightness_lights=0,
):
    if len(frame) != width * height * 3:
        raise ValueError(f"frame is {len(frame)} bytes, expected {width * height * 3}")

    video = bytearray()
    for line in range(lines):
        angle = math.tau * line / lines
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        line_bgr = []

        for led in range(lights):
            radius_index = lights - led - 1
            x = center_x + radius_index * cos_a
            y = center_y + radius_index * sin_a

            if x < 0.0 or x >= width or y < 0.0 or y >= height:
                bgr = (0, 0, 0)
            else:
                bgr = bilinear_bgr(frame, width, height, x, y)
                bgr = tuple(OFFICIAL_LUT[value] for value in bgr)
                bgr = apply_brightness(
                    bgr,
                    radius_index,
                    brightness_values=brightness_values,
                    gamma=gamma,
                    min_brightness=min_brightness,
                    change_brightness_lights=change_brightness_lights,
                )
            line_bgr.append(bgr)

        video.extend(pack_line(line_bgr, color_deep))

    if len(video) != VIDEO_SIZE:
        raise AssertionError(f"video frame is {len(video)} bytes, expected {VIDEO_SIZE}")
    return bytes(video)


def encode_direct_polar_frame(
    pattern,
    brightness_values=(),
    gamma=None,
    min_brightness=None,
    change_brightness_lights=0,
):
    colors_rgb = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (0, 255, 255),
        (255, 0, 255),
    ]
    video = bytearray()
    for line in range(LINES):
        sector = (line % LINES) // (LINES // 6)
        line_bgr = []
        for led in range(LIGHTS):
            radius_index = LIGHTS - led - 1
            if pattern == "polar-solid-wedges":
                rgb = colors_rgb[sector]
            elif pattern == "polar-separated-wedges":
                within = (line % LINES) % (LINES // 6)
                rgb = (0, 0, 0) if within in (0, 1, 48, 49) else colors_rgb[sector]
            else:
                raise ValueError(f"unknown direct polar pattern: {pattern}")

            bgr = (rgb[2], rgb[1], rgb[0])
            bgr = tuple(OFFICIAL_LUT[value] for value in bgr)
            bgr = apply_brightness(
                bgr,
                radius_index,
                brightness_values=brightness_values,
                gamma=gamma,
                min_brightness=min_brightness,
                change_brightness_lights=change_brightness_lights,
            )
            line_bgr.append(bgr)
        video.extend(pack_line(line_bgr))

    if len(video) != VIDEO_SIZE:
        raise AssertionError(f"video frame is {len(video)} bytes, expected {VIDEO_SIZE}")
    return bytes(video)


def make_pattern_frame(width, height, frame_index, frames, pattern):
    pixels = bytearray(width * height * 3)
    cx = width / 2 - 0.5
    cy = height / 2 - 0.5
    # The official sampler reaches radius LIGHTS-1. Draw a little beyond that
    # radius so bilinear interpolation at the outer LED does not mix with black.
    max_r = LIGHTS + 3

    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            radius = math.hypot(dx, dy)
            theta = (math.atan2(dy, dx) + math.tau) % math.tau
            norm_r = radius / max_r
            base = (y * width + x) * 3

            rgb = (0, 0, 0)
            if norm_r <= 1.0:
                if pattern == "rings":
                    ring = int(norm_r * 10)
                    colors = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
                    rgb = colors[ring % len(colors)] if ring % 2 == 0 else (0, 0, 0)
                elif pattern in ("wedges", "solid-wedges", "soft-wedges"):
                    sector = int(theta / math.tau * 6)
                    colors = [
                        (255, 0, 0),
                        (0, 255, 0),
                        (0, 0, 255),
                        (255, 255, 0),
                        (0, 255, 255),
                        (255, 0, 255),
                    ]
                    if pattern == "soft-wedges":
                        sector_pos = theta / math.tau * 6
                        sector = int(sector_pos) % 6
                        frac = sector_pos - int(sector_pos)
                        edge_width = 0.035
                        rgb = colors[sector]
                        if frac < edge_width:
                            prev_rgb = colors[(sector - 1) % 6]
                            mix = frac / edge_width
                            rgb = tuple(int(prev_rgb[i] * (1 - mix) + rgb[i] * mix) for i in range(3))
                        elif frac > 1 - edge_width:
                            next_rgb = colors[(sector + 1) % 6]
                            mix = (frac - (1 - edge_width)) / edge_width
                            rgb = tuple(int(rgb[i] * (1 - mix) + next_rgb[i] * mix) for i in range(3))
                    elif pattern == "solid-wedges" or int(norm_r * 20) % 4 != 0:
                        rgb = colors[sector]
                elif pattern == "spokes":
                    if int(theta / math.tau * 24) % 4 == 0 or 0.90 < norm_r < 0.97:
                        rgb = (255, 255, 255)
                else:
                    raise ValueError(f"unknown pattern: {pattern}")

            # ffmpeg official intermediate is BGR24.
            pixels[base : base + 3] = bytes((rgb[2], rgb[1], rgb[0]))
    return bytes(pixels)


def load_image_frame(path, width, height, image_fit="resize", rotate_degrees=0, fit_scale=1.0, offset_x=0, offset_y=0):
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("Pillow is required for image input") from exc

    img = Image.open(path).convert("RGB")
    if rotate_degrees:
        img = img.rotate(-rotate_degrees, expand=True)
    if image_fit == "resize":
        img = img.resize((width, height))
    elif image_fit == "disc":
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        diameter = max(1, (LIGHTS - 1) * 2)
        scale = min(diameter / img.width, diameter / img.height) * fit_scale
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        left = int(width / 2 - img.width / 2 + offset_x)
        top = int(height / 2 - img.height / 2 + offset_y)
        canvas.paste(img, (left, top))
        img = canvas
    else:
        raise ValueError(f"unknown image fit mode: {image_fit}")
    rgb = img.tobytes()
    bgr = bytearray(len(rgb))
    for offset in range(0, len(rgb), 3):
        r, g, b = rgb[offset : offset + 3]
        bgr[offset : offset + 3] = bytes((b, g, r))
    return bytes(bgr)


def read_audio_chunks(path, frames):
    if path is None:
        return [b"\x00" * AUDIO_SIZE for _ in range(frames)]

    data = Path(path).read_bytes()
    chunks = []
    for frame in range(frames):
        start = frame * AUDIO_SIZE
        chunk = data[start : start + AUDIO_SIZE]
        if len(chunk) < AUDIO_SIZE:
            chunk = chunk + b"\x00" * (AUDIO_SIZE - len(chunk))
        chunks.append(chunk)
    return chunks


def ffmpeg_video_filter(width, height, fit_mode, fit_scale=1.0, offset_x=0, offset_y=0):
    if fit_mode == "resize":
        return f"scale={width}:{height}:flags=lanczos,fps=20,vflip,format=bgr24"
    if fit_mode == "disc":
        diameter = max(1, (LIGHTS - 1) * 2)
        scaled_box = max(1, round(diameter * fit_scale))
        return (
            f"scale={scaled_box}:{scaled_box}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad=max(iw\\,{diameter}):max(ih\\,{diameter}):(ow-iw)/2:(oh-ih)/2:black,"
            f"crop={diameter}:{diameter}:(iw-{diameter})/2+{offset_x}:(ih-{diameter})/2+{offset_y},"
            "fps=20,vflip,format=bgr24"
        )
    raise ValueError(f"unknown video fit mode: {fit_mode}")


def run_ffmpeg(args_list):
    try:
        subprocess.run(args_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for --video input") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg failed:\n{stderr}") from exc


def load_video_inputs(video_path, width, height, fit_mode, rotate_degrees=0, fit_scale=1.0, offset_x=0, offset_y=0):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        raw_video = tmp_dir / "video.bgr"
        raw_audio = tmp_dir / "audio.pcm"

        vf = ffmpeg_video_filter(width, height, fit_mode, fit_scale, offset_x, offset_y)
        if rotate_degrees:
            if rotate_degrees % 360 == 180:
                vf = "hflip,vflip," + vf
            elif rotate_degrees % 360 == 90:
                vf = "transpose=1," + vf
            elif rotate_degrees % 360 == 270:
                vf = "transpose=2," + vf
            else:
                raise ValueError("--rotate for video currently supports 0, 90, 180, 270")

        run_ffmpeg([
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            vf,
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            str(raw_video),
        ])
        try:
            run_ffmpeg([
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-c:a",
                "pcm_u8",
                "-ar",
                "32000",
                "-ac",
                "1",
                "-f",
                "u8",
                str(raw_audio),
            ])
            audio_data = raw_audio.read_bytes() if raw_audio.exists() else b""
        except RuntimeError:
            audio_data = b""

        frame_width = width if fit_mode == "resize" else max(1, (LIGHTS - 1) * 2)
        frame_height = height if fit_mode == "resize" else max(1, (LIGHTS - 1) * 2)
        frame_size = frame_width * frame_height * 3
        video_data = raw_video.read_bytes()
        if len(video_data) % frame_size:
            raise ValueError(f"raw video size {len(video_data)} is not divisible by frame size {frame_size}")
        frames = [video_data[i : i + frame_size] for i in range(0, len(video_data), frame_size)]

        audio_chunks = []
        for frame_index in range(len(frames)):
            start = frame_index * AUDIO_SIZE
            chunk = audio_data[start : start + AUDIO_SIZE]
            if len(chunk) < AUDIO_SIZE:
                chunk = chunk + b"\x00" * (AUDIO_SIZE - len(chunk))
            audio_chunks.append(chunk)

        return frames, audio_chunks, frame_width, frame_height


def pad_output(output, mode):
    if mode == "none":
        return output
    if mode == "factory":
        output.extend(b"\x00" * FACTORY_PADDING_SIZE)
        return output
    if mode == "official":
        remainder = len(output) % OFFICIAL_PAD_MULTIPLE
        if remainder:
            output.extend(b"\x00" * (OFFICIAL_PAD_MULTIPLE - remainder))
        return output
    raise ValueError(f"unknown padding: {mode}")


def build_bin(args):
    if args.header == "official":
        header = OFFICIAL_HEADER
    else:
        header = Path(args.header_file).read_bytes()

    brightness = tuple(args.brightness or ())
    if getattr(args, "video", None):
        video_frames, audio_chunks, input_width, input_height = load_video_inputs(
            args.video,
            args.width,
            args.height,
            args.video_fit,
            args.rotate,
            args.fit_scale,
            args.offset_x,
            args.offset_y,
        )
        if args.frames is not None:
            video_frames = video_frames[: args.frames]
            audio_chunks = audio_chunks[: args.frames]
        frame_count = len(video_frames)
        center_x = input_width / 2 - 0.5
        center_y = input_height / 2 - 0.5
    else:
        frame_count = args.frames if args.frames is not None else 120
        audio_chunks = read_audio_chunks(args.audio, frame_count)
        video_frames = None
        input_width = args.width
        input_height = args.height
        center_x = args.center_x
        center_y = args.center_y
    output = bytearray(header)

    build_bin.frame_count = frame_count

    for frame_index in range(frame_count):
        if args.pattern.startswith("polar-"):
            video = encode_direct_polar_frame(
                args.pattern,
                brightness_values=brightness,
                gamma=args.gamma,
                min_brightness=args.min_brightness,
                change_brightness_lights=args.change_brightness_lights,
            )
            output.extend(video)
            output.extend(audio_chunks[frame_index])
            continue

        if video_frames is not None:
            bgr = video_frames[frame_index]
        elif args.image:
            bgr = load_image_frame(
                args.image,
                args.width,
                args.height,
                args.image_fit,
                args.rotate,
                args.fit_scale,
                args.offset_x,
                args.offset_y,
            )
        else:
            bgr = make_pattern_frame(args.width, args.height, frame_index, frame_count, args.pattern)
        video = encode_video_frame(
            bgr,
            input_width,
            input_height,
            center_x,
            center_y,
            brightness_values=brightness,
            gamma=args.gamma,
            min_brightness=args.min_brightness,
            change_brightness_lights=args.change_brightness_lights,
        )
        output.extend(video)
        output.extend(audio_chunks[frame_index])

    pad_output(output, args.padding)
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description="Encode .bin files using the decompiled 5D HoLo algorithm")
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--image", type=Path, help="single image to encode repeatedly")
    parser.add_argument("--video", type=Path, help="video to encode at 20 fps with PCM u8 32000Hz audio")
    parser.add_argument("--image-fit", choices=["resize", "disc"], default="resize")
    parser.add_argument("--video-fit", choices=["resize", "disc"], default="disc")
    parser.add_argument("--fit-scale", type=float, default=1.0, help="zoom for image/video disc fit; >1 crops closer")
    parser.add_argument("--offset-x", type=float, default=0, help="horizontal fit offset in sampled pixels")
    parser.add_argument("--offset-y", type=float, default=0, help="vertical fit offset in sampled pixels")
    parser.add_argument("--rotate", type=float, default=0, help="clockwise image rotation before encoding")
    parser.add_argument(
        "--pattern",
        choices=[
            "rings",
            "wedges",
            "solid-wedges",
            "soft-wedges",
            "spokes",
            "polar-solid-wedges",
            "polar-separated-wedges",
        ],
        default="wedges",
    )
    parser.add_argument("--frames", type=int, help="frame limit; defaults to all video frames or 120 for image/pattern")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--center-x", type=float, default=319.5)
    parser.add_argument("--center-y", type=float, default=319.5)
    parser.add_argument("--audio", type=Path, help="optional raw pcm_u8 mono 32000Hz")
    parser.add_argument("--header", choices=["official", "file"], default="official")
    parser.add_argument("--header-file", type=Path, help="raw header bytes when --header=file")
    parser.add_argument("--padding", choices=["official", "factory", "none"], default="official")
    parser.add_argument("--gamma", type=float)
    parser.add_argument("--min-brightness", type=float)
    parser.add_argument("--change-brightness-lights", type=int, default=0)
    parser.add_argument("--brightness", type=float, nargs="*", help="per-radius brightness values, center outward")
    args = parser.parse_args()

    if args.frames is not None and args.frames < 1:
        raise ValueError("--frames must be positive")
    if args.fit_scale <= 0:
        raise ValueError("--fit-scale must be positive")
    if args.header == "file" and not args.header_file:
        raise ValueError("--header-file is required when --header=file")
    if args.image and args.video:
        raise ValueError("--image and --video are mutually exclusive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = build_bin(args)
    args.output.write_bytes(data)
    print(f"Wrote {args.output} ({len(data)} bytes)")
    print(f"Header: {len(OFFICIAL_HEADER) if args.header == 'official' else args.header_file.stat().st_size} bytes")
    print(f"Payload: {build_bin.frame_count} * {BLOCK_SIZE} bytes ({build_bin.frame_count / 20:.2f}s @ 20 fps)")
    print(f"Padding: {args.padding}")


if __name__ == "__main__":
    main()
