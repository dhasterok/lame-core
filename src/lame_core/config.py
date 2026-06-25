from pathlib import Path

# Defaults — overridden by the host app calling setup()
BASEDIR: Path = Path(__file__).resolve().parent
RESOURCE_PATH: Path = BASEDIR / "resources"
ICONPATH: Path = RESOURCE_PATH / "icons"
STYLE_PATH: Path = RESOURCE_PATH / "styles"
APPDATA_PATH: Path = RESOURCE_PATH / "app_data"


def setup(
    basedir: Path | None = None,
    resource_path: Path | None = None,
    iconpath: Path | None = None,
    style_path: Path | None = None,
    appdata_path: Path | None = None,
) -> None:
    """Configure lame_core path constants.

    Call this once at application startup before any widgets are constructed.
    Any path not supplied keeps its current value.
    """
    global BASEDIR, RESOURCE_PATH, ICONPATH, STYLE_PATH, APPDATA_PATH

    if basedir is not None:
        BASEDIR = Path(basedir)
    if resource_path is not None:
        RESOURCE_PATH = Path(resource_path)
    if iconpath is not None:
        ICONPATH = Path(iconpath)
    if style_path is not None:
        STYLE_PATH = Path(style_path)
    if appdata_path is not None:
        APPDATA_PATH = Path(appdata_path)


def load_stylesheet(filename: str) -> str:
    replacements = {"{icon_path}": str(ICONPATH.as_posix())}
    with open(STYLE_PATH / filename, "r", encoding="utf-8") as fh:
        stylesheet = fh.read()
    for key, value in replacements.items():
        stylesheet = stylesheet.replace(key, value)
    return stylesheet
