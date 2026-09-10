from pathlib import Path
from PyQt6.QtWidgets import (
        QWidget, QLineEdit, QTableWidget, QComboBox, QPushButton, QCheckBox, QWidget, QTreeView,
        QMenu, QDockWidget, QHeaderView, QToolButton, QSlider, QVBoxLayout, QHBoxLayout, QLabel,
        QSizePolicy, QScrollArea, QLayout, QToolBox, QSpinBox, QListWidget
    )
from PyQt6.QtGui import (
    QStandardItem, QStandardItemModel, QFont, QDoubleValidator, QIcon, QCursor, QPainter,
    QColor, QAction, QIcon
)
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtProperty, pyqtSignal, QSize
import lame_core.format as fmt
import pandas as pd

from lame_core.ColorManager import is_valid_hex_color
from lame_core.UITheme import default_font, ThemeManager
from lame_core.config import ICONPATH
from lame_core.applog import log

class VisibilityWidget(QWidget):
    visibilityChanged = pyqtSignal(bool)  # True = shown, False = hidden

    def showEvent(self, event):
        super().showEvent(event)
        self.visibilityChanged.emit(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibilityChanged.emit(False)

class CustomPage(QWidget):
    def __init__(
        self,
        obj_name: str=None,
        layout_cls=QVBoxLayout,
        layout_args=None,
        scrollable=True,
        parent=None,
    ):
        """
        A QWidget that contains a QScrollArea with a single content widget
        and layout. Simplifies putting scrollable pages into QToolBox, 
        QTabWidget, QDockWidget, etc.

        Parameters
        ----------

        layout_cls : QVBoxLayout | QHBoxLayout | QGridLayout | QFormLayout
            Layout class for the inner content, by default QVBoxLayout
        layout_args : dict
            Dictionary of kwargs to pass to the layout constructor
        scrollable : bool
            If False, skips the scroll area and uses the content directly,
            by default True
        """
        super().__init__(parent)
        self.setObjectName(obj_name)
        if layout_args is None:
            layout_args = {}

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        if scrollable:
            self._scroll = QScrollArea(parent=self)
            self._scroll.setWidgetResizable(True)
            outer_layout.addWidget(self._scroll)

            self._content = QWidget()
            self._content_layout = layout_cls(self._content, **layout_args)
            self._content.setLayout(self._content_layout)

            self._scroll.setWidget(self._content)
        else:
            # non-scrollable fallback: place content directly
            self._scroll = None
            self._content = QWidget(parent=self)
            self._content_layout = layout_cls(self._content, **layout_args)
            self._content.setLayout(self._content_layout)
            outer_layout.addWidget(self._content)

    @property
    def content_widget(self):
        return self._content

    @property
    def content_layout(self) -> QLayout:
        return self._content_layout

    def addItem(self, item):
        """Convenience to add a child item to the inner layout."""
        self._content_layout.addItem(item)

    def addWidget(self, widget):
        """Convenience to add a child widget to the inner layout."""
        self._content_layout.addWidget(widget)

    def addLayout(self, layout):
        """Convenience to add a child layout to the inner layout."""
        self._content_layout.addLayout(layout)

    def setContentsMargins(self, left, top, right, bottom):
        self._content_layout.setContentsMargins(left, top, right, bottom)

    def setSpacing(self, spacing):
        self._content_layout.setSpacing(spacing)

class CustomToolBox(QToolBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_dict = {}  # { page_text: {"light": QIcon(...), "dark": QIcon(...)} }
        self._current_theme = "light"  # default until set

    def set_theme(self, theme: str):
        """Set current theme and update all icons."""
        if theme not in ("light", "dark"):
            raise ValueError("Theme must be 'light' or 'dark'")
        self._current_theme = theme
        self.update_icons()

    def set_page_icons(self, page_text: str, light_icon: Path, dark_icon: Path):
        """Assign icons for a given page."""
        self.icon_dict[page_text] = {
            "light": QIcon(str(light_icon)),
            "dark": QIcon(str(dark_icon))
        }
        self.update_icon(page_text)

    def update_icon(self, page_text: str):
        """Update a single page icon based on current theme."""
        if page_text in self.icon_dict:
            icon = self.icon_dict[page_text][self._current_theme]
            # find the page index by matching text
            for i in range(self.count()):
                if self.itemText(i) == page_text:
                    self.setItemIcon(i, icon)
                    break

    def update_icons(self):
        """Update all page icons to match the current theme."""
        for page_text in self.icon_dict.keys():
            self.update_icon(page_text)

class CustomLineEdit(QLineEdit):
    """Custom line edit widget, when the only input should be of type float

    Adds additional functionality to QLineEdit by installing a validator and methods for limiting the
    precision of the displayed value in the UI.  Note that full precision of the value is stored in
    self.value, only a 'pretty' number is displayed.

    Parameters
    ----------
    parent : _type_, optional
        _description_, by default None
    value : float, optional
        _description_, by default 0.0
    precision : int, optional
        _description_, by default 4
    threshold : _type_, optional
        _description_, by default 1e4
    toward : int, optional
        _description_, by default None
    fixed_point : bool, optional
        If ``True``, display exactly ``precision`` digits after the decimal point
        (``f"{value:.{precision}f}"``) instead of ``precision`` significant digits,
        by default False
    validator : QValidator, optional
        Provide a validator to automatically text inputs for appropriate type and
        ranges, by default QDoubleValidator
    """
    def __init__(
            self,
            parent=None,
            value=0.0,
            precision=4,
            threshold=1e4,
            toward=None,
            fixed_point=False,
            validator=QDoubleValidator()
    ):
        super().__init__(parent)
        self._value = value
        self._precision = precision
        self._threshold = threshold
        self._toward = toward
        self._fixed_point = fixed_point
        self._lower_bound = None
        self._upper_bound = None
        self.textChanged.connect(self._update_value_from_text)
        self.setValidator(validator)
        self.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self._update_text_from_value()

    @property
    def value(self):
        """
        float: The current internal numeric value stored in the widget.
        """
        return self._value

    @value.setter
    def value(self, new_value):
        """
        Set the internal value and update the displayed text accordingly.

        Parameters
        ----------
        new_value : float
            The new value to store and display.
        """
        # ensure value is a float rather than integer
        if self._lower_bound is not None:
            new_value = max(self._lower_bound, new_value)
        if self._upper_bound is not None:
            new_value = min(self._upper_bound, new_value)
        self._value = new_value
        self._update_text_from_value()

    @property
    def precision(self):
        """
        int: The number of significant digits to display in the line edit.
        """
        return self._precision 

    @precision.setter
    def precision(self, new_precision):
        """
        Set the display precision and update the text accordingly.

        Parameters
        ----------
        new_precision : int
            New number of significant digits to display.
        """
        self._precision = new_precision
        self._update_text_from_value()

    @property
    def threshold(self):
        """
        float: Threshold above which scientific notation is used.
        """
        return self._threshold
    
    @threshold.setter
    def threshold(self, new_threshold):
        """
        Set the threshold for scientific notation and update the text.

        Parameters
        ----------
        new_threshold : float
            Value above which to switch to scientific notation.
        """
        self._threshold = new_threshold
        self._update_text_from_value()

    @property
    def toward(self):
        """
        int | float | None: Determines rounding direction in formatting.

        * 0 = round toward zero
        * 1 = round away from zero
        * None = standard rounding
        """
        return self._toward
    
    @toward.setter
    def toward(self, val):
        """
        Set the rounding direction and update the display.

        Parameters
        ----------
        val : int, float, or None
            Rounding mode to apply in formatting.
        """
        self._toward = val
        self._update_text_from_value()

    def set_bounds(self, lower=None, upper=None):
        """Set optional lower and upper bounds for the value."""
        self._lower_bound = lower
        self._upper_bound = upper
        # Apply clamping if value already exists
        self.value = self._value

    def _update_text_from_value(self):
        """
        Update the displayed text based on internal value and formatting rules.
        """
        if self._value is None:
            self.setText('')
        elif self._precision is None:
            self.setText(str(self._value))
        elif self._fixed_point:
            self.setText(f"{self._value:.{self._precision}f}")
        else:
            self.setText(fmt.dynamic_format(self._value, threshold=self._threshold, order=self._precision, toward=self._toward))

    def _update_value_from_text(self):
        """
        Update the internal value from the current text, if valid.
        """
        try:
            new_val = float(self.text())
            # Clamp if bounds are defined
            if self._lower_bound is not None:
                new_val = max(self._lower_bound, new_val)
            if self._upper_bound is not None:
                new_val = min(self._upper_bound, new_val)
            self._value = new_val
        except ValueError:
            # ignore error
            pass

class CustomTableWidget(QTableWidget):
    """
    A QTableWidget subclass with extended utility functions for data extraction and conversion.

    This widget supports conversion of table contents (including embedded widgets such as 
    QLineEdit, QComboBox, QCheckBox, etc.) to a pandas DataFrame, and provides convenience 
    methods for column-based data access. It is designed for integration with tools that 
    dynamically populate cells with interactive widgets.

    Examples
    --------
    >>> widget = CustomTableWidget()
    >>> widget.to_dataframe()
    >>> widget.column_to_list(0)
    >>> widget.column_to_list("Sample Name")

    Notes
    -----
    - Embedded widgets are interpreted based on their type (e.g., `QLineEdit.text()`, 
      `QCheckBox.isChecked()`).
    - Additional widget types can be handled by extending `extract_widget_data()`.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def extract_widget_data(self, widget: QWidget):
        """
        Extracts relevant data from a widget embedded in the table.

        This method is used to obtain the appropriate value representation of a widget 
        for export (e.g., into a DataFrame).

        Parameters
        ----------
        widget : QWidget
            A widget stored in a table cell.

        Returns
        -------
        str or bool or float or None
            The value extracted from the widget, depending on its type.
        """   
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QPushButton):
            return widget.text()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, CustomLineEdit):
            return widget.value
        # Add more widget types as needed
        else:
            return None

    def to_dataframe(self) -> pd.DataFrame:
        """
        Converts the table content (including widgets) to a pandas DataFrame.

        Returns
        -------
        pd.DataFrame
            A DataFrame with rows and columns matching the table content.
        """
        # Get the number of rows and columns in the QTableWidget
        row_count = self.rowCount()
        column_count = self.columnCount()

        
        # Create a dictionary to store the data with column headers
        column_headers = [self.horizontalHeaderItem(col).text() if self.horizontalHeaderItem(col) is not None else f'Column {col+1}' 
                          for col in range(column_count)]
        
        table_data = {
            column_headers[col]: [
                self.item(row, col).text() if self.item(row, col) is not None else self.extract_widget_data(self.cellWidget(row, col)) 
                for row in range(row_count)
            ] for col in range(column_count)
        }

        # table_data = {self.horizontalHeaderItem(col).text(): [] for col in range(column_count)}
        
        # # Iterate over all rows and columns to retrieve the data
        # for row in range(row_count):
        #     for col in range(column_count):
        #         item = self.item(row, col)
        #         if item is not None:
        #             table_data[self.horizontalHeaderItem(col).text()].append(item.text())
        #         else:
        #             # Check for a widget in the cell
        #             widget = self.cellWidget(row, col)
        #             if widget is not None:
        #                 table_data[self.horizontalHeaderItem(col).text()].append(self.extract_widget_data(widget))
        #             else:
        #                 table_data[self.horizontalHeaderItem(col).text()].append(None)
        
        # Convert the dictionary to a pandas DataFrame
        df = pd.DataFrame(table_data)
        
        return df

    def column_to_list(self, column):
        """
        Extracts data from a specified column into a list.

        Parameters
        ----------
        column : int or str
            Column index (int) or column header name (str).

        Returns
        -------
        list
            A list of cell values from the specified column.

        Raises
        ------
        ValueError
            If the specified column name or index is not found.
        """
        column_index = None
        if isinstance(column, int):
            column_index = column
        elif isinstance(column, str) :
            for col in range(self.columnCount()):
                header_text = self.horizontalHeaderItem(col).text()
                if header_text == column:
                    column_index = col
                    break

        if column_index is None:
            raise ValueError(f"Column '{column}' not found")

        # Loop through each row in the column
        column_data = []
        for row in range(self.rowCount()):
            item = self.item(row, column_index)  # Get QTableWidgetItem at (row, column_index)
            
            # Check if item exists (not None) and add its text to the list
            if item:
                column_data.append(item.text())
            else:
                column_data.append('')  # Handle empty cells if needed
        
        return column_data


class RotatedHeaderView(QHeaderView):
    """
    A custom QHeaderView that displays horizontal headers rotated by 90 degrees.

    This header view is useful for tables with many columns where horizontal space
    is constrained. It transposes the size hint and rotates the header text during
    painting to display the headers vertically.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget (typically a QTableView).

    Attributes
    ----------
    orientation : Qt.Orientation
        The orientation of the header view. Fixed to Qt.Horizontal.
    minimumSectionSize : int
        The minimum size of each header section, set to 20 pixels.

    Methods
    -------
    paintSection(painter, rect, logicalIndex)
        Paints a rotated header section by -90 degrees.
    minimumSizeHint()
        Returns the transposed minimum size hint for the rotated layout.
    sectionSizeFromContents(logicalIndex)
        Returns the transposed section size to accommodate vertical text.
    """
    def __init__(self, parent=None):
        super(RotatedHeaderView, self).__init__(Qt.Orientation.Horizontal, parent)
        self.setMinimumSectionSize(20)

    def paintSection(self, painter, rect, logicalIndex ):
        """
        Paint a single section of the header, rotating the text by -90 degrees.

        Parameters
        ----------
        painter : QPainter
            The painter used to draw the section.
        rect : QRect
            The bounding rectangle of the section.
        logicalIndex : int
            The index of the section being painted.
        """
        if painter:
            painter.save()
            # translate the painter to the appropriate position
            painter.translate(rect.x(), rect.y() + rect.height())
            painter.rotate(-90)  # rotate by -90 degrees
            # and have parent code paint at this location
            newrect = QRect(0,0,rect.height(),rect.width())
            super(RotatedHeaderView, self).paintSection(painter, newrect, logicalIndex)
            painter.restore()

    def minimumSizeHint(self):
        """
        Return the minimum size hint for the header.

        Returns
        -------
        QSize
            The minimum size hint, transposed due to rotation.
        """
        size = super(RotatedHeaderView, self).minimumSizeHint()
        size.transpose()
        return size

    def sectionSizeFromContents(self, logicalIndex):
        """
        Return the size of a section, adjusted for rotated text.

        Parameters
        ----------
        logicalIndex : int
            The index of the section.

        Returns
        -------
        QSize
            The size of the section, transposed for vertical layout.
        """
        size = super(RotatedHeaderView, self).sectionSizeFromContents(logicalIndex)
        size.transpose()
        return size
    
class StandardItem(QStandardItem):
    """Extends properties of QStandardItem for QTreeView and QList items.

    Parameters
    ----------
    txt : str, optional
        Text displayed in tree or list, by default ``''``
    font_size : int, optional
        fontsize, by default ``10``
    set_bold : bool, optional
        Bold tree font when ``True``, by default ``False``
    checkable : bool, optional
        Adds a checkbox to the item when ``True``, by default ``False``
    checked : bool, optional
        Initial check state, only meaningful when `checkable` is ``True``,
        by default ``False``
    """
    def __init__(self, txt='', font_size=10, set_bold=False, data=None, checkable=False, checked=False):
        super().__init__()

        # Set item font
        fnt = QFont()
        fnt.setPointSize(font_size)
        fnt.setBold(set_bold)

        self.setEditable(False)
        self.setText(txt)
        self.setFont(fnt)
        if data is not None:
            self.setData(data)
        if checkable:
            self.setCheckable(True)
            self.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

class CustomTreeView(QTreeView):
    """
    A customized QTreeView widget for managing a hierarchical tree structure.

    Provides functionality to create branches and leaves in a QStandardItemModel-based tree,
    search for items, retrieve paths and associated data, sort branches, and handle UI events.
    
    Attributes
    ----------
    treeModel : QStandardItemModel
        The data model used for the tree.
    root_node : QStandardItem
        The invisible root node of the tree model.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget, by default None.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.treeModel = QStandardItemModel()
        self.root_node = self.treeModel.invisibleRootItem()
        self.setModel(self.treeModel)
    
    def branch_exists(self, parent_item, branch_name):
        """
        Check if a branch with a given name exists under the specified parent item.

        Parameters
        ----------
        parent_item : QStandardItem
            The item to search under.
        branch_name : str
            The name of the branch to look for.

        Returns
        -------
        QStandardItem or None
            The branch item if found, otherwise None.
        """
        for row in range(parent_item.rowCount()):
            item = parent_item.child(row)
            if item.text() == branch_name:
                return item  # Return the branch if found
        return None  # Branch not found
    
    def add_branch(self, parent_item, branch_name, data=None):
        """
        Add a new branch to the tree under the specified parent.

        Parameters
        ----------
        parent_item : QStandardItem
            The parent item to add the branch to.
        branch_name : str
            The name of the new branch.
        data : any, optional
            Optional data to associate with the branch.

        Returns
        -------
        QStandardItem
            The created branch item.
        """
        branch_item = StandardItem(branch_name, 10, True, data)
        parent_item.appendRow(branch_item)
        return branch_item
    
    def add_leaf(self, branch_item, leaf_name, data=None, checkable=False, checked=False):
        """
        Add a new leaf to a branch.

        Parameters
        ----------
        branch_item : QStandardItem
            The branch item to which the leaf will be added.
        leaf_name : str
            The name of the new leaf.
        data : any, optional
            Optional data to associate with the leaf.
        checkable : bool, optional
            Adds a checkbox to the leaf when ``True``, by default ``False``.
        checked : bool, optional
            Initial check state, only meaningful when `checkable` is ``True``,
            by default ``False``.

        Returns
        -------
        QStandardItem
            The created leaf item.
        """
        leaf_item = StandardItem(leaf_name, 10, False, data, checkable=checkable, checked=checked)
        branch_item.appendRow(leaf_item)
        return leaf_item

    def get_item_path(self, item):
        """
        Return the full path of an item as a list from root to the given item.

        Parameters
        ----------
        item : QStandardItem
            The item whose path is to be retrieved.

        Returns
        -------
        list of str
            A list representing the hierarchy from root to the item.
        """
        path = []
        while item is not None:
            path.insert(0, item.text())
            item = item.parent()
        return path
    
    def get_leaf_data(self, leaf_item):
        """
        Return the full path of an item as a list from root to the given item.

        Parameters
        ----------
        item : QStandardItem
            The item whose path is to be retrieved.

        Returns
        -------
        list of str
            A list representing the hierarchy from root to the item.
        """
        return leaf_item.data()
    
    def find_leaf(self, branch_item, leaf_name):
        """
        Find a leaf under a branch by its name.

        Parameters
        ----------
        branch_item : QStandardItem
            The branch item to search within.
        leaf_name : str
            The name of the leaf to find.

        Returns
        -------
        QStandardItem or None
            The leaf item if found, otherwise None.
        """
        for row in range(branch_item.rowCount()):
            leaf = branch_item.child(row)
            if leaf.text() == leaf_name:
                return leaf
        return None

    def sort_branch(self, branch, order_list):
        """
        Sorts a branch in the treeView given an ordered list.

        Parameters
        ----------
        branch : QStandardItem
            Branch to sort leaf items.
        order_list : list
            The desired order for the leaf items.
        """        
        # Collect all children (leaves) under the branch into a list
        leaf_items = []
        for i in range(branch.rowCount()):
            leaf_items.append(branch.takeChild(i))
        
        # Sort the leaves based on the provided order list
        # Items not in order_list will be placed at the end
        leaf_items.sort(key=lambda x: order_list.index(x.text()) if x.text() in order_list else len(order_list))

        # Remove the items within the branch first and then replace it with the sorted ones
        branch.removeRows(0, branch.rowCount())
        
        # Add sorted items back to the branch
        for i, leaf in enumerate(leaf_items):
            branch.insertRow(i, leaf)

    def on_double_click(self, index):
        """
        Handle a double-click event on an item in the tree.

        Parameters
        ----------
        index : QModelIndex
            Index of the clicked item.
        """
        item = self.treeModel.itemFromIndex(index)
        item_path = self.get_item_path(item)
        leaf_data = self.get_leaf_data(item)
        log(f"Double-clicked on: {item_path}, Data: {leaf_data}", prefix="UI")

    def clear_tree(self):
        """
        Clears all items from the tree model.
        """
        try:
            self.treeModel.clear()
        except Exception as e:
            log(f"Error while clearing model: {e}", prefix="Error")

class CustomComboBox(QComboBox):
    """
    A QComboBox subclass with support for dynamic item updates before showing the popup.

    This custom combo box allows you to define a callback function that is executed
    each time the combo box is about to display its dropdown list. This is useful for
    updating the list of items dynamically based on application state.

    Attributes
    ----------
    popup_callback : callable or None
        A function to be executed immediately before the popup is shown. Typically used
        to refresh or modify the items in the combo box.

    Methods
    -------
    allItems() -> list[str]
        Returns a list of all item texts currently in the combo box.
    showPopup()
        Overrides the base class method to invoke the callback (if set) before showing the popup.

    Parameters
    ----------
    popup_callback : callable, optional
        A function that updates the combo box items before display. Default is None.
    *args, **kwargs : 
        Additional arguments passed to the QComboBox constructor.

    Examples
    --------

    .. code-block:: python
        def refresh_items():
            combo.clear()
            combo.addItems(["A", "B", "C"])

        combo = CustomComboBox(popup_callback=refresh_items)
        combo.show()  # Each time the dropdown is opened, items are refreshed
    """
    def __init__(self, popup_callback=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.popup_callback = popup_callback

    def allItems(self):
        """Return a list of all item texts in the combobox."""
        return [self.itemText(i) for i in range(self.count())]

    def showPopup(self):
        """
        Executes the popup callback (if any) before showing the dropdown list.

        Overrides the QComboBox method to inject behavior that updates the
        combobox contents just before it is shown to the user.
        """
        if self.popup_callback:
            self.popup_callback()
        super().showPopup()

    def setActive(self, active: bool):
        """Simplifies setting visibility and enabling of CustomComboBox

        Parameters
        ----------
        active : bool
            Sets the state of visibility and enabling of widget
        """
        self.setVisible(active)
        self.setEnabled(active)


class SpinComboBox(QWidget):
    """
    A QSpinBox coupled to a QComboBox, so the spinbox's value always matches
    the combobox's selected index.

    Changing either widget updates the other: stepping the spinbox moves
    the combobox selection, and picking a combobox item moves the spinbox
    to the matching index.

    Parameters
    ----------
    items : list of str, optional
        Initial items to populate the combobox with, by default None.
    parent : QWidget, optional
        Parent widget, by default None.

    Signals
    -------
    currentIndexChanged(int)
        Emitted with the new index whenever the spinbox or the combobox
        changes, regardless of which one triggered the change.
    currentTextChanged(str)
        Emitted with the new combobox text whenever the selection changes.

    Attributes
    ----------
    spin_box : QSpinBox
        The wrapped spin box.
    combo_box : QComboBox
        The wrapped combo box.
    """
    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.spin_box = QSpinBox(self)
        self.combo_box = QComboBox(self)

        if items:
            self.combo_box.addItems(items)
        self._update_spinbox_range()

        self.spin_box.valueChanged.connect(self._sync_combobox_from_spinbox)
        self.combo_box.currentIndexChanged.connect(self._sync_spinbox_from_combobox)
        self.combo_box.currentTextChanged.connect(self.currentTextChanged.emit)

        layout.addWidget(self.combo_box)
        layout.addWidget(self.spin_box)

    def _update_spinbox_range(self):
        """Resize the spinbox range to match the combobox's item count."""
        count = self.combo_box.count()
        self.spin_box.blockSignals(True)
        self.spin_box.setMinimum(0)
        self.spin_box.setMaximum(max(count - 1, 0))
        self.spin_box.blockSignals(False)

    def _sync_combobox_from_spinbox(self, index):
        """Move the combobox selection to match a new spinbox value."""
        if self.combo_box.currentIndex() != index:
            self.combo_box.blockSignals(True)
            self.combo_box.setCurrentIndex(index)
            self.combo_box.blockSignals(False)
        self.currentIndexChanged.emit(index)

    def _sync_spinbox_from_combobox(self, index):
        """Move the spinbox value to match a new combobox selection."""
        if self.spin_box.value() != index:
            self.spin_box.blockSignals(True)
            self.spin_box.setValue(index)
            self.spin_box.blockSignals(False)
        self.currentIndexChanged.emit(index)

    def setItems(self, items):
        """Replace the combobox contents, clamping the current index to the new range.

        Parameters
        ----------
        items : list of str
            New items for the combobox.
        """
        current = self.currentIndex()
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        self.combo_box.addItems(items)
        self.combo_box.blockSignals(False)
        self._update_spinbox_range()
        self.setCurrentIndex(max(0, min(current, self.combo_box.count() - 1)))

    def addItem(self, text):
        """Append a single item to the combobox and grow the spinbox range."""
        self.combo_box.addItem(text)
        self._update_spinbox_range()

    def addItems(self, texts):
        """Append multiple items to the combobox and grow the spinbox range."""
        self.combo_box.addItems(texts)
        self._update_spinbox_range()

    def allItems(self):
        """Return a list of all item texts in the combobox."""
        return [self.combo_box.itemText(i) for i in range(self.combo_box.count())]

    def currentIndex(self) -> int:
        """Return the current combobox index."""
        return self.combo_box.currentIndex()

    def setCurrentIndex(self, index: int):
        """Set the current combobox index."""
        self.combo_box.setCurrentIndex(index)

    def currentText(self) -> str:
        """Return the currently selected combobox text."""
        return self.combo_box.currentText()


class CustomDockWidget(QDockWidget):
    """
    A custom QDockWidget that hides instead of closing when the user clicks the close button.

    This subclass of QDockWidget overrides the standard close behavior so that the widget
    is simply hidden rather than destroyed. This allows the widget to be shown again later
    without needing to be re-instantiated.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget, typically a QMainWindow. Default is None.

    Methods
    -------
    closeEvent(event: QEvent)
        Hides the dock instead of closing it when the user clicks the close button.
    """
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent)

        self.show()

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)

    def closeEvent(self, event):
        """
        Override the default close event to hide the dock widget instead of closing it.

        This prevents the widget from being destroyed and allows it to be shown again later
        via `widget.show()`.

        Parameters
        ----------
        event : QEvent
            The close event triggered by the user action.
        """
        self.hide()
        if event:
            event.ignore()  # Ignore the close event to prevent the widget from being removed.

class ToggleSwitch(QWidget):
    """
    A custom toggle switch widget with animated transitions and customizable colors.

    This widget mimics a modern on/off switch, commonly used in mobile and web UIs. It supports 
    smooth animated transitions between the "on" and "off" states, emits a signal when toggled, 
    and provides optional customization for height, animation duration, and colors.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget, by default None.
    height : int, optional
        Height of the toggle switch. The width is automatically set to twice the height. Default is 24.
    duration : int, optional
        Duration of the toggle animation in milliseconds. Default is 100.
    fg_color : str, optional
        Foreground color (thumb/slider) in hex format. Default is "#f0f0f0".
    bg_left_color : str, optional
        Background color when the switch is in the "off" position. Default is "#ffffff".
    bg_right_color : str, optional
        Background color when the switch is in the "on" position. Default is "#478ae4".

    Signals
    -------
    stateChanged : bool
        Emitted when the switch state changes.

    Attributes
    ----------
    thumb_pos : float
        Position of the thumb (used for animation).
    
    Methods
    -------
    toggle()
        Toggles the switch state and emits the `stateChanged` signal.
    setChecked(checked)
        Sets the checked state and animates the thumb.
    isChecked() -> bool
        Returns the current checked state.
    """
    stateChanged = pyqtSignal(bool)  # Signal emitted when the state changes

    def __init__(self, parent=None, height=24, duration=100, fg_color="#f0f0f0", bg_left_color="#a8b078", bg_right_color="#478ae4"):
        super().__init__(parent)
        self._height = height
        self._width = height * 2
        self.setFixedSize(self._width, self._height)

        self._checked = False

        self._thumb_pos = 2  # Initial position
        self.duration = duration

        self._animation = QPropertyAnimation(self, b"thumb_pos")
        self._animation.setDuration(duration)  # Smooth animation

        if is_valid_hex_color(fg_color):
            self.fg_color = fg_color
        else:
            self.fg_color = "#f0f0f0"

        # background colors
        if is_valid_hex_color(bg_left_color):
            self.bg_left_color = bg_left_color
        else:
            self.bg_left_color = "#ffffff"
        if is_valid_hex_color(bg_right_color):
            self.bg_right_color = bg_right_color
        else:
            self.bg_right_color="#478ae4"

    def toggle(self):
        """Toggle switch state and emit signal"""
        self._checked = not self._checked
        self._animation.setStartValue(self._thumb_pos)
        self._animation.setEndValue(self._width - self._height + 2 if self._checked else 2)
        self._animation.start()

        self.stateChanged.emit(self._checked)  # Emit signal

    def setChecked(self, checked: bool):
        """Sets the checked state of the toggle switch and triggers the animation

        Parameters
        ----------
        checked : bool
            New check state of the toggle switch.
        """
        # Accept both bool and Qt.CheckState
        if isinstance(checked, Qt.CheckState):
            checked = (checked == Qt.CheckState.Checked)
        if self._checked != checked:
            self._checked = checked
            start = self._thumb_pos
            end = self._width - self._height + 2 if self._checked else 2
            self._animation.stop()
            self._animation.setStartValue(start)
            self._animation.setEndValue(end)
            self._animation.start()
            self.stateChanged.emit(self._checked)


    def isChecked(self) -> bool:
        """Return the current state of the toggle switch.
        
        Returns
        -------
        bool
            Returns checked state of the toggle switch
        """
        return self._checked

    def mousePressEvent(self, event):
        """
        Handles mouse press events to toggle the switch state when clicked.

        If the left mouse button is pressed, this method toggles the checked state of the switch.

        Parameters
        ----------
        event : QMouseEvent
            The mouse event triggered by the user interaction.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def sizeHint(self):
        """Returns the size of the toggle switch.
        
        Returns
        -------
        size : QSize
            Returns the size of the toggle switch.
        """
        return self.size()

    def paintEvent(self, event):
        """Draw the toggle switch.

        Draws the toggle switch.

        Parameters
        ----------
        event : QEvent
        """
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Draw background
            bg_color = QColor(self.bg_right_color if self._checked else self.bg_left_color)
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self._width, self._height, self._height // 2, self._height // 2)


            # Draw the thumb (slider)
            thumb_diameter = self._height - 4
            painter.setBrush(QColor(self.fg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(int(self._thumb_pos), 2, thumb_diameter, thumb_diameter))
        finally:
            painter.end()

    def get_thumb_pos(self):
        """Returns the thumb position."""
        return self._thumb_pos

    def set_thumb_pos(self, pos):
        """Sets the thumb position.
        
        Paramters
        ---------
        pos : int
            Thumb position"""
        self._thumb_pos = pos
        self.update()  # Redraw switch

    thumb_pos = pyqtProperty(float, get_thumb_pos, set_thumb_pos)


class CustomAction(QAction):
    """An action that changes icons when checked or the theme changes from light to dark

    Attributes
    ----------
    self._light_icon_unchecked : QIcon
        Icon for light, unchecked state
    self._light_icon_checked : QIcon
        Icon for light, checked state
    self._dark_icon_unchecked : QIcon
        Icon for dark, unchecked state
    self._dark_icon_checked : QIcon
        Icon for dark, checked state
    self._current_theme : str
        "light" or "dark" color theme

    Parameters
    ----------
    text: str
        Text to display by widget
    light_icon_unchecked : str
        Unchecked icon filename for light color theme.
    light_icon_checked : str | None
        Checked icon filename for light color theme.  If None, the icon is not checkable
    dark_icon_unchecked : str
        Unchecked icon filename for dark color theme.
    dark_icon_checked : str | None
        Checked icon filename for dark color theme. If None, the icon is not checkable
    button_size : int
        Size of button in pt.
    icon_size : int
        Size of icon on button in pt.
    parent : QToolButton
        Tool button to set icons.

    Methods
    -------
    set_theme()
        Updates light or dark theme icons
    update_icon()
        Update the icon based on the button's checked state.
    """
    def __init__(
        self,
        text: str,
        light_icon_unchecked: str,
        light_icon_checked: str | None=None,
        dark_icon_unchecked: str | None=None,
        dark_icon_checked: str | None=None,
        icon_text: str | None=None,
        parent=None,
    ):
        super().__init__(text, parent)

        if icon_text is not None and icon_text != text:
            self.setIconText(icon_text)

        def load_icon(filename: str|None, fallback: QIcon=None) -> QIcon:
            """Sets up the QIcon for a given light/dark, checked/unchecked state.

            Parameters
            ----------
            filename : str | None
                Icon filename for a state
            fallback : QIcon, optional
                Fallback icon for a state, by default None

            Returns
            -------
            QIcon
                Icon to use for a given states
            """
            if filename:
                path = ICONPATH / filename
                if path.exists():
                    return QIcon(str(path))
                else:
                    log(f"Icon not found: {path}", prefix="Warning")
            return fallback if fallback else QIcon()

        # Load icons
        self._light_icon_unchecked = load_icon(light_icon_unchecked)
        self._dark_icon_unchecked = load_icon(dark_icon_unchecked, self._light_icon_unchecked)

        if light_icon_checked:
            self.setCheckable(True)
            self._light_icon_checked = load_icon(light_icon_checked, self._light_icon_unchecked)
            self._dark_icon_checked = load_icon(dark_icon_checked, self._light_icon_checked)
        else:
            self.setCheckable(False)
            self._light_icon_checked = None
            self._dark_icon_checked = None

        self._current_theme = "light"

        # Button visual setup
        self.setFont(default_font())

        self.setIconVisibleInMenu(False)

        self.setChecked(False)
        self.update_icon()

        self.triggered.connect(self.update_icon)

    def set_theme(self, theme: str):
        """Updates the icon to light/dark theme."""
        if theme in ["light", "dark"]:
            self._current_theme = theme
            self.update_icon()

    def update_icon(self):
        """Update the icon based on the button's checked state and theme."""
        icon = None
        match self._current_theme:
            case "light":
                icon = self._light_icon_checked if self.isCheckable() and self.isChecked() else self._light_icon_unchecked
            case "dark":
                icon = self._dark_icon_checked if self.isCheckable() and self.isChecked() else self._dark_icon_unchecked

        if icon:
            self.setIcon(icon)

class CustomToolButton(QToolButton):
    """A button that changes icons when checked or the theme changes from light to dark

    Attributes
    ----------
    self._light_icon_unchecked : QIcon
        Icon for light, unchecked state
    self._light_icon_checked : QIcon
        Icon for light, checked state
    self._dark_icon_unchecked : QIcon
        Icon for dark, unchecked state
    self._dark_icon_checked : QIcon
        Icon for dark, checked state
    self._current_theme : str
        "light" or "dark" color theme

    Parameters
    ----------
    light_icon_unchecked : str
        Unchecked icon filename for light color theme.
    light_icon_checked : str | None
        Checked icon filename for light color theme.  If None, the icon is not checkable
    dark_icon_unchecked : str
        Unchecked icon filename for dark color theme.
    dark_icon_checked : str | None
        Checked icon filename for dark color theme. If None, the icon is not checkable
    button_size : int
        Size of button in pt.
    icon_size : int
        Size of icon on button in pt.
    parent : QToolButton
        Tool button to set icons.

    Methods
    -------
    set_theme()
        Updates light or dark theme icons
    update_icon()
        Update the icon based on the button's checked state.
    """
    def __init__(
        self,
        text: str,
        light_icon_unchecked: str,
        light_icon_checked: str | None=None,
        dark_icon_unchecked: str | None=None,
        dark_icon_checked: str | None=None,
        button_size: int = 32,
        icon_size: int = 26,
        parent=None,
    ):
        super().__init__(parent)

        self.setText(text)

        def load_icon(filename: str | None, fallback: QIcon=None) -> QIcon:
            """Sets up the QIcon for a given light/dark, checked/unchecked state.

            Parameters
            ----------
            filename : str | None
                Icon filename for a state
            fallback : QIcon, optional
                Fallback icon for a state, by default None

            Returns
            -------
            QIcon
                Icon to use for a given states
            """
            if filename:
                path = ICONPATH / filename
                if path.exists():
                    return QIcon(str(path))
                else:
                    log(f"Icon not found: {path}", prefix="Warning")
            return fallback if fallback else QIcon()

        # Load icons
        self._light_icon_unchecked = load_icon(light_icon_unchecked)
        self._dark_icon_unchecked = load_icon(dark_icon_unchecked, self._light_icon_unchecked)

        if light_icon_checked:
            self.setCheckable(True)
            self._light_icon_checked = load_icon(light_icon_checked, self._light_icon_unchecked)
            self._dark_icon_checked = load_icon(dark_icon_checked, self._light_icon_checked)
        else:
            self.setCheckable(False)
            self._light_icon_checked = None
            self._dark_icon_checked = None

        self._current_theme = "light"

        # Button visual setup
        self.setFixedSize(button_size, button_size)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFont(default_font())

        self.setChecked(False)
        self.update_icon()

        self.clicked.connect(self.update_icon)

    def set_theme(self, theme: str):
        """Updates the icon to light/dark theme."""
        if theme in ["light", "dark"]:
            self._current_theme = theme
            self.update_icon()

    def update_icon(self):
        """Update the icon based on the button's checked state and theme."""
        icon = None
        match self._current_theme:
            case "light":
                icon = self._light_icon_checked if self.isCheckable() and self.isChecked() else self._light_icon_unchecked
            case "dark":
                icon = self._dark_icon_checked if self.isCheckable() and self.isChecked() else self._dark_icon_unchecked

        if icon:
            self.setIcon(icon)

class _IndicatorCircle(QToolButton):
    """Private: the circle itself. Use :class:`IndicatorLight` instead.

    Implemented as a flat QToolButton that paints a solid color-filled
    circle instead of an icon.

    Statuses are looked up by key in ``status_dict``, a mapping of
    ``{status_key: {'tip_text': str, 'color': str}}``. Calling
    :meth:`set_status` with a key updates the circle's fill color and its
    tooltip to match that entry.

    Parameters
    ----------
    status_dict : dict, optional
        Mapping of status key to ``{'tip_text', 'color'}``, by default
        ``IndicatorLight.DEFAULT_STATUS_DICT``.
    status : str, optional
        Initial status key, looked up in ``status_dict``, by default None
        -- the indicator starts unset (neutral gray, no tooltip).
    size : int, optional
        Diameter of the circle in pixels, by default 16.
    parent : QWidget, optional
        Parent widget, by default None.

    Attributes
    ----------
    status_dict : dict
        Current mapping of status keys to their ``{'tip_text', 'color'}`` entries.
    status : str or None
        The currently active status key, or None if unset.
    """
    DEFAULT_STATUS_DICT = {
        'on': {'tip_text': 'On', 'color': 'green'},
        'off': {'tip_text': 'Off', 'color': 'red'},
    }

    def __init__(self, status_dict=None, status=None, size=16, parent=None):
        super().__init__(parent)

        self.status_dict = dict(status_dict) if status_dict else dict(self.DEFAULT_STATUS_DICT)
        self._status = None
        self._color = QColor('lightgray')
        self._diameter = size

        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")

        self.set_size(size)

        if status is not None:
            self.set_status(status)

    def set_size(self, size: int):
        """Set the indicator's diameter in pixels.

        Parameters
        ----------
        size : int
            New diameter, in pixels.
        """
        self._diameter = size
        self.setFixedSize(size, size)
        self.update()

    def add_status(self, key: str, tip_text: str, color: str):
        """Add or update a status entry in ``status_dict``.

        Parameters
        ----------
        key : str
            Status key.
        tip_text : str
            Tooltip text shown while this status is active.
        color : str
            Fill color while this status is active (any value QColor accepts,
            e.g. a name like ``'green'`` or a hex string like ``'#2ecc71'``).
        """
        self.status_dict[key] = {'tip_text': tip_text, 'color': color}
        if self._status == key:
            self.set_status(key)

    def set_status(self, status: str):
        """Set the current status, updating the fill color and tooltip.

        Parameters
        ----------
        status : str
            Key into ``status_dict``.

        Raises
        ------
        KeyError
            If ``status`` is not a key in ``status_dict``.
        """
        entry = self.status_dict[status]
        self._status = status
        color = QColor(entry.get('color', 'gray'))
        self._color = color if color.isValid() else QColor('gray')
        self.setToolTip(entry.get('tip_text', ''))
        self.update()

    @property
    def status(self):
        """str or None: The currently active status key, or None if unset."""
        return self._status

    def sizeHint(self):
        """Return the indicator's fixed size (diameter x diameter)."""
        return QSize(self._diameter, self._diameter)

    def paintEvent(self, event):
        """Paint a filled circle instead of the default button chrome.

        Parameters
        ----------
        event : QEvent
        """
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(self._color)
            painter.setPen(Qt.PenStyle.NoPen)
            d = min(self.width(), self.height())
            x = (self.width() - d) // 2
            y = (self.height() - d) // 2
            painter.drawEllipse(x, y, d, d)
        finally:
            painter.end()


class IndicatorLight(QWidget):
    """
    A small circular status light with an optional text label to its left,
    right, above, or below.

    The circle itself behaves as described in :class:`_IndicatorCircle`:
    statuses are looked up by key in ``status_dict``, and :meth:`set_status`
    updates the circle's fill color and tooltip to match. The label is
    independent of status -- it shows fixed text you set yourself (e.g. a
    caption like ``'CPU'``), and is left untouched by :meth:`set_status`.

    Parameters
    ----------
    status_dict : dict, optional
        Mapping of status key to ``{'tip_text', 'color'}``, by default
        ``IndicatorLight.DEFAULT_STATUS_DICT``.
    status : str, optional
        Initial status key, looked up in ``status_dict``, by default None
        -- the indicator starts unset (neutral gray, no tooltip).
    size : int, optional
        Diameter of the circle in pixels, by default 16.
    label : str, optional
        Caption text to display next to the light, by default None --
        no label is shown.
    label_position : str, optional
        Where the label sits relative to the light: ``'left'``, ``'right'``,
        ``'above'``, or ``'below'``. Only matters once a label is set.
        Default ``'left'``.
    parent : QWidget, optional
        Parent widget, by default None.

    Attributes
    ----------
    light : QToolButton
        The circular indicator itself.
    label : QLabel
        The caption label, hidden whenever its text is empty.
    status_dict : dict
        Current mapping of status keys to their ``{'tip_text', 'color'}`` entries.
    status : str or None
        The currently active status key, or None if unset.
    label_position : str
        Current label placement: ``'left'``, ``'right'``, ``'above'``, or ``'below'``.

    Examples
    --------

    .. code-block:: python

        light = IndicatorLight()
        light.set_status('on')

        light = IndicatorLight(
            status_dict={
                'ready': {'tip_text': 'Ready', 'color': '#2ecc71'},
                'busy': {'tip_text': 'Busy', 'color': '#f39c12'},
                'error': {'tip_text': 'Error', 'color': '#e74c3c'},
            },
            status='ready',
            size=12,
            label='Worker 1',
            label_position='right',
        )
    """
    DEFAULT_STATUS_DICT = _IndicatorCircle.DEFAULT_STATUS_DICT

    def __init__(self, status_dict=None, status=None, size=16, label=None, label_position='left', parent=None):
        super().__init__(parent)

        if label_position not in ('left', 'right', 'above', 'below'):
            raise ValueError("label_position must be 'left', 'right', 'above', or 'below'.")

        self.light = _IndicatorCircle(status_dict=status_dict, status=status, size=size, parent=self)
        self.label = QLabel('', self)
        self.label.setVisible(False)

        self._label_position = label_position
        self._rebuild_layout()

        if label is not None:
            self.set_label(label)

    def _rebuild_layout(self):
        """Recreate the layout so widget order matches ``label_position``."""
        old_layout = self.layout()
        if old_layout is not None:
            while old_layout.count():
                old_layout.takeAt(0)
            # Reparent the now-empty layout onto a throwaway widget so Qt
            # disposes of it -- `self` can't take a new layout while the
            # old one is still installed.
            QWidget().setLayout(old_layout)

        if self._label_position in ('left', 'right'):
            layout = QHBoxLayout()
        else:
            layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        widgets = (self.label, self.light) if self._label_position in ('left', 'above') else (self.light, self.label)
        for w in widgets:
            layout.addWidget(w)

        self.setLayout(layout)

    def set_label(self, text=None, position=None):
        """Set the label's text and, optionally, its position.

        Parameters
        ----------
        text : str, optional
            Caption to display. Empty or None hides the label, by default None.
        position : str, optional
            One of ``'left'``, ``'right'``, ``'above'``, ``'below'``. Leaves
            the current position unchanged if not given, by default None.
        """
        if position is not None:
            self.set_label_position(position)
        self.label.setText(text or '')
        self.label.setVisible(bool(text))

    def set_label_position(self, position: str):
        """Move the label to a different side of the light.

        Parameters
        ----------
        position : str
            One of ``'left'``, ``'right'``, ``'above'``, ``'below'``.
        """
        if position not in ('left', 'right', 'above', 'below'):
            raise ValueError("label_position must be 'left', 'right', 'above', or 'below'.")
        if position == self._label_position:
            return
        self._label_position = position
        self._rebuild_layout()

    @property
    def label_position(self) -> str:
        """str: Current label placement ('left', 'right', 'above', or 'below')."""
        return self._label_position

    def set_size(self, size: int):
        """Set the light's diameter in pixels."""
        self.light.set_size(size)

    def add_status(self, key: str, tip_text: str, color: str):
        """Add or update a status entry in ``status_dict``. See :meth:`_IndicatorCircle.add_status`."""
        self.light.add_status(key, tip_text, color)

    def set_status(self, status: str):
        """Set the current status, updating the light's fill color and tooltip.

        Parameters
        ----------
        status : str
            Key into ``status_dict``.

        Raises
        ------
        KeyError
            If ``status`` is not a key in ``status_dict``.
        """
        self.light.set_status(status)

    @property
    def status(self):
        """str or None: The currently active status key, or None if unset."""
        return self.light.status

    @property
    def status_dict(self):
        """dict: Current mapping of status keys to their ``{'tip_text', 'color'}`` entries."""
        return self.light.status_dict

class CustomSlider(QWidget):
    """
    A custom slider widget that combines a horizontal QSlider and a QLabel.

    This widget displays the current slider value in a label and emits custom signals
    for common slider events. It supports setting initial value, range, and step size.

    Parameters
    ----------
    min_value : float, optional
        Minimum value of the slider range (default is 0).
    max_value : float, optional
        Maximum value of the slider range (default is 100).
    step : float, optional
        Increment between values (default is 1).
    initial_value : float, optional
        Initial slider value (default is 50).
    precision : int, optional
        Number of digits used to format the label (default is 1); interpreted as
        significant digits unless ``fixed_point`` is ``True``.
    fixed_point : bool, optional
        If ``True``, the label always shows exactly ``precision`` digits after the
        decimal point, rather than ``precision`` significant digits -- appropriate
        for fractional-step sliders (default is False).
    parent : QWidget, optional
        Parent widget (default is None).

    Signals
    -------
    valueChanged(int)
        Emitted when the slider's value changes.
    sliderMoved(int)
        Emitted while the slider is being dragged.
    sliderReleased(int)
        Emitted when the slider handle is released.
    sliderPressed(int)
        Emitted when the slider handle is pressed.
    """
    valueChanged = pyqtSignal(int)
    sliderMoved = pyqtSignal(int)
    sliderReleased = pyqtSignal(int)
    sliderPressed = pyqtSignal(int)

    def __init__(self, min_value=0, max_value=100, step=1, initial_value=50, precision=1, fixed_point=False, orientation="horizontal", label_position="low", parent=None):
        super().__init__(parent)
        
        self._min_value = min_value
        self._max_value = max_value
        self._step = step
        self._precision = precision
        self._scale = int(1 / step)  

        layout = None
        if orientation == "horizontal":
            layout = QHBoxLayout()
        elif orientation == "vertical":
            layout = QVBoxLayout()
        else:
            raise ValueError("Orientation must be 'horizontal' or 'vertical'.")
        
        # Create label to display slider value
        self.label = CustomLineEdit(self,value=initial_value, precision=precision, fixed_point=fixed_point)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMaximumWidth(30)
        self.label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        
        # Create slider
        if orientation == "horizontal":
            self.slider = QSlider(Qt.Orientation.Horizontal, parent=self)
        else:
            self.slider = QSlider(Qt.Orientation.Vertical, parent=self)
        self.slider.setMinimum(0)
        self.slider.setMaximum(int((self.max_value - self.min_value) * self._scale))
        self.slider.setSingleStep(1)
        self.slider.setValue(int((initial_value - self.min_value) * self._scale))
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # connect label to slider
        self.label.editingFinished.connect(self.handle_label_change)
        
        # Connect slider movement to label update
        self.slider.valueChanged.connect(self.update_label)
        self.slider.valueChanged.connect(self.valueChanged.emit)  # Emit custom signal
        self.slider.sliderMoved.connect(self.update_label)
        self.slider.sliderMoved.connect(self.sliderMoved.emit)
        # QSlider.sliderPressed/sliderReleased are argument-less Qt signals
        # (unlike valueChanged/sliderMoved, which carry the int position) --
        # connecting either straight to a slot/signal that expects the value
        # (update_label(int_value), or this widget's own pyqtSignal(int)
        # versions' .emit) raises a TypeError the moment it actually fires,
        # since zero args reach a callable that requires one. Wrap in a
        # lambda that supplies the slider's current value explicitly.
        self.slider.sliderReleased.connect(lambda: self.update_label(self.slider.value()))
        self.slider.sliderReleased.connect(lambda: self.sliderReleased.emit(self.slider.value()))
        self.slider.sliderPressed.connect(lambda: self.sliderPressed.emit(self.slider.value()))
        
        # Add widgets to layout
        if (label_position == "low" and orientation == "horizontal") or (label_position == "high" and orientation == "vertical"):
            layout.addWidget(self.label)
            layout.addWidget(self.slider)
        elif (label_position == "high" and orientation == "horizontal") or (label_position == "low" and orientation == "vertical"):
            layout.addWidget(self.slider)
            layout.addWidget(self.label)
        else:
            raise ValueError("Label position must be 'low' or 'high'.")
        
        self.setLayout(layout)

    @property
    def min_value(self):
        return self._min_value

    @min_value.setter
    def min_value(self, new_value):
        if not new_value or not isinstance(new_value, float):
            raise TypeError('CustomSlider minimum value must be a float.')

        if new_value == self._min_value:
            return
        elif new_value > self.max_value:
            raise ValueError("CustomSlider minimum bound must be greater than the maximum bound.")

        self._min_value = new_value
        self._update_slider_range()

    @property
    def max_value(self):
        return self._max_value

    @max_value.setter
    def max_value(self, new_value):
        if not new_value or not isinstance(new_value, float):
            raise TypeError('CustomSlider maximum bound must be a float.')

        if new_value == self._max_value:
            return
        elif new_value < self.min_value:
            raise ValueError("CustomSlider maximum bound must be greater than the minimum bound.")
        
        self._max_value = new_value
        self._update_slider_range()

    @property
    def step(self):
        return self._step
    
    @step.setter
    def step(self, new_value):
        if not new_value or not isinstance(new_value, float):
            raise TypeError('CustomSlider step must be a float.')

        if new_value == self._step:
            return

        self._step = new_value
        self._scale = int(1 / self._step)
        self._update_slider_range()

    def _update_slider_range(self):
        """Update slider range and current value based on min, max, step."""
        self._scale = int(1 / self._step)

        self.slider.blockSignals(True)  # avoid emitting signals while adjusting
        self.slider.setMinimum(0)
        self.slider.setMaximum(int((self.max_value - self.min_value) * self._scale))
        self.slider.setSingleStep(1)
        # Optionally: clamp current value if needed
        current_value = self.value()
        clamped_value = max(min(current_value, self.max_value), self.min_value)
        self.setValue(clamped_value)
        self.slider.blockSignals(False)
        # setValue() ran with signals blocked, so update_label (normally driven by
        # slider.valueChanged) never fired -- sync the label explicitly.
        self.update_label(self.slider.value())

    def handle_label_change(self):
        """
        Updates the slider value from the label after editing is finished.
        """
        try:
            value = float(self.label.value)
        except (ValueError, TypeError):
            return

        # Clamp to range
        value = max(min(value, self.max_value), self.min_value)
        int_value = int(round((value - self.min_value) * self._scale))
        self.slider.setValue(int_value)
    
    def update_label(self, int_value):
        """
        Updates the label value to display the slider's value.

        Parameters
        ----------
        value : int
            Current value of the slider.
        """
        true_value = self.min_value + (int_value / self._scale)
        self.label.value = true_value
    
    def setTickInterval(self, new_interval):
        if self._scale <= 0:
            return
        tick_interval = int(new_interval * self._scale)
        self.slider.setTickInterval(tick_interval) 
    
    def setValue(self, float_value):
        """
        Sets the slider value.

        Parameters
        ----------
        value : int
            Desired slider value.
        """
        int_value = int(round((float_value - self.min_value) * self._scale))
        self.slider.setValue(int_value)
    
    def value(self):
        """
        Returns the current value of the slider.

        Returns
        -------
        int
            Current slider value.
        """
        return self.min_value + (self.slider.value() / self._scale)


class DoubleSlider(QWidget):
    """
    A dual-slider widget with editable input fields for setting a value range.

    This widget features two horizontal QSliders for setting a minimum and maximum value,
    along with associated QLineEdits to allow manual text input. It emits combined signals
    when either slider changes, is moved, or released.

    Parameters
    ----------
    min_value : int, optional
        Minimum allowed slider value (default is 0).
    max_value : int, optional
        Maximum allowed slider value (default is 100).
    step : int, optional
        Step size between values (default is 1).
    initial_left : int, optional
        Initial value for the left (lower) slider (default is 25).
    initial_right : int, optional
        Initial value for the right (upper) slider (default is 75).
    parent : QWidget, optional
        Parent widget (default is None).

    Signals
    -------
    valueChanged(int, int)
        Emitted when either slider value changes.
    sliderMoved(int, int)
        Emitted while either slider is being dragged.
    sliderReleased(int, int)
        Emitted when either slider handle is released.
    sliderPressed(int, int)
        Emitted when either slider handle is pressed.
    """
    valueChanged = pyqtSignal(int, int)  # Signal emitting both slider values
    sliderMoved = pyqtSignal(int, int)  # Signal emitting both slider values
    sliderReleased = pyqtSignal(int, int)  # Signal emitting both slider values
    sliderPressed = pyqtSignal(int, int)  # Signal emitting both slider values

    def __init__(self, min_value=0, max_value=100, step=1, initial_left=25, initial_right=75, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout()
        
        # Create horizontal layout for sliders
        self.slider_layout = QHBoxLayout()
        
        # Create left slider
        self.left_slider = QSlider(Qt.Orientation.Horizontal)
        self.left_slider.setMinimum(min_value)
        self.left_slider.setMaximum(max_value)
        self.left_slider.setSingleStep(step)
        self.left_slider.setValue(initial_left)
        
        # Create right slider
        self.right_slider = QSlider(Qt.Orientation.Horizontal)
        self.right_slider.setMinimum(min_value)
        self.right_slider.setMaximum(max_value)
        self.right_slider.setSingleStep(step)
        self.right_slider.setValue(initial_right)
        
        # Connect slider changes
        self.left_slider.valueChanged.connect(self.update_values)
        self.right_slider.valueChanged.connect(self.update_values)
        self.left_slider.valueChanged.connect(self.valueChanged.emit)
        self.right_slider.valueChanged.connect(self.valueChanged.emit)

        self.left_slider.sliderMoved.connect(self.update_values)
        self.right_slider.sliderMoved.connect(self.update_values)
        self.left_slider.sliderMoved.connect(self.sliderMoved.emit)
        self.right_slider.sliderMoved.connect(self.sliderMoved.emit)

        self.left_slider.sliderReleased.connect(self.update_values)
        self.right_slider.sliderReleased.connect(self.update_values)
        self.left_slider.sliderReleased.connect(self.sliderReleased.emit)
        self.right_slider.sliderReleased.connect(self.sliderReleased.emit)

        self.left_slider.sliderPressed.connect(self.sliderPressed.emit)
        self.right_slider.sliderPressed.connect(self.sliderPressed.emit)
        
        self.slider_layout.addWidget(self.left_slider)
        self.slider_layout.addWidget(self.right_slider)
        
        # Create horizontal layout for line edits
        self.input_layout = QHBoxLayout()
        
        self.left_input = QLineEdit(str(initial_left))
        self.right_input = QLineEdit(str(initial_right))
        
        self.left_input.setFixedWidth(50)
        self.right_input.setFixedWidth(50)
        
        self.left_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.left_input.editingFinished.connect(self.update_sliders)
        self.right_input.editingFinished.connect(self.update_sliders)
        
        self.input_layout.addWidget(self.left_input)
        self.input_layout.addStretch()
        self.input_layout.addWidget(self.right_input)
        
        layout.addLayout(self.slider_layout)
        layout.addLayout(self.input_layout)
        
        self.setLayout(layout)
    
    def update_values(self):
        """
        Updates the line edits to reflect the slider values and emits the `valueChanged` signal.
        """
        left_value = self.left_slider.value()
        right_value = self.right_slider.value()
        
        self.left_input.setText(str(left_value))
        self.right_input.setText(str(right_value))
        
        self.valueChanged.emit(left_value, right_value)
    
    def update_sliders(self):
        """
        Updates slider values based on text input in the line edits. Invalid input is ignored.
        """
        try:
            left_value = int(self.left_input.text())
            right_value = int(self.right_input.text())
            self.left_slider.setValue(left_value)
            self.right_slider.setValue(right_value)
        except ValueError:
            pass
    
    def setMinimum(self, value):
        """
        Sets the minimum value for both sliders.

        Parameters
        ----------
        value : int
            Minimum value.
        """
        self.left_slider.setMinimum(value)
        self.right_slider.setMinimum(value)
    
    def setMaximum(self, value):
        """
        Sets the maximum value for both sliders.

        Parameters
        ----------
        value : int
            Maximum value.
        """
        self.left_slider.setMaximum(value)
        self.right_slider.setMaximum(value)
    
    def setStep(self, value):
        """
        Sets the step size for both sliders.

        Parameters
        ----------
        value : int
            Step size.
        """
        self.left_slider.setSingleStep(value)
        self.right_slider.setSingleStep(value)

    def setLeftValue(self, value):
        """
        Sets the value of the left slider.

        Parameters
        ----------
        value : int
            Desired value for the left slider.
        """
        self.left_slider.setValue(value)

    def setRightValue(self, value):
        """
        Sets the value of the right slider.

        Parameters
        ----------
        value : int
            Desired value for the right slider.
        """
        self.right_slider.setValue(value)

    def setValues(self, values):
        """
        Sets values for both sliders.

        Parameters
        ----------
        values : tuple of int
            Tuple containing (left_value, right_value).
        """
        self.left_slider.setValue(values[0])
        self.right_slider.setValue(values[1])
    
    def values(self):
        """
        Returns the current values of both sliders.

        Returns
        -------
        tuple of int
            (left_value, right_value)
        """
        return self.left_slider.value(), self.right_slider.value()

class CustomActionMenu(CustomAction):
    """
    A custom QMenu that allows dynamic addition and removal of menu lame_action.

    Attributes
    ----------
    items : dict[str, QAction]
        A dictionary mapping action names (as strings) to their corresponding QAction objects.

    Methods
    -------
    add_menu_item(name: str, callback: Callable, shortcut: Optional[str] = None, tooltip: Optional[str] = None) -> None
        Add a single menu item with an optional shortcut and tooltip.

    remove_menu_item(name: str) -> None
        Remove a menu item by name if it exists.

    _add_menu_items(items: list[tuple[str, Callable, Optional[str], Optional[str]]]) -> None
        Add multiple menu items in one batch operation.

    clear_menu() -> None
        Remove all existing menu actions from the menu and clear the internal items dictionary.

    update_menu(items: list[tuple[str, Callable, Optional[str], Optional[str]]]) -> None
        Clear and rebuild the menu using the provided list of items.

    get_menu_item(name: str) -> Optional[QAction]
        Return the QAction associated with the given name, or None if not found.

    get_menu_structure() -> nested list
        Return current menu structure as a nested list.

    has_submenu(name: str) -> bool
        Check if a submenu by a specific name exists.

    Parameters
    ----------
    icon : str
        Path to the icon displayed in the action.
    text : str
        Text label for the action.
    menu_items : list
        Initial list of menu items and submenus to add.
    parent : QWidget, optional
        Parent widget for the action and menu.
    """
    def __init__(self, text, menu_items, light_icon_unchecked: str, dark_icon_unchecked: str|None=None, parent=None):
        super().__init__(text, light_icon_unchecked=light_icon_unchecked, dark_icon_unchecked=dark_icon_unchecked, parent=parent)
        
        # Create the main menu
        self.menu = QMenu(parent)

        # Dictionary to hold references to dynamically updatable submenus
        self.submenu_references = {}

        # Populate the menu
        self._add_menu_items(self.menu, menu_items)

        # Function to display the menu
        def show_menu():
            self.menu.exec(QCursor.pos())

        # Connect the action to the show_menu function
        self.triggered.connect(show_menu)

    def _add_menu_items(self, menu, items):
        """
        Recursively adds menu items to the given QMenu.

        Parameters
        ----------
        menu : QMenu
            The parent menu to which items will be added.
        items : list of tuples
            A list where each tuple represents a menu item.

            Each tuple must be of the form:
                (str, Callable | list | None)

            - If the second element is a callable, it will be connected to the triggered signal of a QAction.
            - If it's a list, a submenu will be created with that list as its content (recursively).
            - If it's None, a disabled/non-interactive menu item will be added (useful as a label or placeholder).

        Example
        -------

        .. code-block:: python

            items = [
                ("Export", export_callback),
                ("Import", [
                    ("From CSV", import_csv_callback),
                    ("From JSON", import_json_callback)
                ]),
                ("Disabled Item", None)
            ]

        """
        for item_text, callback_or_submenu in items:
            if isinstance(callback_or_submenu, list):
                # Create a submenu
                submenu = QMenu(item_text, menu)
                self.submenu_references[item_text] = submenu  # Store a reference
                self._add_menu_items(submenu, callback_or_submenu)
                menu.addMenu(submenu)
            else:
                # Add a regular action
                menu.addAction(item_text, callback_or_submenu)

    def update_menu(self, new_items):
        """Replace the entire menu with a new structure.


        Parameters
        ----------
        new_items : list of tuples
            A list where each tuple represents a menu item.

            Each tuple must be of the form:
                (str, Callable | list | None)

        :see also: _add_menu_items
        """
        self.clear_menu()
        self._add_menu_items(self.menu, new_items)

    def update_submenu(self, submenu_name, new_items):
        """
        Update a submenu with new items.
        
        Parameters
        ----------
        submenu_name : str
            Name of submenu
        new_items : items
            A list where each tuple represents a menu item.

            Each tuple must be of the form:
                (str, Callable | list | None)

        :see also: _add_menu_items
        """
        submenu = self.submenu_references.get(submenu_name)
        if submenu:
            submenu.clear()  # Remove all current actions
            self._add_menu_items(submenu, new_items)

    def clear_menu(self):
        """Clear all actions and submenus from the menu."""
        self.menu.clear()
        self.submenu_references.clear()

    def add_menu_item(self, text, callback_or_submenu):
        """
        Adds a single menu item to the specified QMenu.

        Parameters:
            menu (QMenu): The menu to which the item will be added.
            label (str): The text label for the menu item.
            action (Callable | None): The function to be called when the menu item is triggered.
                If None, the menu item will be added as a non-interactive (disabled) item.

        Returns:
            QAction: The QAction object that was added to the menu.

        Example
        -------

        .. code-block:: python

            self.add_menu_item(file_menu, "Open", self.open_file)
            self.add_menu_item(help_menu, "About", None)  # Adds a non-clickable item
        """
        self._add_menu_items(self.menu, [(text, callback_or_submenu)])


    def remove_menu_item(self, menu_path):
        """
        Remove a menu item or submenu by its path.

        Parameters
        ----------
        menu_path : list of str
            A list representing the hierarchical path to the item.
            For example, ['Top Level', 'Submenu', 'Item Text'] will remove
            the action or submenu named 'Item Text' inside 'Submenu' which is
            under 'Top Level'.

        Returns
        -------
        bool
            True if the item was found and removed, False otherwise.

        Examples
        --------
        
        To remove 'Export' from the 'File' top level,

        .. code-block:: python

            action.remove_menu_item(['File', 'Export'])

        """
        if not menu_path:
            return False

        menu = self.menu
        for part in menu_path[:-1]:
            found = None
            for action in menu.actions():
                if action.menu() and action.text() == part:
                    found = action.menu()
                    break
            if not found:
                return False
            menu = found

        for action in menu.actions():
            if action.text() == menu_path[-1]:
                menu.removeAction(action)
                return True

        return False

    def get_menu_structure(self):
        """
        Return current menu structure as a nested list.
         
        This method is useful for debugging or serialization.

        Returns
        -------
        nested list
            Current menu structure.
        """
        def recurse(menu):
            items = []
            for action in menu.actions():
                if action.menu():
                    items.append((action.text(), recurse(action.menu())))
                else:
                    items.append((action.text(), None))
            return items
        return recurse(self.menu)
    
    def has_submenu(self, name):
        """Check if a submenu by a specific name exists.
        
        Parameters
        ----------
        name : str
            Submenu text to test

        Returns
        -------
        bool
            True if `name` is a submenu
        """
        return name in self.submenu_references


class ListFilterWidget(QWidget):
    """A search box that filters a target ``QListWidget``'s items live, as
    the user types.

    Case-insensitive substring match by default. Items not matching the
    current filter text are hidden (``QListWidgetItem.setHidden``), not
    removed -- the underlying item set/order is never disturbed, so
    clearing the filter instantly restores the full list, and any
    checkbox/selection state on hidden items is preserved.

    Generic and self-contained: no assumptions about what the list items
    represent, so it's reusable across projects (e.g. filtering a mineral
    list, a field list, a file list) without any project-specific coupling.

    Parameters
    ----------
    target : QListWidget
        The list widget to filter.
    placeholder : str, optional
        Placeholder text shown in the search box, by default "Search...".
    case_sensitive : bool, optional
        Whether the substring match is case-sensitive, by default False.
    parent : QWidget, optional
        Parent widget, by default None.

    Signals
    -------
    filterChanged(str)
        Emitted whenever the filter text changes, after items have already
        been shown/hidden to match.
    """
    filterChanged = pyqtSignal(str)

    def __init__(self, target: QListWidget, placeholder="Search...", case_sensitive=False, parent=None):
        super().__init__(parent)
        self.target = target
        self.case_sensitive = case_sensitive

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(placeholder)
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        self.search_input.textChanged.connect(self._apply_filter)

    def _apply_filter(self, text: str):
        needle = text if self.case_sensitive else text.lower()
        for i in range(self.target.count()):
            item = self.target.item(i)
            haystack = item.text() if self.case_sensitive else item.text().lower()
            item.setHidden(bool(needle) and needle not in haystack)
        self.filterChanged.emit(text)

    def filter_text(self) -> str:
        """Current filter text."""
        return self.search_input.text()

    def clear(self):
        """Clears the filter text, unhiding every item."""
        self.search_input.clear()

