"""Windows 내장 OCR로 이미지에서 텍스트를 추출한다.

인터넷 연결 없이 동작하며, Windows에 설치된 언어 팩(한국어 포함)을 그대로 쓴다.
winsdk 또는 winrt 패키지 중 설치된 쪽을 자동으로 사용한다.
"""
from __future__ import annotations

import asyncio
import io
import re


def _load_winrt():
    """winsdk(신형) → winrt(구형) 순서로 WinRT 바인딩을 찾는다."""
    try:
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.graphics.imaging import BitmapDecoder
        from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
        return OcrEngine, BitmapDecoder, DataWriter, InMemoryRandomAccessStream
    except ImportError:
        pass
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
        return OcrEngine, BitmapDecoder, DataWriter, InMemoryRandomAccessStream
    except ImportError:
        raise RuntimeError("OCR 기능에는 winsdk 패키지가 필요합니다.\n명령창에서: pip install winsdk") from None


async def _recognize(png_bytes: bytes) -> str:
    OcrEngine, BitmapDecoder, DataWriter, InMemoryRandomAccessStream = _load_winrt()
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(png_bytes)
    await writer.store_async()
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("Windows에 OCR 언어 팩이 없습니다.\n설정 > 시간 및 언어 > 언어에서 한국어 언어 팩을 설치하세요.")
    result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines)


async def _recognize_lines(png_bytes: bytes):
    """줄 단위 텍스트와 각 단어의 위치를 함께 돌려준다: [(줄텍스트, [(단어, (x,y,w,h)), …]), …]"""
    OcrEngine, BitmapDecoder, DataWriter, InMemoryRandomAccessStream = _load_winrt()
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(png_bytes)
    await writer.store_async()
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("Windows에 OCR 언어 팩이 없습니다.")
    result = await engine.recognize_async(bitmap)
    lines = []
    for line in result.lines:
        words = [(word.text, (word.bounding_rect.x, word.bounding_rect.y,
                              word.bounding_rect.width, word.bounding_rect.height)) for word in line.words]
        lines.append((line.text, words))
    return lines


# 가릴 대상: 휴대폰·일반 전화번호 / 이메일 / 주민등록번호 / 카드번호 형태
_SENSITIVE_PATTERNS = (
    re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}"),          # 휴대폰
    re.compile(r"0\d{1,2}[-.)\s]\d{3,4}[-.\s]?\d{4}"),            # 지역 전화
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                        # 이메일
    re.compile(r"\d{6}[-\s]?[1-4]\d{6}"),                           # 주민등록번호
    re.compile(r"\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}"),           # 카드번호
)


def find_sensitive(image) -> list[tuple[float, float, float, float]]:
    """이미지에서 전화번호·이메일·주민번호 등으로 보이는 단어들의 위치를 찾는다."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "PNG")
    try:
        lines = asyncio.run(_recognize_lines(buffer.getvalue()))
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"텍스트를 인식하지 못했습니다.\n{error}") from error
    regions = []
    for line_text, words in lines:
        if not any(pattern.search(line_text) for pattern in _SENSITIVE_PATTERNS):
            continue
        # 민감 정보가 있는 줄에서 숫자·@ 성분이 든 단어만 가린다.
        for text, rect in words:
            digits = sum(ch.isdigit() for ch in text)
            if digits >= 2 or "@" in text:
                regions.append(rect)
    return regions


def extract_text(image) -> str:
    """PIL 이미지에서 텍스트를 추출해 돌려준다. 실패 시 RuntimeError로 이유를 알린다."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "PNG")
    try:
        return asyncio.run(_recognize(buffer.getvalue()))
    except RuntimeError:
        raise
    except Exception as error:  # WinRT 호출 실패를 사용자에게 그대로 전달한다.
        raise RuntimeError(f"텍스트를 인식하지 못했습니다.\n{error}") from error
