"""Scams arrive as screenshots and voice notes, not as text: turn both into a transcript.

Screenshot -> Muse Spark image understanding (chat completions, image_url part).
Voice note -> Muse Voice Transcribe (POST /v1/asr/transcribe, mono 16-bit WAV).
Telegram voice notes are OGG/Opus: ffmpeg converts them (PATH, or the binary that
ships with the imageio-ffmpeg wheel).

The transcript then goes to the judge like any pasted conversation. Nothing here
decides anything: a misread screenshot can only make the judge more careful, because
the red flags and the mandate still run on what was read.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid

from .judge import load_env_file

SCREENSHOT_PROMPT = (
    "This is a screenshot from a messenger, a marketplace chat, an SMS list or a bank app. "
    "Transcribe it as plain text. First line: the chat title (contact name or number) if one is "
    "shown. Then every message in order, one per line, as 'them: ...' or 'me: ...'. Copy phone "
    "numbers, card numbers, amounts, links and names exactly as written. Keep the original language. "
    "Do not summarise, translate or add anything."
)


class MediaError(RuntimeError):
    pass


class MetaMedia:
    def __init__(self, api_key: str, base_url: str = "https://api.meta.ai/v1",
                 vision_model: str = "muse-spark-1.3",
                 asr_model: str = "muse-voice-transcribe-1.0", timeout: float = 120.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.vision_model = vision_model
        self.asr_model = asr_model
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "MetaMedia":
        load_env_file()
        key = os.environ.get("MONEYGATE_API_KEY") or os.environ.get("MODEL_API_KEY")
        if not key:
            raise MediaError("MONEYGATE_API_KEY is not set")
        return cls(key, vision_model=os.environ.get("MONEYGATE_VISION_MODEL", "muse-spark-1.3"))

    def _post(self, path: str, data: bytes, content_type: str) -> dict:
        request = urllib.request.Request(
            self.base_url + path, data=data, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": content_type})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise MediaError(f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise MediaError(repr(exc)) from exc

    def read_screenshot(self, image: bytes, mime: str = "image/jpeg") -> str:
        body = {
            "model": self.vision_model,
            "max_tokens": 4000,          # reasoning shares the budget
            "reasoning_effort": "low",   # copying text needs no deep thought
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": SCREENSHOT_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}},
            ]}],
        }
        payload = self._post("/chat/completions", json.dumps(body).encode("utf-8"), "application/json")
        text = (payload["choices"][0]["message"].get("content") or "").strip()
        if not text:
            raise MediaError("the screenshot came back empty")
        return text

    def transcribe(self, audio: bytes) -> str:
        wav = audio if audio[:4] == b"RIFF" else to_wav(audio)
        settings = {"mode": "PUSH_TO_TALK", "model": self.asr_model, "audioEncoding": "WAV",
                    # Not in the 25 evaluated languages, but recognised; the hint helps code-switching.
                    "languageBias": ["Russian", "Kazakh"]}
        try:
            return self._asr(wav, settings)
        except MediaError as exc:
            if not str(exc).startswith("HTTP 400"):
                raise
            settings.pop("languageBias")  # an unsupported hint must not cost the transcript
            return self._asr(wav, settings)

    def _asr(self, wav: bytes, settings: dict) -> str:
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"request\"\r\n"
            f"Content-Type: application/json\r\n\r\n{json.dumps(settings)}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"voice.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode("utf-8") + wav + f"\r\n--{boundary}--\r\n".encode("utf-8")
        payload = self._post("/asr/transcribe", body, f"multipart/form-data; boundary={boundary}")
        return (payload.get("transcript") or "").strip()


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise MediaError("ffmpeg not found: install it or `pip install imageio-ffmpeg`") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def to_wav(audio: bytes) -> bytes:
    """Any container ffmpeg reads (Telegram OGG/Opus, m4a, mp3) -> mono 16-bit 24 kHz WAV."""
    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", "-map_metadata", "-1", "-f", "wav", "pipe:1"],
        input=audio, capture_output=True, timeout=60)
    if proc.returncode != 0 or proc.stdout[:4] != b"RIFF":
        raise MediaError("could not convert audio: " + proc.stderr.decode("utf-8", "replace")[:200])
    return proc.stdout
