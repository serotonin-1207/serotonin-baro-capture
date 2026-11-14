"""선택 UI가 포커스를 바꾸기 전에 확보한 화면과 가상 화면 좌표."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from PIL import Image, ImageGrab


@dataclass
class ScreenSnapshot:
    image: Image.Image
    origin: tuple[int, int]

    @classmethod
    def grab(cls) -> "ScreenSnapshot":
        user32 = ctypes.windll.user32
        origin = (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77))
        return cls(ImageGrab.grab(all_screens=True, include_layered_windows=True), origin)

    def crop(self, bbox) -> Image.Image:
        x, y = self.origin
        left, top, right, bottom = bbox
        # 선택 영역을 가상 화면 안으로 제한한다.
        bounds = (max(0, left - x), max(0, top - y),
                  min(self.image.width, right - x), min(self.image.height, bottom - y))
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError("선택한 영역이 화면 밖에 있습니다.")
        return self.image.crop(bounds)
