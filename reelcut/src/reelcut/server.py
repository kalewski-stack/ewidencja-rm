"""Lokalny interfejs w przeglądarce: przeciągnij wideo, kliknij "Potnij", obejrzyj i pobierz rolkę.

Serwer słucha wyłącznie na 127.0.0.1. Pliki nie opuszczają Twojego komputera.
"""
from __future__ import annotations

import json
import mimetypes
import re
import shutil
import threading
import time
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, captions, media
from .pipeline import AUDIO_EXT, VIDEO_EXT, Options, run
from .template import TemplateError, list_templates, resolve_alias

DEFAULT_WORKDIR = Path.home() / "ReelCut"
UI_FILE = Path(__file__).resolve().parent / "data" / "ui.html"
JOB_ID = r"[0-9a-f]{12}"
RUN_LOCK = threading.Lock()  # jedno zadanie na raz: ffmpeg i tak zużywa wszystkie rdzenie

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
PLAN_EXT = {".json", ".txt", ".md"}  # plan grafik (JSON) albo scenariusz ze znacznikami
GRAPHICS_EXT = PLAN_EXT | {".png", ".jpg", ".jpeg", ".webp"}  # plan i obrazy, których używa
MAX_PLAN_BYTES, MAX_IMAGE_BYTES = 2_000_000, 40_000_000


@dataclass
class Job:
    id: str
    dir: Path
    state: str = "new"  # new | queued | running | done | error
    percent: float = 0.0
    label: str = ""
    log: list[str] = field(default_factory=list)
    video: Path | None = None
    broll: list[Path] = field(default_factory=list)
    graphics: Path | None = None  # plan grafik (JSON); obrazy z planu leżą obok
    result: dict | None = None
    error: str | None = None
    served: dict[str, Path] = field(default_factory=dict)

    def add_log(self, msg: str) -> None:
        self.log.append(msg)
        del self.log[:-200]

    def set_progress(self, frac: float, label: str) -> None:
        self.percent, self.label = round(frac * 100, 1), label

    def public(self) -> dict:
        return {"id": self.id, "state": self.state, "percent": self.percent, "label": self.label,
                "log": self.log[-30:], "result": self.result, "error": self.error}


class State:
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.jobs_dir = workdir / "zadania"
        self.out_dir = workdir / "wyniki"
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def new_job(self) -> Job:
        jid = uuid.uuid4().hex[:12]
        d = self.jobs_dir / jid
        d.mkdir(parents=True)
        job = Job(jid, d)
        with self.lock:
            self.jobs[jid] = job
        return job

    def get(self, jid: str) -> Job | None:
        with self.lock:
            return self.jobs.get(jid)


def hostname(host_header: str) -> str:
    """"127.0.0.1:8765" -> "127.0.0.1", "[::1]:8765" -> "[::1]", "localhost" -> "localhost"."""
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


def safe_name(name: str) -> str:
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", Path(name).name).strip(" .")
    return name[:120] or "plik"


def unique_path(folder: Path, name: str) -> Path:
    p = folder / name
    n = 2
    while p.exists():
        p = folder / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    return p


def parse_options(data: dict, job: Job) -> Options:
    def pick(key: str, allowed: set, default):
        v = data.get(key, default)
        if v not in allowed:
            raise ValueError(f"Nieprawidłowa wartość pola {key}: {v!r}")
        return v

    templates = {t for t, _ in list_templates()}
    if isinstance(data.get("template"), str):
        data = {**data, "template": resolve_alias(data["template"])}  # format1 / format2 działają jak pełne nazwy
    try:
        max_zoom = float(data["max_zoom"]) if data.get("max_zoom") not in (None, "", 0) else None
        look = float(data.get("look", 1.0))
    except (TypeError, ValueError):
        raise ValueError("Pola max_zoom i look muszą być liczbami.") from None
    return Options(
        template=pick("template", templates, "rolka_DeuOaXKtPBb"),
        broll=tuple(job.broll),
        graphics=job.graphics,
        captions=pick("captions", {"auto", "on", "off"}, "auto"),
        lang=pick("lang", {"pl", "en", "de", "cs", "uk", "es", "fr", "it", "auto"}, "pl"),
        model=pick("model", {"tiny", "base", "small", "medium", "large-v3"}, "small"),
        emphasis="auto" if data.get("emphasis", True) else "off",
        max_zoom=None if max_zoom is None else min(3.0, max(1.0, max_zoom)),
        tighten=bool(data.get("tighten", True)),
        snap=bool(data.get("snap", True)),
        look=min(1.0, max(0.0, look)),
        framing="auto" if data.get("framing", True) else "off",
    )


def run_job(state: State, job: Job, opts: Options) -> None:
    job.state, job.label = "queued", "W kolejce"
    with RUN_LOCK:
        job.state = "running"
        try:
            out = unique_path(state.out_dir, f"{Path(job.video.name).stem}_rolka.mp4")
            res = run(job.video, out, opts, log=job.add_log, progress=job.set_progress)
            job.served["video"] = res.output
            if res.words_file and res.words_file.exists():
                job.served["words"] = res.words_file
            job.result = {
                "video": res.output.name, "words": res.words_file.name if res.words_file else None,
                "folder": str(res.output.parent), "plan": res.plan_text, "warnings": res.warnings,
                "seconds": round(res.seconds, 1), "input_seconds": round(res.input_seconds, 1),
                "output_seconds": round(res.plan.total_frames / res.plan.fps, 1), "slots": len(res.plan.slots),
                "captions": res.captions_used, "caption_stats": res.caption_stats, "mode": res.plan.mode,
                "face": res.face, "look": res.look, "graphics": res.graphics,
            }
            job.state, job.percent, job.label = "done", 100.0, "Gotowe"
        except (media.MediaError, TemplateError, captions.CaptionsUnavailable, ValueError) as exc:
            job.state, job.error = "error", str(exc)
        except Exception as exc:  # noqa: BLE001: pokazujemy użytkownikowi, co się stało, zamiast wieszać zadanie
            job.add_log(traceback.format_exc())
            job.state, job.error = "error", f"Nieoczekiwany błąd: {exc}"
        finally:
            shutil.rmtree(job.dir, ignore_errors=True)  # wgrane pliki są już niepotrzebne


class Handler(BaseHTTPRequestHandler):
    server_version = "reelcut"
    protocol_version = "HTTP/1.1"
    state: State  # ustawiane w serve()

    def log_message(self, fmt, *args):  # cisza w konsoli
        pass

    # --- pomocnicze ---------------------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8", extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _fail(self, status: int, msg: str):
        self.close_connection = True  # nie wiemy, czy ciało żądania zostało przeczytane
        self._json({"error": msg}, status)

    def _guard(self, mutating: bool) -> bool:
        """Tylko połączenia lokalne (obrona przed DNS rebinding) i, dla zmian, nagłówek, którego obca strona nie ustawi."""
        if hostname(self.headers.get("Host") or "") not in LOCAL_HOSTS:
            self._fail(403, "Dozwolone jest tylko połączenie lokalne.")
            return False
        if mutating and self.headers.get("X-Reelcut") != "1":
            self._fail(403, "Brak nagłówka X-Reelcut.")
            return False
        return True

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("Za duże żądanie.")
        return json.loads(self.rfile.read(n) or b"{}")

    # --- GET ----------------------------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        if not self._guard(False):
            return
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if path == "/api/info":
            try:
                import faster_whisper  # noqa: F401
                has_whisper = True
            except ImportError:
                has_whisper = False
            return self._json({"version": __version__, "whisper": has_whisper, "ffmpeg": media.ffmpeg_summary(),
                               "templates": [{"id": i, "name": n} for i, n in list_templates()],
                               "output_dir": str(self.state.out_dir)})
        m = re.fullmatch(rf"/api/job/({JOB_ID})", path)
        if m:
            job = self.state.get(m.group(1))
            return self._json(job.public()) if job else self._fail(404, "Nie ma takiego zadania.")
        m = re.fullmatch(rf"/files/({JOB_ID})/(video|words)", path)
        if m:
            job = self.state.get(m.group(1))
            f = job.served.get(m.group(2)) if job else None
            return self._serve_file(f) if f and f.exists() else self._fail(404, "Nie ma pliku.")
        self._fail(404, "Nie ma takiej strony.")

    do_HEAD = do_GET  # noqa: N815

    def _serve_file(self, f: Path):
        size = f.stat().st_size
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    return self._send(416, b"", extra={"Content-Range": f"bytes */{size}"})
                end, status = min(end, size - 1), 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if f.suffix == ".json" or self.path.endswith("?download=1"):
            self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(f, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    # --- POST / PUT / DELETE ------------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        if not self._guard(True):
            return
        path = urlparse(self.path).path
        if path == "/api/job":
            self._read_json()
            return self._json({"id": self.state.new_job().id})
        m = re.fullmatch(rf"/api/job/({JOB_ID})/start", path)
        if m:
            job = self.state.get(m.group(1))
            if not job:
                return self._fail(404, "Nie ma takiego zadania.")
            if job.state != "new" or not job.video:
                return self._fail(409, "Najpierw wgraj nagranie (albo zadanie już ruszyło).")
            try:
                opts = parse_options(self._read_json(), job)
            except (ValueError, json.JSONDecodeError) as exc:
                return self._fail(400, str(exc))
            job.state = "queued"
            threading.Thread(target=run_job, args=(self.state, job, opts), daemon=True).start()
            return self._json({"ok": True})
        self._fail(404, "Nie ma takiego adresu.")

    def do_PUT(self):  # noqa: N802
        if not self._guard(True):
            return
        url = urlparse(self.path)
        m = re.fullmatch(rf"/api/job/({JOB_ID})/upload", url.path)
        if not m:
            return self._fail(404, "Nie ma takiego adresu.")
        job = self.state.get(m.group(1))
        if not job or job.state != "new":
            return self._fail(404, "Nie ma takiego zadania albo już ruszyło.")
        q = parse_qs(url.query)
        role, name = (q.get("role") or [""])[0], safe_name((q.get("name") or ["plik"])[0])
        if role not in ("video", "broll", "grafiki"):
            return self._fail(400, "role musi być video, broll albo grafiki.")
        suffix = Path(name).suffix.lower()
        if role == "grafiki":
            if suffix not in GRAPHICS_EXT:
                return self._fail(400, f"Nieobsługiwany typ pliku: {name}. Wgraj plan grafik (.json), scenariusz (.txt, .md) albo obraz (.png, .jpg, .webp).")
        elif suffix not in (VIDEO_EXT | AUDIO_EXT if role == "video" else VIDEO_EXT):
            return self._fail(400, f"Nieobsługiwany typ pliku: {name}. Wgraj nagranie wideo (np. .mp4, .mov)"
                                   f"{' albo nagranie głosu (.m4a, .mp3, .wav) dla trybu motion' if role == 'video' else ''}.")
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._fail(400, "Pusty plik.")
        if role == "grafiki" and length > (MAX_PLAN_BYTES if suffix in PLAN_EXT else MAX_IMAGE_BYTES):
            return self._fail(413, f"Plik {name} jest za duży.")
        updir = job.dir / role
        updir.mkdir(exist_ok=True)
        dest = updir / name if role == "grafiki" else unique_path(updir, name)  # plan odwołuje się do obrazów po nazwie
        left = length
        with open(dest, "wb") as fh:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                fh.write(chunk)
                left -= len(chunk)
        if left:
            dest.unlink(missing_ok=True)
            return self._fail(400, "Wgrywanie przerwane.")
        if role == "video":
            job.video = dest
        elif role == "broll":
            job.broll.append(dest)
        elif suffix in PLAN_EXT:
            job.graphics = dest
        self._json({"ok": True, "name": dest.name, "size": length})

    def do_DELETE(self):  # noqa: N802
        if not self._guard(True):
            return
        m = re.fullmatch(rf"/api/job/({JOB_ID})", urlparse(self.path).path)
        job = self.state.get(m.group(1)) if m else None
        if not job:
            return self._fail(404, "Nie ma takiego zadania.")
        if job.state not in ("running", "queued"):
            shutil.rmtree(job.dir, ignore_errors=True)
            with self.state.lock:
                self.state.jobs.pop(job.id, None)
        self._json({"ok": True})


def serve(port: int = 8765, open_browser: bool = True, workdir: Path | None = None) -> int:
    try:
        media.find_binary("ffmpeg")
        media.find_binary("ffprobe")
    except media.MediaError as exc:
        print(f"BŁĄD: {exc}")
        return 1
    state = State(Path(workdir) if workdir else DEFAULT_WORKDIR)
    Handler.state = state
    httpd = None
    for p in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if httpd is None:
        print(f"BŁĄD: porty {port}-{port + 19} są zajęte. Podaj inny: python rolka.py serve --port 9000")
        return 1
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"reelcut {__version__}: interfejs działa pod adresem {url}")
    print(f"Wyniki zapisują się w: {state.out_dir}")
    print(media.ffmpeg_summary())
    print("Zatrzymanie: Ctrl+C")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        httpd.server_close()
    return 0
