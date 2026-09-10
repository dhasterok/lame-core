"""
Make the mouse wheel scroll the panel the pointer is over.

The problem
-----------

Qt delivers a wheel event to the widget under the pointer and walks up the parent
chain only while each ancestor *ignores* it. An enclosing ``QScrollArea`` scrolls
only if the event survives that walk -- and several common widget classes accept
the wheel unconditionally, **even when they have nothing to scroll**:

* every ``QAbstractScrollArea`` subclass (``QTableWidget``, ``QListWidget``,
  ``QTreeView``, ``QPlainTextEdit``, ``QTextEdit``, ``QTextBrowser``,
  ``QGraphicsView``) swallows the wheel even when empty,
* ``QAbstractSpinBox`` swallows it *and silently changes its value*,
* ``FigureCanvasQTAgg`` (matplotlib) swallows it, because its ``wheelEvent``
  emits ``scroll_event`` and never calls ``ignore()``.

So in a panel whose body is covered by a results table, a log pane or a grid of
plots, the wheel does nothing anywhere except directly over the scrollbar. The
symptom is per-window, which is why only some panels feel broken.

The fix
-------

One application-wide event filter, installed once at startup:

.. code-block:: python

    from lame_core.wheel_scroll import install_wheel_scrolling

    install_wheel_scrolling(app)

On each wheel event it asks whether the hovered widget can actually *use* the
wheel. If it can, nothing changes. If it cannot, the event is forwarded to the
nearest enclosing scroll area that can scroll, and consumed.

The default is deliberately conservative: an unrecognised widget is assumed to
want its own wheel events, so only the three cases above are ever redirected.
Widgets for which the wheel is a real feature -- pyqtgraph views, which zoom --
are left alone.
"""
from PyQt6.QtCore import QObject, QEvent, QPointF
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QAbstractScrollArea, QAbstractSpinBox, QApplication, QWidget

from lame_core.applog import log

__all__ = ['WheelScrollFilter', 'install_wheel_scrolling']


def _is_plot_canvas(widget):
    """
    Is this a matplotlib canvas?

    Matched by class name rather than ``isinstance`` so that ``lame_core`` does
    not import matplotlib -- it sits below the plotting code in the dependency
    graph, and importing matplotlib here would pull it into every consumer.

    pyqtgraph views are deliberately *not* matched: there the wheel zooms, so
    consuming it is correct behaviour.

    Parameters
    ----------
    widget : QWidget
        Widget under the pointer.

    Returns
    -------
    bool
        ``True`` for a matplotlib Qt canvas.
    """
    return any(cls.__name__.startswith('FigureCanvas') for cls in type(widget).__mro__)


def _scrollable(area, vertical):
    """
    Can this scroll area move along the axis the wheel is turning?

    Parameters
    ----------
    area : QAbstractScrollArea
        Candidate scroll area.
    vertical : bool
        ``True`` to test the vertical scrollbar, ``False`` the horizontal one.

    Returns
    -------
    bool
        ``True`` if the relevant scrollbar has a non-empty range.
    """
    bar = area.verticalScrollBar() if vertical else area.horizontalScrollBar()
    return bar is not None and bar.maximum() > bar.minimum()


def _owning_scroll_area(widget):
    """
    Return the scroll area that ``widget`` is the viewport of, else ``None``.

    Real wheel events land on a scroll area's *viewport*, not on the scroll area
    itself, so the viewport has to be recognised as standing in for its owner.

    Parameters
    ----------
    widget : QWidget
        Widget under the pointer.

    Returns
    -------
    QAbstractScrollArea or None
        The owner if ``widget`` is a viewport, otherwise ``None``.
    """
    parent = widget.parentWidget()
    if isinstance(parent, QAbstractScrollArea) and parent.viewport() is widget:
        return parent
    return None


class WheelScrollFilter(QObject):
    """
    Application event filter that redirects unusable wheel events to the nearest
    enclosing scroll area.

    Install it with :func:`install_wheel_scrolling` rather than constructing it
    directly; the module keeps a reference to the installed instance so it is not
    garbage collected while Qt still holds a pointer to it.

    Parameters
    ----------
    parent : QObject, optional
        Owner, by default None.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Guard against re-entry: the event we forward is itself delivered
        # through this same filter.
        self._forwarding = False

    def _consumes_wheel(self, widget, vertical):
        """
        Should this widget keep the wheel event for itself?

        Parameters
        ----------
        widget : QWidget
            Widget under the pointer.
        vertical : bool
            ``True`` if the wheel is turning vertically.

        Returns
        -------
        bool
            ``True`` to leave the event alone, ``False`` to forward it onwards.
        """
        area = widget if isinstance(widget, QAbstractScrollArea) else _owning_scroll_area(widget)
        if area is not None:
            # An inner list/table/editor keeps the wheel only while it has
            # somewhere to scroll; an empty or fully-visible one hands it on.
            return _scrollable(area, vertical)

        if isinstance(widget, QAbstractSpinBox):
            # Scrolling past a spin box must not silently edit an analysis
            # parameter -- it only steps the value when it has focus.
            return widget.hasFocus()

        if _is_plot_canvas(widget):
            return False

        return True

    def _forward_target(self, widget, vertical):
        """
        Find the nearest ancestor scroll area able to scroll along this axis.

        Parameters
        ----------
        widget : QWidget
            Widget under the pointer.
        vertical : bool
            ``True`` if the wheel is turning vertically.

        Returns
        -------
        QAbstractScrollArea or None
            The scroll area to forward to, or ``None`` if there is none.
        """
        node = widget.parentWidget()
        while node is not None:
            if isinstance(node, QAbstractScrollArea) and _scrollable(node, vertical):
                return node
            if node.isWindow():
                break
            node = node.parentWidget()
        return None

    def eventFilter(self, obj, event):
        """
        Redirect a wheel event the hovered widget cannot use.

        Parameters
        ----------
        obj : QObject
            Intended receiver of the event.
        event : QEvent
            The event being delivered.

        Returns
        -------
        bool
            ``True`` if the event was consumed here, otherwise ``False``.
        """
        if event.type() != QEvent.Type.Wheel or self._forwarding:
            return False
        if not isinstance(obj, QWidget):
            return False

        vertical = event.angleDelta().y() != 0 or event.pixelDelta().y() != 0
        if self._consumes_wheel(obj, vertical):
            return False

        target = self._forward_target(obj, vertical)
        if target is None:
            return False

        viewport = target.viewport()
        local = viewport.mapFromGlobal(event.globalPosition().toPoint())
        forwarded = QWheelEvent(
            QPointF(local),
            event.globalPosition(),
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )

        self._forwarding = True
        try:
            QApplication.sendEvent(viewport, forwarded)
        finally:
            self._forwarding = False

        log(f"wheel forwarded from {type(obj).__name__} to "
            f"{type(target).__name__}({target.objectName() or '-'})", prefix="UI")
        return True


_filter = None


def install_wheel_scrolling(app=None):
    """
    Install the wheel-forwarding filter on the application.

    Idempotent: calling it again returns the filter already installed.

    Parameters
    ----------
    app : QApplication, optional
        Application to filter events for; defaults to the running instance.

    Returns
    -------
    WheelScrollFilter or None
        The installed filter, or ``None`` if there is no application to install
        it on.
    """
    global _filter

    if _filter is not None:
        return _filter

    app = app or QApplication.instance()
    if app is None:
        log("no QApplication -- wheel scrolling not installed", prefix="Warning")
        return None

    _filter = WheelScrollFilter(app)
    app.installEventFilter(_filter)
    return _filter
