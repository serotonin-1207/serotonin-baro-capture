"""최근 캡처를 메모리에만 보관한다."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CaptureRecord:
    image: object
    created: datetime = field(default_factory=datetime.now)


class CaptureHistory:
    def __init__(self, max_count=10, max_bytes=64 * 1024 * 1024):
        self.max_count = max_count
        self.max_bytes = max_bytes
        self.items = []

    def add(self, image):
        self.items.insert(0, CaptureRecord(image))
        used = 0
        for index, item in enumerate(self.items):
            # Pillow RGB 이미지의 내부 픽셀은 4바이트를 사용한다.
            used += item.image.width * item.image.height * 4
            if index and (index >= self.max_count or used > self.max_bytes):
                del self.items[index:]
                break
