from PyQt5.QtCore import QDate, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QShortcut,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..workshop import money
from .common import USER_ERRORS, DataTable, button, label
from .dialogs import (
    ClientDialog,
    DeviceDialog,
    OrderDialog,
    OrderForm,
    PasswordDialog,
    ServiceDialog,
    UserDialog,
)

ORDER_COLUMNS = [
    ("№", "id", 76), ("Клиент", "client_name", 160),
    ("Устройство", "device", 180), ("Статус", "status_name", 135),
    ("Мастер", "master_name", 150), ("Стоимость", "total_kopecks", 130),
    ("Плановая дата", "due_date", 120)
]


def order_rows(rows):
    return [{**row, "device": f"{row['brand']} {row['model']}"} for row in rows]


class OrdersPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.workshop, self.session = window, window.workshop, window.session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        title = QHBoxLayout()
        title.addWidget(label("Журнал заявок", "title"))
        title.addStretch()
        self.new_button = button("Новая заявка · Ctrl+N", self.create_order, True)
        self.new_button.setVisible(self.session.role == "admin")
        title.addWidget(self.new_button)
        layout.addLayout(title)
        filter_row = QHBoxLayout()
        search_label = label("&Поиск")
        self.search = QLineEdit()
        self.search.setAccessibleName("Поиск заявок")
        self.search.setPlaceholderText("Номер, клиент, телефон или устройство")
        search_label.setBuddy(self.search)
        filter_row.addWidget(search_label)
        filter_row.addWidget(self.search, 1)
        self.status = QComboBox()
        self.status.addItem("Все статусы", None)
        for status in self.workshop.statuses(self.session):
            self.status.addItem(status["name"], status["code"])
        status_label = label("&Статус")
        status_label.setBuddy(self.status)
        self.status.setAccessibleName("Фильтр по статусу")
        filter_row.addWidget(status_label)
        filter_row.addWidget(self.status)
        self.master = QComboBox()
        self.master.addItem("Все мастера", None)
        if self.session.role == "admin":
            for master in self.workshop.masters(self.session):
                self.master.addItem(master["full_name"], master["id"])
            master_label = label("&Мастер")
            master_label.setBuddy(self.master)
            filter_row.addWidget(master_label)
            filter_row.addWidget(self.master)
        filter_row.addWidget(button("Сбросить", self.reset_filters))
        layout.addLayout(filter_row)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(180)
        self.search.textChanged.connect(lambda: self.debounce.start())
        self.debounce.timeout.connect(self.safe_refresh)
        self.status.currentIndexChanged.connect(self.safe_refresh)
        self.master.currentIndexChanged.connect(self.safe_refresh)
        self.splitter = QSplitter(Qt.Horizontal)
        self.table = DataTable(ORDER_COLUMNS)
        self.table.sortItems(0, Qt.DescendingOrder)
        self.table.itemSelectionChanged.connect(self.update_preview)
        self.table.cellDoubleClicked.connect(self.open_order)
        self.splitter.addWidget(self.table)
        self.preview = QFrame()
        self.preview.setObjectName("preview")
        self.preview.setMinimumWidth(270)
        self.preview.setMaximumWidth(350)
        preview_layout = QVBoxLayout(self.preview)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_layout.setSpacing(16)
        self.preview_title = label("Карточка ремонта", "title", True)
        self.preview_text = label("Выберите заявку в журнале.", wrap=True)
        self.preview_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.preview_total = label("", "mono")
        self.open_button = button("Открыть заявку", self.open_order, True)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_text)
        preview_layout.addStretch()
        preview_layout.addWidget(self.preview_total)
        preview_layout.addWidget(self.open_button)
        self.splitter.addWidget(self.preview)
        self.splitter.setSizes([900, 290])
        layout.addWidget(self.splitter, 1)
        bottom = QHBoxLayout()
        self.count_label = label("", "muted", True)
        bottom.addWidget(self.count_label, 1)
        bottom.addWidget(button("Обновить · F5", self.safe_refresh))
        layout.addLayout(bottom)
        QShortcut(QKeySequence("Return"), self.table, activated=self.open_order).setContext(Qt.WidgetShortcut)
        self.refresh()

    def safe_refresh(self):
        self.window.perform(self.refresh)

    def refresh(self):
        # Справочник мастеров обновляется после добавления сотрудников.
        if self.session.role == "admin":
            selected = self.master.currentData()
            self.master.blockSignals(True)
            self.master.clear()
            self.master.addItem("Все мастера", None)
            for master in self.workshop.masters(self.session):
                self.master.addItem(master["full_name"], master["id"])
            self.master.setCurrentIndex(max(0, self.master.findData(selected)))
            self.master.blockSignals(False)
        rows = self.workshop.list_orders(
            self.session, self.search.text(), self.status.currentData(), self.master.currentData()
        )
        self.table.set_rows(
            order_rows(rows), {"id": lambda n: f"{n:05d}", "total_kopecks": money, "due_date": lambda d: d or "—"},
            numeric=("id", "total_kopecks"),
        )
        if rows:
            self.count_label.setText(f"Заявок в журнале: {len(rows)} · Enter или двойной щелчок — открыть")
        elif self.search.text() or self.status.currentData() or self.master.currentData():
            self.count_label.setText("По этим условиям заявок нет. Измените фильтры или нажмите «Сбросить».")
        else:
            self.count_label.setText(
                "Заявок пока нет. Добавьте мастера, клиента и устройство, затем создайте первую заявку."
                if self.session.role == "admin" else "Назначенных вам заявок пока нет."
            )
        self.update_preview()

    def reset_filters(self):
        self.search.clear()
        self.status.setCurrentIndex(0)
        self.master.setCurrentIndex(0)
        self.safe_refresh()

    def update_preview(self):
        selected = self.table.record()
        self.open_button.setEnabled(bool(selected))
        if not selected:
            self.preview_title.setText("Карточка ремонта")
            self.preview_text.setText("Выберите заявку в журнале.\n\nЗдесь появятся клиент, устройство и описание неисправности.")
            self.preview_total.clear()
            return
        self.preview_title.setText(f"№{selected['id']:05d}\n{selected['status_name']}")
        self.preview_text.setText(
            f"{selected['client_name']}\n{selected['phone']}\n\n"
            f"{selected['device_type']}\n{selected['brand']} {selected['model']}\n\n"
            f"НЕИСПРАВНОСТЬ\n{selected['complaint'][:220]}\n\n"
            f"Мастер: {selected['master_name']}\n"
            f"Плановая дата: {selected['due_date'] or 'не указана'}"
        )
        self.preview_total.setText(money(selected["total_kopecks"]))

    def create_order(self):
        if self.session.role != "admin":
            return
        self.window.perform(lambda: self.window.open_form(OrderForm(self.workshop, self.session, parent=self)))

    def open_order(self, *_):
        row = self.table.record()
        if not row:
            return
        self.window.perform(lambda: self._open(row["id"]))

    def _open(self, order_id):
        dialog = OrderDialog(self.workshop, self.session, order_id, self)
        dialog.exec_()
        self.window.refresh_all()


class CatalogPage(QWidget):
    def __init__(self, window, title, columns, fetch, new_dialog=None, edit_dialog=None,
                 remove=None, remove_label="Удалить", formatters=None, numeric=()):
        super().__init__()
        self.window, self.fetch = window, fetch
        self.new_dialog, self.edit_dialog, self.remove = new_dialog, edit_dialog, remove
        self.formatters, self.numeric = formatters or {}, numeric
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        top = QHBoxLayout()
        top.addWidget(label(title, "title"))
        top.addStretch()
        if new_dialog:
            top.addWidget(button("Добавить", self.add_record, True))
        layout.addLayout(top)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setAccessibleName(f"Поиск: {title}")
        caption = label("&Поиск")
        caption.setBuddy(self.search)
        search_row.addWidget(caption)
        search_row.addWidget(self.search, 1)
        layout.addLayout(search_row)
        self.table = DataTable(columns)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.cellDoubleClicked.connect(self.edit_record)
        layout.addWidget(self.table, 1)
        footer = QHBoxLayout()
        self.count = label("", "muted")
        footer.addWidget(self.count, 1)
        self.edit_button = button("Изменить", self.edit_record)
        self.edit_button.setVisible(bool(edit_dialog))
        footer.addWidget(self.edit_button)
        self.remove_button = button(remove_label, self.remove_record)
        self.remove_button.setVisible(bool(remove))
        footer.addWidget(self.remove_button)
        footer.addWidget(button("Обновить", lambda: window.perform(self.refresh)))
        layout.addLayout(footer)
        self.search.textChanged.connect(self.filter_rows)
        self.refresh()

    def refresh(self):
        self.records = self.fetch()
        self.filter_rows()

    def filter_rows(self):
        query = self.search.text().strip().casefold()
        rows = [
            row for row in self.records
            if not query or query in " ".join(str(value or "") for value in row.values()).casefold()
        ]
        self.table.set_rows(rows, self.formatters, self.numeric)
        self.count.setText(f"Записей: {len(rows)}" if rows else "Записей нет. Добавьте запись или измените поиск.")
        self.selection_changed()

    def selection_changed(self):
        selected = bool(self.table.record())
        self.edit_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)

    def add_record(self):
        self.window.perform(lambda: self.window.open_form(self.new_dialog()))

    def edit_record(self, *_):
        selected = self.table.record()
        if selected and self.edit_dialog:
            self.window.perform(lambda: self.window.open_form(self.edit_dialog(selected)))

    def remove_record(self):
        selected = self.table.record()
        if not selected or not self.remove:
            return
        if QMessageBox.question(
            self, "Подтвердите действие", "Выполнить действие для выбранной записи?\n"
            "Связанные с заявками данные не будут удалены.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            self.window.perform(lambda: self._remove(selected))

    def _remove(self, selected):
        self.remove(selected)
        self.window.refresh_all()


class ReportPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(label("Сводка по ремонту", "title"))
        layout.addWidget(label(
            "Период задаётся по дате приёма заявки. Стоимость выданных работ не является учётом платежей.",
            "muted", True
        ))
        filters = QHBoxLayout()
        self.start = QDateEdit(QDate.currentDate().addMonths(-1))
        self.end = QDateEdit(QDate.currentDate())
        for title, field in [("С", self.start), ("По", self.end)]:
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd.MM.yyyy")
            caption = label(title)
            caption.setBuddy(field)
            filters.addWidget(caption)
            filters.addWidget(field)
        filters.addStretch()
        filters.addWidget(button("Сформировать", lambda: window.perform(self.refresh), True))
        layout.addLayout(filters)
        self.summary = label("", "mono", True)
        layout.addWidget(self.summary)
        self.table = DataTable(ORDER_COLUMNS)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        report = self.window.workshop.report(
            self.window.session, self.start.date().toString("yyyy-MM-dd"), self.end.date().toString("yyyy-MM-dd")
        )
        self.summary.setText(
            f"Принято: {report['count']}    Незавершено: {report['active']}    "
            f"Готово к выдаче: {report['ready']}\n"
            f"Стоимость услуг в выданных заявках: {money(report['issued_amount'])}"
        )
        self.table.set_rows(
            order_rows(report["rows"]),
            {"id": lambda n: f"{n:05d}", "total_kopecks": money, "due_date": lambda d: d or "—"},
            numeric=("id", "total_kopecks"),
        )


class MainWindow(QMainWindow):
    def __init__(self, workshop, session, demo=False):
        super().__init__()
        self.workshop, self.session = workshop, session
        self.relogin = False
        self.setWindowTitle("Ремонт · учёт заявок" + (" · демонстрация" if demo else ""))
        self.resize(1380, 850)
        self.setMinimumSize(1100, 720)
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        brand = QFrame()
        brand.setObjectName("brand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(24, 16, 24, 16)
        brand_layout.addWidget(label("РЕМОНТ", "title"))
        brand_layout.addWidget(label("  /  журнал сервисного центра", "subtitle"))
        brand_layout.addStretch()
        role = "Администратор" if session.role == "admin" else "Мастер"
        brand_layout.addWidget(label(f"{session.full_name}\n{role}", wrap=True))
        brand_layout.addSpacing(16)
        brand_layout.addWidget(button("Пароль", self.change_password))
        brand_layout.addWidget(button("Выйти", self.logout))
        layout.addWidget(brand)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.orders_page = OrdersPage(self)
        self.pages = [self.orders_page]
        self.tabs.addTab(self.orders_page, "Заявки")
        if session.role == "admin":
            self.build_catalogs()
        self.report_page = ReportPage(self)
        self.pages.append(self.report_page)
        self.tabs.addTab(self.report_page, "Сводка")
        self.tabs.currentChanged.connect(self.tab_changed)
        self.statusBar().showMessage(
            ("ДЕМОНСТРАЦИЯ · вымышленные данные · " if demo else "Локальная база данных · ")
            + "Ctrl+F — поиск · F5 — обновить"
        )
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.orders_page.create_order)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("F5"), self, activated=lambda: self.perform(self.refresh_all))

    def build_catalogs(self):
        w, s = self.workshop, self.session
        specs = [
            ("Клиенты", [("ФИО", "full_name", 280), ("Телефон", "phone", 190),
                         ("Email", "email", 250), ("Устройств", "device_count", 110)],
             lambda: w.list_clients(s),
             lambda: ClientDialog(w, s, parent=self),
             lambda row: ClientDialog(w, s, row, self),
             lambda row: w.delete_client(s, row["id"]), "Удалить", {}, ("device_count",)),
            ("Устройства", [("Тип", "device_type", 140), ("Производитель", "brand", 150),
                            ("Модель", "model", 210), ("Серийный №", "serial_number", 210),
                            ("Клиент", "client_name", 250)],
             lambda: w.list_devices(s),
             lambda: DeviceDialog(w, s, parent=self),
             lambda row: DeviceDialog(w, s, row, self),
             lambda row: w.delete_device(s, row["id"]), "Удалить", {}, ()),
            ("Услуги", [("Название услуги", "name", 500), ("Базовая цена", "price_kopecks", 180),
                        ("Доступность", "is_active", 180)],
             lambda: w.list_services(s),
             lambda: ServiceDialog(w, s, parent=self),
             lambda row: ServiceDialog(w, s, row, self), None, "",
             {"price_kopecks": money, "is_active": lambda v: "Доступна" if v else "Архив"},
             ("price_kopecks",)),
            ("Сотрудники", [("ФИО", "full_name", 300), ("Логин", "username", 220),
                           ("Роль", "role", 180), ("Учётная запись", "is_active", 200)],
             lambda: w.list_users(s),
             lambda: UserDialog(w, s, self), None,
             lambda row: w.set_user_active(s, row["id"], not row["is_active"]),
             "Включить / отключить",
             {"role": lambda v: "Администратор" if v == "admin" else "Мастер",
              "is_active": lambda v: "Активна" if v else "Отключена"}, ()),
        ]
        for title, columns, fetch, new, edit, remove, remove_label, formatters, numeric in specs:
            page = CatalogPage(
                self, title, columns, fetch, new, edit, remove, remove_label, formatters, numeric
            )
            self.pages.append(page)
            self.tabs.addTab(page, title)

    def perform(self, operation):
        try:
            return operation()
        except USER_ERRORS as error:
            QMessageBox.warning(self, "Не удалось выполнить действие", str(error))
            return None

    def open_form(self, dialog):
        if dialog.exec_() == QDialog.Accepted:
            self.refresh_all()
            self.statusBar().showMessage("Изменения сохранены", 4000)

    def refresh_all(self):
        for page in self.pages:
            page.refresh()

    def tab_changed(self, index):
        self.perform(self.pages[index].refresh)

    def focus_search(self):
        self.tabs.setCurrentWidget(self.orders_page)
        self.orders_page.search.setFocus()
        self.orders_page.search.selectAll()

    def change_password(self):
        self.perform(lambda: self.open_form(PasswordDialog(self.workshop, self.session, self)))

    def logout(self):
        self.relogin = True
        self.close()

    def closeEvent(self, event):
        self.workshop.logout(self.session)
        event.accept()
        QApplication.instance().quit()
