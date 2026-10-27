import sys
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]
W, H = 720, 1100
img = Image.new("RGB", (W, H), (236, 229, 221))
d = ImageDraw.Draw(img)
f = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
fb = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)
fs = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
d.rectangle([0, 0, W, 110], fill=(7, 94, 84))
d.text((30, 22), "+7 707 913 44 81", font=fb, fill="white")
d.text((30, 64), "в сети", font=fs, fill=(210, 230, 225))
def wrap(t, width=30):
    out, line = [], ""
    for w in t.split():
        if len(line) + len(w) + 1 > width: out.append(line); line = w
        else: line = (line + " " + w).strip()
    return out + [line]
y = 140
msgs = [("in", "Мама привет, это Арман. Телефон упал в воду, пишу с нового номера, старый пока не работает", "18:02"),
        ("out", "Арманжан, ты где? Всё нормально?", "18:04"),
        ("in", "Да, всё ок. Мам срочно нужно 85 000, оплатить за общагу до вечера, иначе выселят", "18:05"),
        ("in", "Скинь на эту карту, это друга: 4400 4302 1187 6650", "18:05"),
        ("in", "Только папе не говори пока, сам потом объясню. Вечером верну", "18:06")]
for side, text, t in msgs:
    lines = wrap(text)
    h = 22 + 34 * len(lines) + 24
    w = 470
    x = 24 if side == "in" else W - w - 24
    d.rounded_rectangle([x, y, x + w, y + h], 14, fill=(255, 255, 255) if side == "in" else (220, 248, 198))
    for i, l in enumerate(lines):
        d.text((x + 18, y + 12 + 34 * i), l, font=f, fill=(20, 20, 20))
    d.text((x + w - 70, y + h - 30), t, font=fs, fill=(120, 120, 120))
    y += h + 18
img.save(out)
print(out, img.size)
