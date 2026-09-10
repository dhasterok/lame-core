import os
import shutil
import sys
from pathlib import Path


def default_user_data_dir(app_name: str = "LaME") -> Path:
    """Return the conventional per-user writable data directory for this platform.

    Computed without Qt so it is safe to call before a ``QApplication`` exists.

    Parameters
    ----------
    app_name : str
        Name of the directory created under the platform's data location.

    Returns
    -------
    Path :
        ``%APPDATA%/<app_name>`` on Windows, ``~/Library/Application Support/<app_name>``
        on macOS, ``$XDG_DATA_HOME/<app_name>`` (or ``~/.local/share/<app_name>``)
        elsewhere. The directory is not created here.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / app_name


# Defaults — overridden by the host app calling setup()
BASEDIR: Path = Path(__file__).resolve().parent
RESOURCE_PATH: Path = BASEDIR / "resources"
ICONPATH: Path = RESOURCE_PATH / "icons"
STYLE_PATH: Path = RESOURCE_PATH / "styles"
APPDATA_PATH: Path = RESOURCE_PATH / "app_data"
# Writable, per-user, and never inside the installation directory — a frozen app
# bundle is read-only, so everything the app saves at runtime belongs here.
USERDATA_PATH: Path = default_user_data_dir()


def setup(
    basedir: Path | None = None,
    resource_path: Path | None = None,
    iconpath: Path | None = None,
    style_path: Path | None = None,
    appdata_path: Path | None = None,
    userdata_path: Path | None = None,
) -> None:
    """Configure lame_core path constants.

    Call this once at application startup before any widgets are constructed.
    Any path not supplied keeps its current value.
    """
    global BASEDIR, RESOURCE_PATH, ICONPATH, STYLE_PATH, APPDATA_PATH, USERDATA_PATH

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
    if userdata_path is not None:
        USERDATA_PATH = Path(userdata_path)


def user_data_dir(*subdirs: str) -> Path:
    """Return a writable directory under ``USERDATA_PATH``, creating it if needed.

    Parameters
    ----------
    *subdirs : str
        Path components below ``USERDATA_PATH``, e.g. ``user_data_dir('saved', 'figures')``.

    Returns
    -------
    Path :
        The directory, guaranteed to exist.
    """
    path = USERDATA_PATH.joinpath(*subdirs)
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_data_file(*relpath: str) -> Path:
    """Return a writable copy of a user-editable app data file.

    Files such as preset lists are shipped read-only inside the installation but are
    edited at runtime. The first time one is requested, the bundled copy is seeded into
    ``USERDATA_PATH`` and the writable path is returned from then on.

    Parameters
    ----------
    *relpath : str
        Path components relative to both ``APPDATA_PATH`` and the user data directory,
        e.g. ``user_data_file('qv_lists.csv')``.

    Returns
    -------
    Path :
        Location of the writable copy. The file itself may not exist if there was no
        bundled original to seed from — callers handle that as they do today.
    """
    target = USERDATA_PATH.joinpath('app_data', *relpath)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        source = APPDATA_PATH.joinpath(*relpath)
        if source.is_file():
            shutil.copy2(source, target)
    return target


def load_stylesheet(filename: str) -> str:
    replacements = {"{ICONPATH}": str(ICONPATH.as_posix())}
    with open(STYLE_PATH / filename, "r", encoding="utf-8") as fh:
        stylesheet = fh.read()
    for key, value in replacements.items():
        stylesheet = stylesheet.replace(key, value)
    return stylesheet
