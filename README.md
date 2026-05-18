# Holo Fan Toolkit

Tools for generating `.bin` media files for small 48 LED / 300 line holographic fans, including models sold as PD13, F-Mini11, F11, or F-MINI12-like devices.

This repo is the clean implementation extracted from the reverse engineering workspace. It focuses on the confirmed encoder path from the Windows `5D HoLo` software.

## What Works

- Static image to `.bin`
- Video to `.bin`
- Variable duration video
- PCM u8 mono audio at 32000 Hz
- Manual zoom and offset for fitting content into the fan disc
- 180 degree rotation when needed

## Requirements

- Python 3.10+
- ffmpeg available on `PATH` for video input

Install for development:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Encode An Image

```bash
holo-fan encode \
  --output generated/smile.bin \
  --image test_image.png \
  --image-fit disc \
  --rotate 180
```

## Encode A Video

```bash
holo-fan encode \
  --output generated/video.bin \
  --video input.mp4 \
  --video-fit disc \
  --fit-scale 2.0
```

Useful fit options:

```text
--fit-scale 2.0   zoom in
--offset-x 8      move crop window horizontally
--offset-y -4     move crop window vertically
--frames 120      limit output to 120 frames / 6 seconds
```

## Current Device Profile

```text
lights = 48
lines = 300
colorDeep = 5
fps = 20
audio = pcm_u8 mono 32000 Hz
```

The encoder uses the official 5D HoLo header and LUT captured during reverse engineering.

## UI Plan

The `ui/` directory is reserved for the next phase: a visual tool that loads a video, shows a circular fan preview mask, and lets the user adjust scale, offset, rotation, and duration before exporting.
