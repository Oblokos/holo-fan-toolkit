# UI Plan

This directory is reserved for the visual editor.

Planned workflow:

1. Load an image or video.
2. Show a circular fan disc overlay.
3. Adjust zoom, offset, rotation, start time, and duration.
4. Preview the sampled disc.
5. Export a `.bin` through the CLI/core encoder.

The CLI is the source of truth first; the UI should call into the same encoder module.
