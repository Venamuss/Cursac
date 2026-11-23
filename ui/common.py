import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

USER_ERRORS = (ValueError, PermissionError, sqlite3.Error, OSError)


def label(text="", role=None, wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback=None, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if primary:
        widget.setProperty("primary", "true")
    if callback:
        widget.clicked.connect(callback)
    return widget


def add_field(form, title, widget):
    caption = label(title)
    caption.setBuddy(widget)
    widget.setAccessibleName(title.replace("&", ""))
    form.addRow(caption, widget)


class FormDialog(QDialog):
    def __init__(self, title, description="", parent=None, save_text="Сохранить"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(16)
        self.layout.addWidget(label(title, "title"))
        if description:
            self.layout.addWidget(label(description, "muted", True))
        self.error = label("", "error", True)
        self.error.hide()
        self.layout.addWidget(self.error)
        self.form = QFormLayout()
        self.form.setSpacing(12)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.layout.addLayout(self.form)
        self.buttons = QDialogButtonBox(self)
        self.save_button = self.buttons.addButton(save_text, QDialogButtonBox.AcceptRole)
        self.save_button.setProperty("primary", "true")
        self.save_button.style().unpolish(self.save_button)
        self.save_button.style().polish(self.save_button)
        self.save_button.setDefault(True)
        self.buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def submit(self, operation):
        self.error.hide()
        try:
            self.result_value = operation()
        except USER_ERRORS as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.accept()


class SortItem(QTableWidgetItem):
    def __lt__(self, other):
        left, right = self.data(Qt.UserRole), other.data(Qt.UserRole)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return str(left or "").casefold() < str(right or "").casefold()


class DataTable(QTableWidget):
    def __init__(self, columns, parent=None):
        super().__init__(0, len(columns), parent)
        self.columns = columns
        self.setHorizontalHeaderLabels([column[0] for column in columns])
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(44)
        self.horizontalHeader().setMinimumSectionSize(70)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
        for index, column in enumerate(columns):
            self.setColumnWidth(index, column[2] if len(column) > 2 else 160)

    def set_rows(self, rows, formatters=None, numeric=()):
        formatters = formatters or {}
        selected = self.record()
        selected_id = selected.get("id") if selected else None
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for index, (_, key, *_) in enumerate(self.columns):
                raw = row.get(key, "")
                display = formatters[key](raw) if key in formatters else (str(raw) if raw is not None else "")
                item = SortItem(display)
                item.setData(Qt.UserRole, raw)
                item.setData(Qt.UserRole + 1, row)
                item.setToolTip(display)
                if key in numeric:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setFont(QFont("DejaVu Sans Mono", 10))
                    self.horizontalHeaderItem(index).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(row_index, index, item)
        self.setSortingEnabled(True)
        self.clearSelection()
        self.setCurrentCell(-1, -1)
        if selected_id is not None:
            for i in range(self.rowCount()):
                if self.item(i, 0).data(Qt.UserRole + 1).get("id") == selected_id:
                    self.selectRow(i)
                    break

    def record(self):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.item(indexes[0].row(), 0)
        return item.data(Qt.UserRole + 1) if item else None
