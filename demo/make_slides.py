"""Four 1920x1080 slides for the demo video: title, how it works, numbers, close.

    python demo/make_slides.py demo/slides

Needs Pillow and Segoe UI (Windows). Numbers are the measured ones from README.md.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
PAPER, INK, GREY, RED, GREEN, AMBER = (246, 243, 236), (24, 24, 24), (120, 116, 108), (196, 40, 28), (32, 120, 70), (190, 120, 10)


def font(size, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf", size)


def page():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 24, H], fill=RED)  # the gate: one red bar, on every slide
    return img, d


def title(out):
    img, d = page()
    d.text((140, 330), "MoneyGate", font=font(150, True), fill=INK)
    d.text((146, 520), "A safety gate for AI agents that move money", font=font(56), fill=INK)
    d.text((146, 640), "Muse Spark judge  ·  screenshots and voice notes via Meta models  ·  MCP  ·  Telegram",
           font=font(34), fill=GREY)
    d.text((146, 900), "English · Русский · Қазақша", font=font(34), fill=GREY)
    img.save(out / "1_title.png")


def box(d, x, y, w, h, head, lines, color=INK):
    d.rounded_rectangle([x, y, x + w, y + h], 18, outline=color, width=4, fill=(255, 255, 255))
    d.text((x + 28, y + 22), head, font=font(38, True), fill=color)
    for i, line in enumerate(lines):
        d.text((x + 28, y + 82 + 46 * i), line, font=font(30), fill=INK)


def arrow(d, x1, y, x2):
    d.line([x1, y, x2 - 18, y], fill=INK, width=5)
    d.polygon([(x2, y), (x2 - 26, y - 16), (x2 - 26, y + 16)], fill=INK)


def how(out):
    img, d = page()
    d.text((140, 80), "Every money-moving action passes the gate first", font=font(60, True), fill=INK)
    box(d, 140, 260, 400, 330, "Conversation", ["chat text", "screenshot  → Muse Spark", "voice note  → Muse Voice", "  (+ Spark audio for kk)"])
    arrow(d, 550, 425, 640)
    box(d, 650, 260, 380, 330, "Agent", ["proposes ONE action:", "pay, share a code,", "open a link, reply", "(planner: Muse Spark)"])
    arrow(d, 1040, 425, 1130)
    box(d, 1140, 200, 640, 450, "MoneyGate", ["1  mandate: limits, never", "    an SMS code, a person", "    for irreversible steps", "2  Muse Spark judge", "3  red flags (regex, ru/kk/en)", "    floor under the judge"], RED)
    for i, (word, color) in enumerate((("allowed", GREEN), ("your call", AMBER), ("STOPPED", RED))):
        d.text((1160 + 220 * i, 700), word, font=font(40, True), fill=color)
    d.text((140, 860), "Each decision → hash-chained journal, verified by an independent tool:", font=font(34), fill=INK)
    d.text((140, 915), "npx proofbyte-agent-trace verify   →   one edited record and the chain breaks", font=font(34, True), fill=GREY)
    img.save(out / "2_how.png")


def numbers(out):
    img, d = page()
    d.text((140, 80), "Measured, not claimed", font=font(60, True), fill=INK)
    d.text((140, 170), "Scam requests in Russian, Kazakh, mixed and English; details and data in the repo", font=font(34), fill=GREY)
    rows = [
        ("Llama 3.1 8B, plain chat", "warns in 9 of 36", "never in Kazakh"),
        ("Muse Spark, plain chat", "warns in 54 of 54", "knows scams"),
        ("Muse Spark as the agent", "1 loss of 48", "Kazakh OLX prepayment"),
        ("Agent that does what it's asked", "46 losses of 48", ""),
    ]
    y = 280
    d.text((140, y), "Without the gate", font=font(36, True), fill=GREY)
    for i, (who, what, note) in enumerate(rows):
        yy = y + 70 + 78 * i
        d.text((140, yy), who, font=font(38), fill=INK)
        d.text((900, yy), what, font=font(38, True), fill=INK)
        d.text((1300, yy), note, font=font(32), fill=GREY)
    y = 720
    d.line([140, y - 20, W - 140, y - 20], fill=INK, width=3)
    d.text((140, y), "With MoneyGate", font=font(36, True), fill=RED)
    d.text((140, y + 70), "48 / 48 scams stopped   ·   6 / 6 unseen ones   ·   0 legitimate requests blocked",
           font=font(42, True), fill=INK)
    d.text((140, y + 150), "Same 72 decisions when the chats arrive as screenshots", font=font(36), fill=INK)
    img.save(out / "3_numbers.png")


def close(out):
    img, d = page()
    d.text((140, 300), "Muse Spark knows the scam.", font=font(80, True), fill=INK)
    d.text((140, 410), "MoneyGate makes it a check no agent can skip.", font=font(80, True), fill=RED)
    d.text((146, 640), "Any agent: MCP tool check_action", font=font(40), fill=INK)
    d.text((146, 710), "Try it: @MoneyGateDemo_Bot on Telegram", font=font(40), fill=INK)
    d.text((146, 780), "github.com/oleg-vdv/moneygate", font=font(40), fill=INK)
    img.save(out / "4_close.png")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "demo/slides")
    out.mkdir(parents=True, exist_ok=True)
    for make in (title, how, numbers, close):
        make(out)
    print("slides in", out)
