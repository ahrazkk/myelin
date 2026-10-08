# PyInstaller recipe for Myelin.exe. From the repo root, after building the frontend:
#
#   pip install -e "backend[desktop,build]"
#   pyinstaller packaging/myelin.spec --noconfirm
#
# Output: dist/Myelin/Myelin.exe (a folder build: starts fast, easy for the installer to ship).
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(root, "frontend", "dist"), "frontend")]
for package in ("myelin", "tzdata", "recurring_ical_events", "icalendar", "webview"):
    datas += collect_data_files(package)

hiddenimports = (
    collect_submodules("myelin")
    + collect_submodules("uvicorn")
    + collect_submodules("webview")
    + ["pystray._win32", "windows_toasts", "tzdata"]
)

a = Analysis(
    [os.path.join(SPECPATH, "myelin_app.py")],
    pathex=[os.path.join(root, "backend")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Myelin",
    console=False,
    icon=os.path.join(SPECPATH, "myelin.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Myelin")
