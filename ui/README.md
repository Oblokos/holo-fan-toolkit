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

The CLI is the source of truth first; the UI should call into the same encoder module.
