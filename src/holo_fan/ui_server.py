import argparse
from email.parser import BytesParser
from email.policy import default
import json
import mimetypes
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from .encoder import build_bin


UI_ROOT = files("holo_fan.ui")


def _field_text(form, name, default=""):
    value = form.get(name)
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode()
    return value


def _field_float(form, name, default):
    value = _field_text(form, name, "")
    if value == "":
        return default
    return float(value)


def _field_int(form, name, default):
    value = _field_text(form, name, "")
    if value == "":
        return default
    return int(value)


def _content_disposition(filename):
    return f'attachment; filename="{filename}"'


class HoloFanUIHandler(BaseHTTPRequestHandler):
    server_version = "HoloFanUI/0.1"

    def do_HEAD(self):
        parsed = urlparse(self.path)
        asset_name, content_type = self._resolve_asset(parsed.path)
        if asset_name is None:
            self.send_error(404, "not found")
            return
        try:
            data = (UI_ROOT / asset_name).read_bytes()
        except FileNotFoundError:
            self.send_error(404, "not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        asset_name, content_type = self._resolve_asset(parsed.path)
        if asset_name is None:
            self.send_error(404, "not found")
        else:
            self._serve_asset(asset_name, content_type)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/export":
            self.send_error(404, "not found")
            return

        try:
            data, filename = self._export_bin()
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", _content_disposition(filename))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def _resolve_asset(self, path):
        if path == "/":
            return "index.html", "text/html; charset=utf-8"
        if path.startswith("/assets/"):
            asset_name = path.removeprefix("/assets/")
            return asset_name, mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
        return None, None

    def _serve_asset(self, asset_name, content_type):
        try:
            data = (UI_ROOT / asset_name).read_bytes()
        except FileNotFoundError:
            self.send_error(404, "not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _export_bin(self):
        form, files = self._parse_multipart()

        media = files.get("media")
        if media is None or not media["filename"]:
            raise ValueError("No media file was uploaded")

        source_name = Path(media["filename"]).name
        suffix = Path(source_name).suffix or ".media"
        media_kind = _field_text(form, "mediaKind", "image")
        output_name = Path(_field_text(form, "outputName", "") or source_name).stem + ".bin"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            media_path = tmp_dir / f"input{suffix}"
            output_path = tmp_dir / output_name
            media_path.write_bytes(media["content"])

            duration = _field_float(form, "duration", 6.0)
            frames = max(1, round(duration * 20))
            args = SimpleNamespace(
                output=output_path,
                image=media_path if media_kind == "image" else None,
                video=media_path if media_kind == "video" else None,
                image_fit="disc",
                video_fit="disc",
                fit_scale=_field_float(form, "fitScale", 1.0),
                offset_x=_field_float(form, "offsetX", 0.0),
                offset_y=_field_float(form, "offsetY", 0.0),
                rotate=_field_float(form, "rotate", 0.0),
                start=_field_float(form, "start", 0.0),
                duration=duration if media_kind == "video" else None,
                pattern="wedges",
                frames=frames,
                width=_field_int(form, "width", 640),
                height=_field_int(form, "height", 640),
                center_x=319.5,
                center_y=319.5,
                audio=None,
                header="official",
                header_file=None,
                padding=_field_text(form, "padding", "official"),
                gamma=None,
                min_brightness=None,
                change_brightness_lights=0,
                brightness=None,
            )
            data = build_bin(args)
        return data, output_name

    def _parse_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Expected multipart form data")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        raw = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
        ).encode() + body
        message = BytesParser(policy=default).parsebytes(raw)
        form = {}
        files = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files[name] = {"filename": filename, "content": payload}
            else:
                charset = part.get_content_charset() or "utf-8"
                form[name] = payload.decode(charset, errors="replace")
        return form, files


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the Holo Fan visual editor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), HoloFanUIHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Holo Fan UI running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
