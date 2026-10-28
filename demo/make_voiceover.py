"""Synthesised English voice-over for the demo video, one MP3 per scene plus subtitles.

    python demo/make_voiceover.py demo/voiceover

Uses edge-tts (Microsoft neural voices, online; the text sent is only this public script).
Each scene must fit its slot in docs/video.md; the script prints the spare seconds.
"""

import asyncio
import sys
from pathlib import Path

import edge_tts

VOICE = "en-US-AndrewNeural"
RATE = "+0%"

# (slot start, slot end, text): keep in step with the table in docs/video.md
SCENES = [
    (0, 12, "Hi Mom, it's Arman, new number. Send eighty-five thousand to my friend's card, "
            "don't tell Dad. Every family in Kazakhstan has seen this message."),
    (12, 25, "Now AI assistants are starting to pay bills and answer sellers for people. "
             "When that message reaches an agent, who stops the payment? "
             "This is MoneyGate: a safety gate for AI agents that move money."),
    (25, 45, "The agent proposes one action. Before it runs, MoneyGate checks it three ways: "
             "a mandate with limits and hard rules, like never giving out an SMS code; "
             "a Muse Spark judge; and red-flag rules in Russian, Kazakh and English. "
             "Screenshots are read by Muse Spark, voice notes by Muse Voice Transcribe."),
    (45, 75, "Here is the assistant in Telegram. I forward the screenshot and ask it to send the money. "
             "The agent proposes the transfer, exactly as asked. MoneyGate stops it: "
             "someone on a new number, a card from the message, pressure to hurry, keep it secret."),
    (75, 100, "The same scam as a voice note in Kazakh. Meta's transcriber doesn't cover Kazakh yet, "
              "so MoneyGate falls back to Muse Spark audio. "
              "Stopped again, and the advice comes back in Kazakh."),
    (100, 115, "And an ordinary bill goes straight through. A gate that blocks everything is useless."),
    (115, 135, "Every decision is written to a hash-chained journal. An independent tool verifies it, "
               "and if anyone edits a single record, the chain breaks."),
    (135, 165, "We measured it. Muse Spark already knows scams: in plain chat it warns every time. "
               "But agents don't chat, they act. An agent that does what it's asked would lose money "
               "in forty-six of forty-eight cases. Even Muse Spark as the agent agreed once, "
               "to a Kazakh marketplace prepayment. A small on-device model warns in nine of thirty-six, "
               "never in Kazakh. With MoneyGate: every scam stopped, no legitimate request blocked."),
    (165, 180, "Any agent can call MoneyGate over MCP. Muse Spark knows the scam; "
               "MoneyGate makes it a check no agent can skip. Try the bot. The code is on GitHub."),
]


def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


async def scene(i: int, start: int, end: int, text: str, out: Path) -> list[tuple[float, float, str]]:
    """Writes the MP3; returns sentence cues in seconds from the start of the video."""
    cues = []
    with (out / f"{i:02}_{start:03}s.mp3").open("wb") as audio:
        async for chunk in edge_tts.Communicate(text, VOICE, rate=RATE, boundary="SentenceBoundary").stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                begin = chunk["offset"] / 1e7
                cues.append((start + begin, start + begin + chunk["duration"] / 1e7, chunk["text"]))
    return cues


async def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    srt, n = [], 0
    for i, (start, end, text) in enumerate(SCENES, 1):
        cues = await scene(i, start, end, text, out)
        spoken = cues[-1][1] - start if cues else 0
        print(f"scene {i}: {spoken:5.1f} s of {end - start} s slot" + ("   TOO LONG" if spoken > end - start else ""))
        for a, b, line in cues:
            n += 1
            srt.append(f"{n}\n{stamp(a)} --> {stamp(b)}\n{line}\n")
    (out / "subtitles_en.srt").write_text("\n".join(srt), encoding="utf-8")
    full_track(out)


def full_track(out: Path) -> None:
    """All scenes on one 3:00 track, each at its slot start: drop it under the video as is."""
    import subprocess

    from imageio_ffmpeg import get_ffmpeg_exe

    parts = [out / f"{i:02}_{start:03}s.mp3" for i, (start, _, _) in enumerate(SCENES, 1)]
    args = [get_ffmpeg_exe(), "-y", "-loglevel", "error"]
    for p in parts:
        args += ["-i", str(p)]
    delays = "".join(f"[{k}]adelay={start * 1000}:all=1[a{k}];" for k, (start, _, _) in enumerate(SCENES))
    mix = "".join(f"[a{k}]" for k in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,apad=whole_dur=180"
    subprocess.run(args + ["-filter_complex", delays + mix, "-t", "180", str(out / "voiceover_full.mp3")], check=True)
    print("full track:", out / "voiceover_full.mp3")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else "demo/voiceover")))
