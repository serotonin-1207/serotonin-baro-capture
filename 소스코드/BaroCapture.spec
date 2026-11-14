# -*- mode: python ; coding: utf-8 -*-
from importlib.metadata import distribution
from pathlib import Path
import sys

root = Path(SPECPATH)
pillow = distribution("Pillow")
pillow_license = next(pillow.locate_file(path) for path in pillow.files if path.name == "LICENSE")
datas = [(str(root / "app.ico"), "."), (str(root / "licenses"), "licenses"),
         (str(pillow_license), "licenses/Pillow"),
         (str(Path(sys.base_prefix) / "LICENSE.txt"), "licenses/Python")]
binaries = []


a = Analysis(
    ['hwp_capture.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["winsdk", "winrt", "numpy", "pandas", "matplotlib", "IPython", "pytest",
              "pystray"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SerotoninBaroCapture',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
    version='version_info.txt',
)

# 설치형은 런타임을 설치 시 배치해 실행마다 임시 압축을 풀지 않는다.
installed_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SerotoninBaroCaptureApp',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['app.ico'],
    version='version_info.txt',
)
installed = COLLECT(
    installed_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='SerotoninBaroCaptureInstalled',
)
