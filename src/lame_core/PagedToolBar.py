from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QToolBar, QToolButton, QButtonGroup,
    QStackedWidget, QSizePolicy
)


class PagedToolBar(QWidget):
    """A toolbar with a fixed, bounded footprint: a row of page-selector
    tabs on top, above a second row where a pinned set of actions that
    never changes sits beside a content area whose contents swap per page
    (sized to exactly what that page needs, not stretched to fill dead
    space).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(2)

        # Row 1: page tabs
        self.page_bar = QToolBar()
        self.page_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._page_group = QButtonGroup(self)
        self._page_group.setExclusive(True)
        outer.addWidget(self.page_bar)

        # Row 2: pinned actions (left) beside the swappable page content
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(4)

        self.pinned_bar = QToolBar()
        self.pinned_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        bottom_row.addWidget(self.pinned_bar)

        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Stretch factor 1 (rather than a trailing addStretch()) so leftover
        # width is claimed by `pages` itself, not left as bare QWidget
        # background past its content -- QStackedWidget always resizes its
        # current child to fill its own rect, and that child is a QToolBar,
        # which paints its own background across whatever width it's given.
        # A separate stretch spacer has no widget to paint, so it would show
        # PagedToolBar's own (differently colored) background instead.
        bottom_row.addWidget(self.pages, 1)

        outer.addLayout(bottom_row)

        self._page_names = []

    def add_page(self, name: str, page_widget: QWidget) -> int:
        """Register a new page, with a matching tab button in ``page_bar``.

        The first page added becomes the current/checked one.
        """
        idx = self.pages.addWidget(page_widget)
        self._page_names.append(name)

        btn = QToolButton(text=name, checkable=True, autoRaise=True)
        btn.clicked.connect(lambda: self.pages.setCurrentIndex(idx))
        self._page_group.addButton(btn)
        self.page_bar.addWidget(btn)

        if idx == 0:
            btn.setChecked(True)
            self.pages.setCurrentIndex(idx)

        self.sync_content_height()
        return idx

    def set_current_page(self, name: str) -> None:
        """Switch to the page registered under ``name``, if it exists."""
        if name not in self._page_names:
            return
        idx = self._page_names.index(name)
        self.pages.setCurrentIndex(idx)
        buttons = self._page_group.buttons()
        if 0 <= idx < len(buttons):
            buttons[idx].setChecked(True)

    def current_page_name(self) -> str:
        return self._page_names[self.pages.currentIndex()]

    def sync_content_height(self) -> None:
        """Match the swappable content row's height to the pinned row's.

        Ties the content row's height to `pinned_bar` (rather than measuring
        each page independently) so it stays constant across page switches
        *and* automatically tracks style changes that affect `pinned_bar`'s
        own height -- e.g. toggling icon-only vs. icon+text -- with no extra
        bookkeeping. Callers that change button styles on `pinned_bar` or
        any page (see `MainToolbar.set_show_button_text`) should call this
        again afterward so the fixed height reflects the new style.
        """
        height = self.pinned_bar.sizeHint().height()
        if height > 0:
            self.pages.setFixedHeight(height)
