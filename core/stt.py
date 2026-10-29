"""Speech-to-text: faster-whisper -> openai-whisper -> SpeechEngineUnavailable."""
from __future__ import annotations

import io
import math
import os
import sys
import tempfile
import wave
from array import array
from functools import lru_cache
from typing import Any, Callable

from core import config

try:  # cache the heavy model across Streamlit reruns
    import streamlit as st
    _cache_resource = st.cache_resource(show_spinner=False)
except Exception:  # pragma: no cover - running without Streamlit
    _cache_resource = lru_cache(maxsize=2)


class SpeechEngineUnavailable(RuntimeError):
    """Raised when no speech-to-text engine can be loaded or run."""


@_cache_resource
def _load_faster_whisper(model_size: str):
    """Load (once) a faster-whisper model on CPU with int8 quantisation."""
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device="cpu", compute_type=config.WHISPER_COMPUTE_TYPE)


@_cache_resource
def _load_openai_whisper(model_size: str):
    """Load (once) an openai-whisper model on CPU."""
    import whisper
    return whisper.load_model(model_size, device="cpu")


def _result(text: str = "", language: str = "", confidence: float = 0.0,
            duration: float = 0.0, engine: str = "none") -> dict[str, Any]:
    return {"text": text, "language": language, "confidence": confidence,
            "duration": duration, "engine": engine}


def _wav_info(audio_bytes: bytes) -> tuple[float, float] | None:
    """Return (duration_seconds, normalised_rms) for a WAV, or None if it can't be analysed."""
    try:
        with wave.open(io.BytesIO(audio_bytes)) as wav:
            rate, frames_n, width = wav.getframerate(), wav.getnframes(), wav.getsampwidth()
            if rate <= 0:
                return None
            duration = frames_n / rate
            if width != 2:
                return duration, 1.0  # cannot measure loudness: assume not silent
            raw = wav.readframes(min(frames_n, rate * 60))
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder == "big":
            samples.byteswap()
        if not samples:
            return duration, 0.0
        picked = samples[:: max(1, len(samples) // 50000)]
        rms = math.sqrt(sum(s * s for s in picked) / len(picked)) / 32768.0
        return duration, rms
    except Exception:
        return None


def audio_level(audio_bytes: bytes) -> float:
    """Loudness of a WAV recording scaled to 0-1 (for UI visuals); 0.0 on any problem."""
    info = _wav_info(audio_bytes or b"")
    if info is None:
        return 0.0
    return float(max(0.0, min(1.0, info[1] * 6.0)))


def _confidence(avg_logprobs: list[float]) -> float:
    """Map segment average log-probabilities to a 0-1 confidence."""
    if not avg_logprobs:
        return 0.0
    probs = [math.exp(max(-5.0, min(0.0, lp))) for lp in avg_logprobs]
    return round(sum(probs) / len(probs), 3)


def _run_faster_whisper(path: str, model_size: str) -> dict[str, Any]:
    model = _load_faster_whisper(model_size)
    segments, info = model.transcribe(path, beam_size=1, vad_filter=True,
                                      condition_on_previous_text=False)
    texts: list[str] = []
    logprobs: list[float] = []
    for seg in segments:
        if seg.text.strip():
            texts.append(seg.text.strip())
            logprobs.append(seg.avg_logprob)
    return _result(" ".join(texts).strip(), getattr(info, "language", "") or "",
                   _confidence(logprobs), float(getattr(info, "duration", 0.0) or 0.0))


def _run_openai_whisper(path: str, model_size: str) -> dict[str, Any]:
    model = _load_openai_whisper(model_size)
    out = model.transcribe(path, fp16=False)
    segments = out.get("segments") or []
    duration = float(segments[-1]["end"]) if segments else 0.0
    return _result((out.get("text") or "").strip(), out.get("language", "") or "",
                   _confidence([s.get("avg_logprob", -1.0) for s in segments]), duration)


def transcribe(audio_bytes: bytes, model_size: str = "base") -> dict:
    """Transcribe WAV bytes into {text, language, confidence, duration, engine}.

    Empty or silent audio returns an empty `text` (no exception). Raises
    SpeechEngineUnavailable when no engine can be loaded or run.
    """
    if not audio_bytes:
        return _result()
    info = _wav_info(audio_bytes)
    if info is not None:
        duration, rms = info
        if duration < config.MIN_AUDIO_SECONDS or rms < config.SILENCE_RMS:
            return _result(duration=duration)
    elif len(audio_bytes) < config.MIN_AUDIO_BYTES:
        return _result()

    engines: list[tuple[str, Callable[[str, str], dict[str, Any]]]] = [
        ("faster-whisper", _run_faster_whisper),
        ("openai-whisper", _run_openai_whisper),
    ]
    errors: list[str] = []
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        for name, runner in engines:
            try:
                out = runner(path, model_size)
                out["engine"] = name
                return out
            except Exception as exc:  # missing package, model download failure, decode error ...
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
    except OSError as exc:
        errors.append(f"temp file: {exc}")
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    raise SpeechEngineUnavailable(
        "No speech engine is available. Install one with 'pip install faster-whisper' "
        "(the first run needs internet to download the model), or type your command instead. "
        "Details: " + " | ".join(errors))