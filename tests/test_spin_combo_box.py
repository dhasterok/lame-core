from PyQt6.QtWidgets import QApplication

from lame_core.CustomWidgets import SpinComboBox


def test_spin_combo_box_keeps_index_in_sync():
    app = QApplication.instance() or QApplication([])
    widget = SpinComboBox(["one", "two", "three"])

    assert widget.currentIndex() == 0
    assert widget.spin_box.value() == 0

    widget.setCurrentIndex(2)
    assert widget.spin_box.value() == 2
    assert widget.combo_box.currentIndex() == 2

    widget.spin_box.setValue(1)
    assert widget.combo_box.currentIndex() == 1
    assert widget.currentIndex() == 1

    assert widget.allItems() == ["one", "two", "three"]
    app.processEvents()
