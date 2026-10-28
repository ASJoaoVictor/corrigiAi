# Build only on Windows, with CPU torch and pre-downloaded OCR models.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
entrypoint = 'corrigiai_testes.py' if os.getenv('CORRIGIAI_BUILD_SQLITE_TEST') == '1' else 'corrigiai_desktop.py'
models = root / 'build' / 'ocr-models'
if not (models / 'english_g2.pth').is_file():
    raise SystemExit('Prepare OCR models before packaging.')
datas = [(str(root / 'app' / part), 'app/' + part) for part in ('templates', 'static', 'omr')]
datas.append((str(models), 'ocr-models'))
binaries, hiddenimports = [], ['psycopg', 'psycopg2', 'win32crypt', 'win32timezone', 'win32com.shell.shell', 'win32com.shell.shellcon', 'sqlite3', 'sqlalchemy.dialects.sqlite.pysqlite']
for package in ('easyocr', 'torch', 'torchvision', 'cv2', 'skimage', 'scipy'):
    package_data, package_bins, package_imports = collect_all(package, include_py_files=False,
        filter_submodules=lambda name: not any(part in ('tests', 'test') for part in name.split('.')))
    datas += package_data
    binaries += package_bins
    hiddenimports += package_imports
icon = root / 'assets' / 'corrigiai.ico'
a = Analysis([str(root / entrypoint)], pathex=[str(root)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=['pytest', 'gunicorn', 'IPython', 'matplotlib', 'tensorboard'])
# Package data collectors can include upstream test fixtures; omit those.
a.datas = [item for item in a.datas if not any(part in ('tests', 'test', '__pycache__') for part in Path(item[0]).parts)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='corrigiAi',
          console=False, debug=False, upx=False, icon=str(icon) if icon.exists() else None)
coll = COLLECT(exe, a.binaries, a.datas, name='corrigiAi', upx=False)
