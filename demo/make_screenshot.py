"""Draw a WhatsApp-style "son with a new number" chat for the demo.

    python demo/make_screenshot.py demo/shot_son_ru.png ru
    python demo/make_screenshot.py demo/shot_son_en.png en

Synthetic: the number and card are made up. Needs Pillow and the Segoe UI font (Windows).
"""

import sys

from PIL import Image, ImageDraw, ImageFont

CHATS = {
    "ru": ("в сети", [
        ("in", "Мама привет, это Арман. Телефон упал в воду, пишу с нового номера, старый пока не работает", "18:02"),
        ("out", "Арманжан, ты где? Всё нормально?", "18:04"),
        ("in", "Да, всё ок. Мам срочно нужно 85 000, оплатить за общагу до вечера, иначе выселят", "18:05"),
        ("in", "Скинь на эту карту, это друга: 4400 4302 1187 6650", "18:05"),
        ("in", "Только папе не говори пока, сам потом объясню. Вечером верну", "18:06")]),
    "en": ("online", [
        ("in", "Hi Mom, it's Arman. Dropped my phone in water, texting from a new number, the old one doesn't work", "18:02"),
        ("out", "Arman, where are you? Are you ok?", "18:04"),
        ("in", "Yes all good. Mom I urgently need 85 000 tenge for the dorm by tonight or they'll kick me out", "18:05"),
        ("in", "Send it to this card, it's my friend's: 4400 4302 1187 6650", "18:05"),
        ("in", "Just don't tell Dad yet, I'll explain later. I'll pay you back tonight", "18:06")]),
}


def wrap(text, width=30):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return out + [line]


def main(out, lang="ru"):
    status, msgs = CHATS[lang]
    W, H = 720, 1100
    img = Image.new("RGB", (W, H), (236, 229, 221))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
    fb = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)
    fs = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
    d.rectangle([0, 0, W, 110], fill=(7, 94, 84))
    d.text((30, 22), "+7 707 913 44 81", font=fb, fill="white")
    d.text((30, 64), status, font=fs, fill=(210, 230, 225))
    y = 140
    for side, text, t in msgs:
        lines = wrap(text)
        h = 22 + 34 * len(lines) + 24
        w = 470
        x = 24 if side == "in" else W - w - 24
        d.rounded_rectangle([x, y, x + w, y + h], 14, fill=(255, 255, 255) if side == "in" else (220, 248, 198))
        for i, line in enumerate(lines):
            d.text((x + 18, y + 12 + 34 * i), line, font=f, fill=(20, 20, 20))
        d.text((x + w - 70, y + h - 30), t, font=fs, fill=(120, 120, 120))
        y += h + 18
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    main(*sys.argv[1:3])
