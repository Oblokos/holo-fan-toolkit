# UI

The visual editor is implemented as package assets under `src/holo_fan/ui` and is served by the Python CLI:

```bash
holo-fan serve-ui
```

Open `http://127.0.0.1:8765` after the server starts.

Current workflow:

1. Load an image or video.
2. Show a circular fan disc overlay.
3. Adjust zoom, offset, rotation, start time, and duration.
4. Preview the sampled disc.
5. Export a `.bin` through the CLI/core encoder.

Implementation notes:

- Video metadata is read through `ffprobe` so the duration slider matches the loaded file.
- If the browser cannot decode the original video, the server generates a short H.264 MP4 preview with ffmpeg.
- The sampled output preview updates from the current preview frame while video plays.
- Export uses the browser save-file dialog when supported, then falls back to a normal download.

The CLI is the source of truth first; the UI should call into the same encoder module.
