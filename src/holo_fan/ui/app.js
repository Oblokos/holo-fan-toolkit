const state = {
  file: null,
  mediaKind: "image",
  image: null,
  url: null,
};

const controls = {
  mediaInput: document.querySelector("#mediaInput"),
  exportButton: document.querySelector("#exportButton"),
  sourceCanvas: document.querySelector("#sourceCanvas"),
  sampleCanvas: document.querySelector("#sampleCanvas"),
  video: document.querySelector("#videoSource"),
  sourceMeta: document.querySelector("#sourceMeta"),
  status: document.querySelector("#status"),
  zoom: document.querySelector("#zoom"),
  offsetX: document.querySelector("#offsetX"),
  offsetY: document.querySelector("#offsetY"),
  rotation: document.querySelector("#rotation"),
  start: document.querySelector("#start"),
  duration: document.querySelector("#duration"),
  padding: document.querySelector("#padding"),
};

const outputs = {
  zoom: document.querySelector("#zoomValue"),
  offsetX: document.querySelector("#offsetXValue"),
  offsetY: document.querySelector("#offsetYValue"),
  rotation: document.querySelector("#rotationValue"),
  start: document.querySelector("#startValue"),
  duration: document.querySelector("#durationValue"),
};

const sourceContext = controls.sourceCanvas.getContext("2d", { willReadFrequently: true });
const sampleContext = controls.sampleCanvas.getContext("2d");
const hiddenCanvas = document.createElement("canvas");
hiddenCanvas.width = 640;
hiddenCanvas.height = 640;
const hiddenContext = hiddenCanvas.getContext("2d", { willReadFrequently: true });

function values() {
  return {
    zoom: Number(controls.zoom.value),
    offsetX: Number(controls.offsetX.value),
    offsetY: Number(controls.offsetY.value),
    rotation: Number(controls.rotation.value),
    start: Number(controls.start.value),
    duration: Number(controls.duration.value),
    padding: controls.padding.value,
  };
}

function syncLabels() {
  const v = values();
  outputs.zoom.value = `${v.zoom.toFixed(2)}x`;
  outputs.offsetX.value = `${v.offsetX}`;
  outputs.offsetY.value = `${v.offsetY}`;
  outputs.rotation.value = `${Math.round(v.rotation)} deg`;
  outputs.start.value = `${v.start.toFixed(1)}s`;
  outputs.duration.value = `${v.duration.toFixed(1)}s`;
}

function clearCanvas(ctx) {
  ctx.clearRect(0, 0, 640, 640);
  ctx.fillStyle = "#101314";
  ctx.fillRect(0, 0, 640, 640);
}

function drawDiscGuides(ctx) {
  ctx.save();
  ctx.translate(320, 320);
  ctx.strokeStyle = "rgba(245, 241, 232, 0.28)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(0, 0, 282, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = "rgba(100, 212, 180, 0.22)";
  ctx.lineWidth = 1;
  for (const radius of [70, 140, 210]) {
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(255, 179, 92, 0.24)";
  for (let i = 0; i < 12; i += 1) {
    const angle = (Math.PI * 2 * i) / 12;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(Math.cos(angle) * 282, Math.sin(angle) * 282);
    ctx.stroke();
  }
  ctx.restore();
}

function currentMediaElement() {
  if (state.mediaKind === "video") {
    return controls.video.readyState >= 2 ? controls.video : null;
  }
  return state.image;
}

function drawSource() {
  const media = currentMediaElement();
  clearCanvas(hiddenContext);
  clearCanvas(sourceContext);

  if (!media) {
    drawDiscGuides(sourceContext);
    drawSample();
    return;
  }

  const v = values();
  const width = media.videoWidth || media.naturalWidth || 1;
  const height = media.videoHeight || media.naturalHeight || 1;
  const base = Math.min(564 / width, 564 / height);
  const scale = base * v.zoom;
  const drawWidth = width * scale;
  const drawHeight = height * scale;

  hiddenContext.save();
  hiddenContext.translate(320 + v.offsetX, 320 + v.offsetY);
  hiddenContext.rotate((v.rotation * Math.PI) / 180);
  hiddenContext.drawImage(media, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
  hiddenContext.restore();

  sourceContext.drawImage(hiddenCanvas, 0, 0);
  sourceContext.save();
  sourceContext.globalCompositeOperation = "destination-in";
  sourceContext.beginPath();
  sourceContext.arc(320, 320, 282, 0, Math.PI * 2);
  sourceContext.fill();
  sourceContext.restore();
  drawDiscGuides(sourceContext);
  drawSample();
}

function drawSample() {
  const frame = hiddenContext.getImageData(0, 0, 640, 640);
  clearCanvas(sampleContext);
  sampleContext.save();
  sampleContext.translate(320, 320);
  sampleContext.lineCap = "round";

  for (let line = 0; line < 300; line += 1) {
    const angle = (Math.PI * 2 * line) / 300;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    for (let led = 0; led < 48; led += 1) {
      const radius = (47 - led) * 6;
      const x = Math.round(320 + radius * cos);
      const y = Math.round(320 + radius * sin);
      const idx = (y * 640 + x) * 4;
      const red = frame.data[idx];
      const green = frame.data[idx + 1];
      const blue = frame.data[idx + 2];
      const alpha = frame.data[idx + 3];
      if (alpha === 0 || (red + green + blue) < 10) {
        continue;
      }
      sampleContext.strokeStyle = `rgb(${red} ${green} ${blue})`;
      sampleContext.lineWidth = led < 6 ? 2 : 1.4;
      sampleContext.beginPath();
      sampleContext.moveTo(cos * Math.max(0, radius - 2), sin * Math.max(0, radius - 2));
      sampleContext.lineTo(cos * (radius + 2), sin * (radius + 2));
      sampleContext.stroke();
    }
  }
  sampleContext.restore();
  drawDiscGuides(sampleContext);
}

function setStatus(text, isError = false) {
  controls.status.textContent = text;
  controls.status.classList.toggle("error", isError);
}

async function loadFile(file) {
  if (state.url) {
    URL.revokeObjectURL(state.url);
  }
  state.file = file;
  state.url = URL.createObjectURL(file);
  state.mediaKind = file.type.startsWith("video/") ? "video" : "image";
  controls.exportButton.disabled = true;
  controls.sourceMeta.textContent = `${file.name} - ${(file.size / 1024 / 1024).toFixed(2)} MB`;

  if (state.mediaKind === "video") {
    state.image = null;
    controls.video.onloadedmetadata = () => {
      controls.start.max = Math.max(0, Math.floor(controls.video.duration || 60));
      controls.video.currentTime = Math.min(values().start, controls.video.duration || values().start);
    };
    controls.video.onloadeddata = () => {
      controls.exportButton.disabled = false;
      setStatus("Video ready. Adjust the frame and export.");
      drawSource();
    };
    controls.video.src = state.url;
    controls.video.load();
  } else {
    controls.video.removeAttribute("src");
    const image = new Image();
    image.onload = () => {
      state.image = image;
      controls.exportButton.disabled = false;
      setStatus("Image ready. Adjust the frame and export.");
      drawSource();
    };
    image.src = state.url;
  }
}

async function exportBin() {
  if (!state.file) {
    return;
  }

  const v = values();
  const form = new FormData();
  form.append("media", state.file);
  form.append("mediaKind", state.mediaKind);
  form.append("outputName", state.file.name);
  form.append("fitScale", v.zoom);
  form.append("offsetX", v.offsetX);
  form.append("offsetY", v.offsetY);
  form.append("rotate", v.rotation);
  form.append("start", v.start);
  form.append("duration", v.duration);
  form.append("padding", v.padding);
  form.append("width", 640);
  form.append("height", 640);

  controls.exportButton.disabled = true;
  setStatus("Encoding BIN...");
  try {
    const response = await fetch("/api/export", { method: "POST", body: form });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Export failed" }));
      throw new Error(error.error || "Export failed");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${state.file.name.replace(/\.[^.]+$/, "")}.bin`;
    link.click();
    URL.revokeObjectURL(url);
    setStatus(`Exported ${(blob.size / 1024).toFixed(1)} KB BIN.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    controls.exportButton.disabled = false;
  }
}

controls.mediaInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) {
    loadFile(file);
  }
});

for (const input of [controls.zoom, controls.offsetX, controls.offsetY, controls.rotation, controls.duration, controls.padding]) {
  input.addEventListener("input", () => {
    syncLabels();
    drawSource();
  });
}

controls.start.addEventListener("input", () => {
  syncLabels();
  if (state.mediaKind === "video" && Number.isFinite(controls.video.duration)) {
    controls.video.currentTime = Math.min(Number(controls.start.value), controls.video.duration);
  }
  drawSource();
});

controls.video.addEventListener("seeked", drawSource);
controls.video.addEventListener("loadeddata", drawSource);
controls.exportButton.addEventListener("click", exportBin);

syncLabels();
clearCanvas(sourceContext);
clearCanvas(sampleContext);
drawDiscGuides(sourceContext);
drawDiscGuides(sampleContext);
