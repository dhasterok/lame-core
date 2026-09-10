"""
Minimal logging shim for ``lame_core`` and the sibling widget libraries that build
on it (blueberry-colortools, siesta-rest-editor).

These libraries sit *below* the application in the dependency graph, so they cannot
import the host application's logger directly. Instead they call :func:`log` here,
and the host registers its own handler at startup via :func:`set_log_handler`.

The host application (LaME) registers ``src.control.Logger.log``, which routes
messages to the LoggerDock or to the terminal in verbose mode.

Until a handler is registered -- and for anyone using these libraries standalone --
the fallback is quiet: only ``Error`` and ``Warning`` messages are written to stderr,
everything else is discarded.

Examples
--------

.. code-block:: python

    from lame_core.applog import log

    log(f"Icon not found: {path}", prefix="Warning")   # always shown
    log(f"Double-clicked on: {item}", prefix="UI")     # shown only when verbose
"""
import sys

__all__ = ['log', 'set_log_handler', 'get_log_handler']

# Prefixes that always reach the user, mirroring src.control.Logger.
_ALWAYS_SHOW = ('error', 'warning')

_handler = None


def set_log_handler(handler):
    """
    Register the callable used to emit log messages.

    Parameters
    ----------
    handler : callable or None
        A callable accepting ``(msg, prefix="")``. Passing None restores the
        quiet stderr fallback.
    """
    global _handler
    _handler = handler


def get_log_handler():
    """Return the currently registered log handler, or None."""
    return _handler


def log(msg, prefix=""):
    """
    Emit a log message through the registered handler.

    Parameters
    ----------
    msg : str
        The message to log.
    prefix : str, optional
        Category label, e.g. 'UI', 'Warning', 'Error'.
    """
    if _handler is not None:
        _handler(msg, prefix=prefix)
        return

    if prefix.strip().rstrip(':').lower() in _ALWAYS_SHOW:
        print(f"{prefix}: {msg}" if prefix else f"{msg}", file=sys.stderr)
