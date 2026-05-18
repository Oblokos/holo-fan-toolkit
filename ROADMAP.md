# Roadmap

## Phase 1: Clean CLI

- [x] Move confirmed encoder into a clean package.
- [x] Include official header and LUT as package data.
- [x] Support static image export.
- [x] Support variable-duration video export.
- [x] Support zoom and offset.
- [x] Keep tests on the Python standard library.
- [ ] Add preview frame export for CLI fit tuning.
- [ ] Add friendlier errors for missing ffmpeg/Pillow.
- [ ] Add real sample assets or documented fixture generation.

## Phase 2: Visual UI

- [x] Load image/video.
- [x] Show circular fan-disc mask.
- [x] Manual zoom, offset, rotation, start, and duration.
- [x] Preview sampled output.
- [x] Export through the same Python encoder.
- [x] Generate browser-compatible animated video previews with ffmpeg fallback.
- [x] Clamp video timing controls from ffprobe metadata.
- [x] Use native save dialog for BIN export when the browser supports it.
- [ ] Add packaged desktop app instructions.
- [ ] Add richer video playback controls.
- [ ] Add export progress for long videos.
- [ ] Cache generated preview clips while tuning fit controls.

## Phase 3: Public Repo

- [ ] Add screenshots/GIFs.
- [ ] Add supported-device warning.
- [ ] Add format notes.
- [ ] Add license.
- [ ] Add release workflow or packaged app instructions.
