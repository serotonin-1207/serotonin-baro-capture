"""Win32 이미지 클립보드. 소유권을 넘기지 못한 메모리는 직접 반환한다."""
import ctypes
import io
import time


def copy_image(image, owner):
    stream = io.BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(stream, "BMP")
    payload = stream.getbuffer()
    size = len(payload) - 14
    data = ctypes.c_char.from_buffer(payload, 14)
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
    user32.OpenClipboard.argtypes = (ctypes.c_void_p,)
    user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
    user32.SetClipboardData.restype = ctypes.c_void_p
    handle = kernel32.GlobalAlloc(0x0002, size)
    if not handle:
        raise OSError("클립보드 메모리를 할당하지 못했습니다.")
    transferred = False
    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise OSError("클립보드 메모리에 접근하지 못했습니다.")
        ctypes.memmove(pointer, ctypes.addressof(data), size)
        kernel32.GlobalUnlock(handle)
        for attempt in range(4):
            if user32.OpenClipboard(owner):
                break
            if attempt == 3:
                raise OSError("클립보드가 사용 중입니다. 최근 캡처에서 다시 복사해 주세요.")
            time.sleep(0.01)
        try:
            if not user32.EmptyClipboard() or not user32.SetClipboardData(8, handle):
                raise OSError("클립보드에 이미지를 복사하지 못했습니다.")
            transferred = True
        finally:
            user32.CloseClipboard()
    finally:
        if not transferred:
            kernel32.GlobalFree(handle)
