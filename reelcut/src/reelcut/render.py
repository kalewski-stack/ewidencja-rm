"""Renderer: master (skrócone pauzy), złożenie ujęć wg planu, dźwięk, kodowanie."""
from __future__ import annotations

import json
import random
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from . import media
from .media import MediaError, MediaInfo, ProgressCb
from .planner import Plan, Slot

FADE_S = 0.006  # krótkie wyciszenie na łączeniach, żeby nie trzaskało


def _even(v: float) -> int:
    return max(2, int(round(v / 2.0)) * 2)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class Geometry:
    crop: tuple[int, int, int, int]  # szer, wys, x, y wycinka ze źródła w proporcji kanwy
    size: tuple[int, int]  # rozmiar mastera


def master_geometry(src_w: int, src_h: int, canvas: tuple[int, int], focus_x: float = 0.5,
                    cap: tuple[int, int] | None = None) -> Geometry:
    """Wycina ze źródła kadr w proporcji kanwy (9:16 albo 16:9) i ogranicza rozmiar mastera (domyślnie 1620x2880, a przy kanwie poziomej 2880x1620)."""
    ar = canvas[0] / canvas[1]
    if cap is None:
        cap = (1620, 2880) if ar <= 1.0 else (2880, 1620)
    if src_w / src_h >= ar:
        ch = src_h
        cw = int(round(ch * ar))
    else:
        cw = src_w
        ch = int(round(cw / ar))
    cw, ch = cw - cw % 2, ch - ch % 2
    x = int(_clamp(round(focus_x * src_w - cw / 2), 0, src_w - cw))
    y = (src_h - ch) // 2
    k = min(1.0, cap[0] / cw, cap[1] / ch)
    return Geometry((cw, ch, x - x % 2, y - y % 2), (_even(cw * k), _even(ch * k)))


# ----------------------------------------------------------------------------------------------
# Master: obraz 25 kl./s w kadrze 9:16 + dźwięk bez długich pauz
# ----------------------------------------------------------------------------------------------

def build_master(src: str | Path, info: MediaInfo, keep: Sequence[tuple[int, int]], geom: Geometry, out: Path,
                 workdir: Path, fps: int, on_progress: ProgressCb | None = None) -> None:
    cw, ch, cx, cy = geom.crop
    mw, mh = geom.size
    n = len(keep)
    audio = info.has_audio
    parts = [f"[0:v]fps={fps},crop={cw}:{ch}:{cx}:{cy},scale={mw}:{mh}:flags=lanczos,setsar=1,format=yuv420p"
             + (f",split={n}" + "".join(f"[v{i}]" for i in range(n)) if n > 1 else "[vs]")]
    if audio:
        parts.append("[0:a]aresample=48000,aformat=channel_layouts=stereo"
                     + (f",asplit={n}" + "".join(f"[a{i}]" for i in range(n)) if n > 1 else "[as]"))
    labels = []
    for i, (a, b) in enumerate(keep):
        vin = f"[v{i}]" if n > 1 else "[vs]"
        parts.append(f"{vin}trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[tv{i}]")
        labels.append(f"[tv{i}]")
        if audio:
            ain = f"[a{i}]" if n > 1 else "[as]"
            dur = (b - a) / fps
            chain = f"atrim=start={a / fps:.6f}:end={b / fps:.6f},asetpts=PTS-STARTPTS"
            if i > 0:
                chain += f",afade=t=in:d={FADE_S}"
            if i < n - 1 and dur > 2 * FADE_S:
                chain += f",afade=t=out:st={dur - FADE_S:.6f}:d={FADE_S}"
            parts.append(f"{ain}{chain}[ta{i}]")
            labels.append(f"[ta{i}]")
    parts.append("".join(labels) + f"concat=n={n}:v=1:a={1 if audio else 0}[vm]" + ("[am]" if audio else ""))
    total_s = sum(b - a for a, b in keep) / fps
    args = ["-i", str(src), *media.filter_script_args(";\n".join(parts), workdir, "graph_master"),
            "-map", "[vm]", *(["-map", "[am]"] if audio else ["-an"]),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(fps),
            *(["-c:a", "pcm_s16le"] if audio else []), str(out)]
    media.run_ffmpeg(args, total_s=total_s, on_progress=on_progress, cwd=workdir)


def build_master_audio(src: str | Path, keep: Sequence[tuple[int, int]], canvas: tuple[int, int], out: Path, workdir: Path,
                       fps: int, on_progress: ProgressCb | None = None, bg: str = "0xF7F4EC") -> None:
    """Master trybu motion: jednolity obraz w kolorze tła (grafiki rysują całą resztę) i dźwięk z pliku bez długich pauz.
    Obraz z pliku źródłowego jest pomijany, więc źródłem może być samo nagranie głosu."""
    n = len(keep)
    parts = ["[0:a]aresample=48000,aformat=channel_layouts=stereo"
             + (f",asplit={n}" + "".join(f"[a{i}]" for i in range(n)) if n > 1 else "[as]")]
    labels = []
    for i, (a, b) in enumerate(keep):
        ain = f"[a{i}]" if n > 1 else "[as]"
        dur = (b - a) / fps
        chain = f"atrim=start={a / fps:.6f}:end={b / fps:.6f},asetpts=PTS-STARTPTS"
        if i > 0:
            chain += f",afade=t=in:d={FADE_S}"
        if i < n - 1 and dur > 2 * FADE_S:
            chain += f",afade=t=out:st={dur - FADE_S:.6f}:d={FADE_S}"
        parts.append(f"{ain}{chain}[ta{i}]")
        labels.append(f"[ta{i}]")
    parts.append("".join(labels) + f"concat=n={n}:v=0:a=1[am]")
    total_s = sum(b - a for a, b in keep) / fps
    W, H = canvas
    args = ["-i", str(src), "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={fps}:d={total_s:.3f}",
            *media.filter_script_args(";\n".join(parts), workdir, "graph_master"),
            "-map", "1:v", "-map", "[am]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "pcm_s16le", "-t", f"{total_s:.3f}", str(out)]
    media.run_ffmpeg(args, total_s=total_s, on_progress=on_progress, cwd=workdir)


# ----------------------------------------------------------------------------------------------
# B-roll
# ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BrollPick:
    path: str
    start: float


def assign_broll(slots: Sequence[Slot], clips: Sequence[MediaInfo], fps: int, seed: int = 7) -> dict[int, BrollPick]:
    """Przydziela klipy B-roll ujęciom typu B: bez powtórek, dopóki starcza klipów, w stałej (losowej) kolejności."""
    rng = random.Random(seed)
    pool: list[MediaInfo] = []
    picks: dict[int, BrollPick] = {}
    for s in slots:
        if s.source != "B":
            continue
        need = s.frames / fps + 0.1
        if not pool:
            pool = list(clips)
            rng.shuffle(pool)
        fit = [c for c in pool if c.duration >= need]
        clip = fit[0] if fit else max(pool, key=lambda c: c.duration)
        pool.remove(clip)
        slack = max(0.0, clip.duration - need)
        picks[s.index] = BrollPick(clip.path, round(rng.uniform(0.0, slack), 3))
    return picks


# ----------------------------------------------------------------------------------------------
# Złożenie wideo
# ----------------------------------------------------------------------------------------------

def _slot_chain(slot: Slot, master_size: tuple[int, int], canvas: tuple[int, int], fps: int) -> str:
    """Filtry kadrujące ujęcie z mastera (zoom wokół punktu uwagi), do rozmiaru kanwy."""
    mw, mh = master_size
    W, H = canvas
    chain = [f"trim=start_frame={slot.start}:end_frame={slot.end}", "setpts=PTS-STARTPTS"]
    if slot.zoom > 1.001:
        cw = _even(mw / slot.zoom)
        ch = _even(cw * mh / mw)
        x = int(_clamp(round(slot.fx * mw - cw / 2), 0, mw - cw))
        y = int(_clamp(round(slot.fy * mh - ch / 2), 0, mh - ch))
        chain.append(f"crop={cw}:{ch}:{x - x % 2}:{y - y % 2}")
    if (mw, mh) != (W, H) or slot.zoom > 1.001:
        chain.append(f"scale={W}:{H}:flags=lanczos")
    chain.append("setsar=1")
    return ",".join(chain)


def matte_chain(slot: Slot, master_size: tuple[int, int]) -> str:
    """Kadrowanie jak w montażu (samo przycięcie do zoomu ujęcia, bez skalowania), żeby sylwetka pasowała do obrazu wyniku."""
    mw, mh = master_size
    if slot.zoom <= 1.001:
        return "null"
    cw = _even(mw / slot.zoom)
    ch = _even(cw * mh / mw)
    x = int(_clamp(round(slot.fx * mw - cw / 2), 0, mw - cw))
    y = int(_clamp(round(slot.fy * mh - ch / 2), 0, mh - ch))
    return f"crop={cw}:{ch}:{x - x % 2}:{y - y % 2}"


def effects_chain(src: str, effects: Sequence[dict], dst: str) -> list[str]:
    """Rozmycie (z lekkim przyciemnieniem) całego obrazu w oknach czasu: kopia rozmyta wchodzi i znika płynnie."""
    parts, cur = [], src
    for k, fx in enumerate(effects):
        a, d, ramp = float(fx["at"]), float(fx["dur"]), min(float(fx.get("ramp", 0.4)), float(fx["dur"]) / 2)
        sigma, dim = float(fx.get("sigma", 14)), float(fx.get("dim", 0.25))
        nxt = dst if k == len(effects) - 1 else f"[fx{k}]"
        parts.append(f"{cur}split[fa{k}][fb{k}]")
        parts.append(f"[fb{k}]gblur=sigma={sigma:g}:steps=2,eq=brightness={-dim * 0.5:.3f},format=yuva420p,"
                     f"fade=t=in:st={a:.3f}:d={ramp:.3f}:alpha=1,fade=t=out:st={a + d - ramp:.3f}:d={ramp:.3f}:alpha=1[fc{k}]")
        parts.append(f"[fa{k}][fc{k}]overlay=format=yuv420,format=yuv420p{nxt}")
        cur = nxt
    return parts


def build_final_graph(plan: Plan, master_size: tuple[int, int], canvas: tuple[int, int],
                      picks: dict[int, BrollPick], input_index: dict[int, int], *, look_chain: str | None,
                      ass_file: str | None, fonts_dir: str | None, graphics_input: int | None = None,
                      effects: Sequence[dict] = ()) -> str:
    fps, W, H = plan.fps, *canvas
    a_slots = [s for s in plan.slots if s.source == "A"]
    parts: list[str] = []
    if len(a_slots) > 1:
        parts.append("[0:v]format=yuv420p,split=" + str(len(a_slots)) + "".join(f"[m{s.index}]" for s in a_slots))
    elif a_slots:
        parts.append(f"[0:v]format=yuv420p[m{a_slots[0].index}]")
    labels = []
    for s in plan.slots:
        fx = next((f for f in s.effects if f.type == "blur_in"), None)
        bw = any(f.type == "bw" for f in s.effects)  # czarno-biały hak: nagranie bez koloru (grafiki kładą się na nim w kolorach marki)
        final = f"[s{s.index}]"
        raw = f"[b{s.index}]" if (fx or bw) else final  # wyjście ze źródła; dalej ewentualne odbarwienie i wejście z rozmycia
        if s.source == "S":  # karta: jednolity kolor, a tekst i obwódkę rysuje warstwa grafik
            parts.append(f"color=c=0x{s.slide_rgb.lstrip('#')}:s={W}x{H}:r={fps},format=yuv420p,setsar=1,"
                         f"trim=end_frame={s.frames},setpts=PTS-STARTPTS{raw}")
        elif s.source == "A":
            parts.append(f"[m{s.index}]{_slot_chain(s, master_size, canvas, fps)}{raw}")
        else:
            j = input_index[s.index]
            parts.append(
                f"[{j}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H},setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=3,"
                f"trim=end_frame={s.frames},setpts=PTS-STARTPTS{raw}")
        if bw:  # rozmycie (jeśli jest) liczy się na obrazie już bez koloru
            nxt = f"[w{s.index}]" if fx else final
            parts.append(f"{raw}hue=s=0,format=yuv420p{nxt}")
            raw = nxt
        if fx:  # wejście z rozmycia (focus-pull): rozmyta kopia znika w czasie fx.dur
            d = min(fx.dur, 0.4 * s.frames / fps)
            i = s.index
            parts.append(f"{raw}split[ba{i}][bb{i}]")
            parts.append(f"[bb{i}]gblur=sigma=26:steps=2,format=yuva420p,fade=t=out:st=0:d={d:.3f}:alpha=1[bc{i}]")
            parts.append(f"[ba{i}]format=yuv420p[bd{i}]")
            parts.append(f"[bd{i}][bc{i}]overlay=format=yuv420,format=yuv420p{final}")
        labels.append(final)
    head = [look_chain] if look_chain else []
    tail = []
    if ass_file:
        tail.append(f"ass={ass_file}" + (f":fontsdir={fonts_dir}" if fonts_dir else ""))
    tail.append("format=yuv420p")
    if not effects and graphics_input is None:
        parts.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0," + ",".join(head + tail) + "[vout]")
        return ";\n".join(parts)
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0," + ",".join(head + ["format=yuv420p"]) + "[vc]")
    cur = "[vc]"
    if effects:
        nxt = "[vfx]"
        parts += effects_chain(cur, effects, nxt)
        cur = nxt
    if graphics_input is not None:  # warstwa grafik RGBA nakładana po korekcji kolorów, żeby kolory marki zostały dokładne
        parts.append(f"[{graphics_input}:v]format=rgba,scale=out_color_matrix=bt709:out_range=tv,format=yuva420p[gl]")
        parts.append(f"{cur}[gl]overlay=0:0:format=yuv420:eof_action=pass,format=yuv420p[vg]")
        cur = "[vg]"
    parts.append(f"{cur}{','.join(tail)}[vout]")
    return ";\n".join(parts)


def measure_loudness(path: Path, lufs: float, tp: float, lra: float) -> dict | None:
    cmd = [media.find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-vn",
           "-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    if res.returncode != 0 or not m:
        return None
    try:
        data = json.loads(m.group(0))
        if float(data["input_i"]) < -60:
            return None  # praktycznie cisza: nie ma czego normalizować
        return data
    except (ValueError, KeyError):
        return None


def audio_filter(master: Path, lufs: float, tp: float, lra: float) -> str:
    m = measure_loudness(master, lufs, tp, lra)
    if not m:
        return "aresample=48000"
    return (f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
            f":linear=true,aresample=48000")


def render_final(master: Path, master_info: MediaInfo, master_size: tuple[int, int], plan: Plan,
                 picks: dict[int, BrollPick], out: Path, workdir: Path, *, canvas: tuple[int, int],
                 look_chain: str | None = None, ass_file: str | None = None, fonts_dir: str | None = None,
                 normalize: bool = True, lufs: float = -14.0, tp: float = -1.0, lra: float = 11.0,
                 crf: int = 18, preset: str = "medium", on_progress: ProgressCb | None = None,
                 graphics_frames: Iterable[bytes] | None = None, effects: Sequence[dict] = ()) -> None:
    inputs = ["-i", str(master)]
    input_index: dict[int, int] = {}
    for s in plan.slots:
        if s.source == "B":
            pick = picks[s.index]
            input_index[s.index] = 1 + len(input_index)
            inputs += ["-ss", f"{pick.start:.3f}", "-t", f"{s.frames / plan.fps + 0.2:.3f}", "-i", pick.path]
    graphics_input = None
    if graphics_frames is not None:  # warstwa grafik: surowe klatki RGBA z naszego strumienia (stdin ffmpeg)
        graphics_input = 1 + len(input_index)
        inputs += ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{canvas[0]}x{canvas[1]}", "-framerate", str(plan.fps), "-i", "pipe:0"]
    graph = build_final_graph(plan, master_size, canvas, picks, input_index, look_chain=look_chain,
                              ass_file=ass_file, fonts_dir=fonts_dir, graphics_input=graphics_input, effects=effects)
    total_s = plan.total_frames / plan.fps
    has_audio = master_info.has_audio
    args = [*inputs, *media.filter_script_args(graph, workdir, "graph_final"), "-map", "[vout]"]
    if has_audio:
        af = audio_filter(master, lufs, tp, lra) if normalize else "aresample=48000"
        args += ["-map", "0:a:0", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        args += ["-an"]
    if look_chain or graphics_input is not None:  # po obróbce w RGB kodujemy w BT.709 i tak oznaczamy plik, żeby odtwarzacze pokazały dokładnie te kolory
        args += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    args += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-r", str(plan.fps), "-movflags", "+faststart", "-t", f"{total_s:.3f}", str(out)]
    media.run_ffmpeg(args, total_s=total_s, on_progress=on_progress, cwd=workdir, stdin_frames=graphics_frames)
