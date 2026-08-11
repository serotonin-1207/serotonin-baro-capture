"""설치 파일과 바로가기에 쓸 앱 아이콘(app.ico)을 생성한다."""
from pathlib import Path
from PIL import Image, ImageDraw

BLUE, INK = "#1677ff", "#25354d"


def render(size: int) -> Image.Image:
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 둥근 파란 배경
    d.rounded_rectangle((16, 16, s - 16, s - 16), radius=48, fill=BLUE)
    # 캡처 영역을 나타내는 흰 크롭 프레임(모서리 ㄱ자)
    m, t, L = 70, 14, 50
    white = "#ffffff"
    # 좌상
    d.line((m, m, m + L, m), fill=white, width=t)
    d.line((m, m, m, m + L), fill=white, width=t)
    # 우상
    d.line((s - m, m, s - m - L, m), fill=white, width=t)
    d.line((s - m, m, s - m, m + L), fill=white, width=t)
    # 좌하
    d.line((m, s - m, m + L, s - m), fill=white, width=t)
    d.line((m, s - m, m, s - m - L), fill=white, width=t)
    # 우하
    d.line((s - m, s - m, s - m - L, s - m), fill=white, width=t)
    d.line((s - m, s - m, s - m, s - m - L), fill=white, width=t)
    # 가운데 점(셔터 느낌)
    d.ellipse((s // 2 - 18, s // 2 - 18, s // 2 + 18, s // 2 + 18), fill=white)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    out = Path(__file__).with_name("app.ico")
    base = render(256)
    base.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved", out)


if __name__ == "__main__":
    main()
