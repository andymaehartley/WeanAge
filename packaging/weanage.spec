# PyInstaller spec: builds a single-file WeanAge executable.
#   poetry run pyinstaller packaging/weanage.spec
from pathlib import Path

root = Path(SPECPATH).parent
pkg = root / "src" / "weanage"

a = Analysis(
    [str(pkg / "__main__.py")],
    pathex=[str(root / "src")],
    datas=[(str(pkg / "data"), "weanage/data"), (str(pkg / "web"), "weanage/web")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                   "uvicorn.lifespan.on", "scipy.optimize", "scipy.stats"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="weanage", console=True, upx=False)
