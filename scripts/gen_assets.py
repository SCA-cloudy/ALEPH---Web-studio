"""
테스트/제출용 샘플 자산 생성 스크립트.
전부 이 스크립트가 코드로 직접 그려서 만든 '자작' 이미지이며, 실제 사진이 아니므로
위치정보(EXIF GPS) 등 메타데이터가 원천적으로 존재하지 않는다.
"""
import json
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "test-assets")
os.makedirs(OUT, exist_ok=True)


def gradient_bg(w, h, c1, c2, vertical=True):
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    steps = h if vertical else w
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        if vertical:
            draw.line([(0, i), (w, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, h)], fill=(r, g, b))
    return img


# 1) 가로형 JPEG (풍경 느낌의 자작 그라디언트 + 원)
landscape = gradient_bg(1600, 900, (255, 183, 94), (255, 94, 148))
d = ImageDraw.Draw(landscape)
d.ellipse([1150, 120, 1450, 420], fill=(255, 255, 255, 255))
landscape.convert("RGB").save(os.path.join(OUT, "sample_landscape.jpg"), quality=90)

# 2) 세로형 PNG (인물 카드 느낌의 자작 그라디언트 + 사각형)
portrait = gradient_bg(900, 1600, (94, 156, 255), (94, 255, 210))
d = ImageDraw.Draw(portrait)
d.rounded_rectangle([200, 1100, 700, 1400], radius=40, fill=(255, 255, 255))
portrait.save(os.path.join(OUT, "sample_portrait.png"))

# 3) 투명 배경 PNG (로고 스티커 느낌)
transparent = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
d = ImageDraw.Draw(transparent)
d.ellipse([150, 150, 850, 850], fill=(255, 210, 60, 255))
d.ellipse([320, 380, 480, 540], fill=(40, 40, 40, 255))
d.ellipse([520, 380, 680, 540], fill=(40, 40, 40, 255))
d.arc([300, 550, 700, 800], start=200, end=340, fill=(40, 40, 40, 255), width=30)
transparent.save(os.path.join(OUT, "sample_transparent.png"))

# 4) 정사각형 JPEG (완성 이미지용)
square = gradient_bg(1200, 1200, (120, 90, 255), (255, 120, 190))
square.convert("RGB").save(os.path.join(OUT, "sample_square.jpg"), quality=90)

# 5) 위장 파일: 확장자는 .png 이지만 실제 내용은 일반 텍스트 (매직바이트 검증용)
with open(os.path.join(OUT, "fake_image.png"), "w", encoding="utf-8") as f:
    f.write("이것은 이미지가 아니라 텍스트 파일입니다. PNG 시그니처가 없습니다.\n")

# 6) 지원하지 않는 실제 이미지 포맷: 단색 GIF
gif = Image.new("P", (100, 100))
gif.putpalette([255, 0, 0] + [0, 0, 0] * 255)
gif.save(os.path.join(OUT, "unsupported.gif"))

print("이미지 자산 생성 완료:", os.listdir(OUT))

# ---------- 템플릿 JSON 샘플 ----------

valid_templates = [
    {
        "id": "tpl_sample_1",
        "name": "샘플-공지형",
        "text": "9월 정기 점검 안내",
        "x": 50,
        "y": 85,
        "fontSize": 8,
        "color": "#ffffff",
        "stroke": True,
        "image": None,
        "imageName": None,
        "updatedAt": "2026-09-01T00:00:00.000Z",
    },
    {
        "id": "tpl_sample_2",
        "name": "샘플-밈형",
        "text": "월요일의\n나",
        "x": 50,
        "y": 20,
        "fontSize": 12,
        "color": "#111111",
        "stroke": True,
        "image": None,
        "imageName": None,
        "updatedAt": "2026-09-02T00:00:00.000Z",
    },
    {
        "id": "tpl_sample_3",
        "name": "샘플-인용구",
        "text": "\"작게 시작해도 괜찮다\"",
        "x": 50,
        "y": 50,
        "fontSize": 6,
        "color": "#ffe082",
        "stroke": False,
        "image": None,
        "imageName": None,
        "updatedAt": "2026-09-03T00:00:00.000Z",
    },
]
with open(os.path.join(OUT, "valid_templates.json"), "w", encoding="utf-8") as f:
    json.dump(valid_templates, f, ensure_ascii=False, indent=2)

# 문법이 손상된 JSON (마지막에 쉼표+괄호 미종료)
with open(os.path.join(OUT, "broken_syntax.json"), "w", encoding="utf-8") as f:
    f.write('[\n  { "name": "깨진 파일", "text": "abc", "x": 50, "y": 50, "fontSize": 8, "color": "#ffffff", ]\n')

# 필수 항목(color)이 빠진 JSON
missing_required = [
    {
        "id": "tpl_missing_1",
        "name": "필수항목 누락 샘플",
        "text": "color 필드가 없음",
        "x": 50,
        "y": 50,
        "fontSize": 8,
        # "color" 누락
    }
]
with open(os.path.join(OUT, "missing_required.json"), "w", encoding="utf-8") as f:
    json.dump(missing_required, f, ensure_ascii=False, indent=2)

print("JSON 샘플 생성 완료")
