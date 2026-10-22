"""Wykrywanie twarzy modelem YuNet (ONNX) bez OpenCV: wystarczą numpy i onnxruntime.

Model: face_detection_yunet_2023mar.onnx z OpenCV Zoo (licencja MIT, patrz data/YuNet-LICENSE.txt).
Służy do kadrowania: rozmiar i położenie twarzy w Twoim nagraniu pozwalają trafić w proporcje kadrów wzorca.
"""
from __future__ import annotations

import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import media
from .template import DATA_DIR

MODEL = DATA_DIR / "face_detection_yunet_2023mar.onnx"
SIZE = 640  # model ma stałe wejście 640x640; mniejsze kadry wstawiamy w lewy górny róg
STRIDES = (8, 16, 32)


class FacesUnavailable(RuntimeError):
    """Brak numpy/onnxruntime albo pliku modelu."""


@dataclass(frozen=True)
class Face:
    x: float  # prostokąt twarzy jako ułamki kadru
    y: float
    w: float
    h: float
    score: float
    eye_y: float  # wysokość linii oczu (ułamek wysokości kadru)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True)
class FaceEstimate:
    h: float  # wysokość twarzy / wysokość kadru
    cx: float
    cy: float
    eye_y: float
    n: int  # z ilu wykryć
    w: float = 0.0  # szerokość twarzy / szerokość kadru


class FaceDetector:
    def __init__(self, score: float = 0.6, nms: float = 0.3):
        try:
            import numpy as np
            import onnxruntime as ort
        except ImportError as exc:
            raise FacesUnavailable(
                "Do kadrowania po twarzy potrzebne są pakiety numpy i onnxruntime: pip install numpy onnxruntime") from exc
        if not MODEL.exists():
            raise FacesUnavailable(f"Brak pliku modelu twarzy: {MODEL}")
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self._np = np
        self._sess = ort.InferenceSession(str(MODEL), opts, providers=["CPUExecutionProvider"])
        self._names = [o.name for o in self._sess.get_outputs()]
        self.score, self.nms = score, nms

    def detect(self, rgb) -> list[Face]:
        """rgb: tablica HxWx3 uint8, h i w <= 640. Zwraca twarze od największej."""
        np = self._np
        h, w = rgb.shape[:2]
        if h > SIZE or w > SIZE:
            raise ValueError(f"Kadr {w}x{h} jest większy niż {SIZE} px.")
        canvas = np.zeros((SIZE, SIZE, 3), np.float32)
        canvas[:h, :w] = rgb[..., ::-1]  # model oczekuje BGR 0-255
        outs = dict(zip(self._names, self._sess.run(None, {"input": canvas.transpose(2, 0, 1)[None]})))
        return self._decode(outs, w, h)

    def _decode(self, outs: dict, w: int, h: int) -> list[Face]:
        np = self._np
        boxes, scores, kps = [], [], []
        for stride in STRIDES:
            cols = SIZE // stride
            cls = outs[f"cls_{stride}"].reshape(-1)
            obj = outs[f"obj_{stride}"].reshape(-1)
            score = np.sqrt(np.clip(cls, 0, 1) * np.clip(obj, 0, 1))
            idx = np.nonzero(score >= self.score)[0]
            if not len(idx):
                continue
            bbox = outs[f"bbox_{stride}"].reshape(-1, 4)[idx]
            kp = outs[f"kps_{stride}"].reshape(-1, 10)[idx]
            r, c = idx // cols, idx % cols
            cx, cy = (c + bbox[:, 0]) * stride, (r + bbox[:, 1]) * stride
            bw, bh = np.exp(bbox[:, 2]) * stride, np.exp(bbox[:, 3]) * stride
            boxes.append(np.stack([cx - bw / 2, cy - bh / 2, bw, bh], 1))
            scores.append(score[idx])
            ky = (kp[:, 1::2] + r[:, None]) * stride  # y pięciu punktów: oczy, nos, kąciki ust
            kps.append(ky)
        if not boxes:
            return []
        boxes, scores, kps = np.concatenate(boxes), np.concatenate(scores), np.concatenate(kps)
        keep = self._nms_keep(boxes, scores)
        faces = []
        for i in keep:
            x, y, bw, bh = boxes[i]
            eye = float((kps[i][0] + kps[i][1]) / 2) / h
            faces.append(Face(float(x) / w, float(y) / h, float(bw) / w, float(bh) / h, float(scores[i]), eye))
        return sorted(faces, key=lambda f: -f.w * f.h)

    def _nms_keep(self, boxes, scores) -> list[int]:
        np = self._np
        order = np.argsort(-scores)
        x1, y1 = boxes[:, 0], boxes[:, 1]
        x2, y2 = x1 + boxes[:, 2], y1 + boxes[:, 3]
        area = boxes[:, 2] * boxes[:, 3]
        keep: list[int] = []
        while len(order):
            i = int(order[0])
            keep.append(i)
            if len(order) == 1:
                break
            rest = order[1:]
            iw = np.maximum(0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
            ih = np.maximum(0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
            inter = iw * ih
            iou = inter / (area[i] + area[rest] - inter + 1e-9)
            order = rest[iou <= self.nms]
        return keep


def iter_rgb(video: str | Path, *, every_s: float = 0.5, start: float = 0.0, duration: float | None = None):
    """Co every_s sekund daje (czas, klatka HxWx3 uint8) zmniejszoną tak, by dłuższy bok miał SIZE px."""
    try:
        import numpy as np
    except ImportError as exc:
        raise FacesUnavailable("Potrzebny jest pakiet numpy: pip install numpy") from exc
    info = media.probe(video)
    if info.width >= info.height:
        w, h = SIZE, max(2, int(round(info.height * SIZE / info.width / 2)) * 2)
    else:
        w, h = max(2, int(round(info.width * SIZE / info.height / 2)) * 2), SIZE
    cmd = [media.find_binary("ffmpeg"), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(video)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-an", "-vf", f"fps=1/{every_s},scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    size = w * h * 3
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        assert proc.stdout is not None
        i = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield start + i * every_s, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1


def sample_faces(video: str | Path, *, every_s: float = 0.5, start: float = 0.0, duration: float | None = None,
                 detector: FaceDetector | None = None) -> list[tuple[float, Face | None]]:
    """Co every_s sekund wykrywa najwiekszą twarz. Zwraca [(czas, Face albo None)]."""
    det = detector or FaceDetector()
    out: list[tuple[float, Face | None]] = []
    for t, frame in iter_rgb(video, every_s=every_s, start=start, duration=duration):
        found = det.detect(frame)
        out.append((t, found[0] if found else None))
    return out


def estimate(found: Sequence[Face]) -> FaceEstimate | None:
    """Mediana z listy wykryć (None, gdy lista pusta)."""
    return FaceTrack._estimate(found)


class FaceTrack:
    """Wykrycia twarzy w czasie; estymata dla przedziału = mediana wykryć w nim (albo globalna, gdy ich mało)."""

    def __init__(self, samples: Sequence[tuple[float, Face | None]]):
        self.samples = list(samples)

    @staticmethod
    def _estimate(faces: Sequence[Face]) -> FaceEstimate | None:
        if not faces:
            return None
        return FaceEstimate(statistics.median(f.h for f in faces), statistics.median(f.cx for f in faces),
                            statistics.median(f.cy for f in faces), statistics.median(f.eye_y for f in faces), len(faces),
                            statistics.median(f.w for f in faces))

    def detections(self) -> list[Face]:
        return [f for _, f in self.samples if f is not None]

    def global_estimate(self) -> FaceEstimate | None:
        return self._estimate(self.detections())

    def estimate(self, t0: float, t1: float, min_count: int = 3) -> FaceEstimate | None:
        local = [f for t, f in self.samples if f is not None and t0 <= t < t1]
        if len(local) >= min_count:
            return self._estimate(local)
        return self.global_estimate()

    def coverage(self) -> float:
        return len(self.detections()) / len(self.samples) if self.samples else 0.0
