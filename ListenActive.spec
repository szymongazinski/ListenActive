# Build with Python 3.12 on Windows x64: pyinstaller ListenActive.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for package in ['faster_whisper', 'ctranslate2', 'tokenizers', 'onnxruntime', 'av', 'nvidia.cublas', 'nvidia.cudnn']:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
datas += [('LICENSE', '.'), ('THIRD-PARTY.md', '.'), ('README.md', '.')]
a = Analysis(['main.py'], pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=['torch', 'tensorflow', 'matplotlib', 'pandas', 'IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ListenActive', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ListenActive')
