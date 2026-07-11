from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parents[1] / "websites/example.com/content/media/content-workflow.png"
image = Image.new("RGB", (1200, 630), "#f5f7fa")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((90, 165, 470, 465), radius=28, fill="#1f2937")
for x, color in ((130, "#ef4444"), (160, "#f59e0b"), (190, "#22c55e")):
    draw.ellipse((x - 9, 196, x + 9, 214), fill=color)
font = ImageFont.load_default(size=48)
small = ImageFont.load_default(size=26)
bottom = ImageFont.load_default(size=34)
draw.text((135, 275), "Markdown", font=font, fill="white")
draw.text((135, 345), "post.md + image.png", font=small, fill="#93c5fd")
draw.line((510, 315, 665, 315), fill="#2563eb", width=22)
draw.line((625, 270, 680, 315, 625, 360), fill="#2563eb", width=22, joint="curve")
draw.ellipse((730, 145, 1070, 485), fill="#21759b")
word_font = ImageFont.load_default(size=170)
draw.text((900, 315), "W", font=word_font, fill="white", anchor="mm")
draw.text((600, 560), "VS Code -> REST API -> WordPress", font=bottom, fill="#111827", anchor="mm")
image.save(OUTPUT, optimize=True)

