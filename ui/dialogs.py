from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..database import STATUSES, TRANSITIONS
from ..workshop import money
from .common import USER_ERRORS, DataTable, FormDialog, add_field, button, label


def entry(value="", password=False):
    field = QLineEdit(str(value or ""))
    if password:
        field.setEchoMode(QLineEdit.Password)
        field.setMaxLength(128)
    else:
        field.setMaxLength(200)
    return field


def multiline(value="", height=90):
    field = QPlainTextEdit(str(value or ""))
    field.setFixedHeight(height)
    return field


def choose(combo, value):
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


class LoginDialog(FormDialog):
    def __init__(self, workshop, demo=False):
        super().__init__(
            "Ремонт · вход",
            "Журнал заявок сервисного центра. Данные хранятся на этом компьютере.",
            save_text="Войти",
        )
        self.workshop = workshop
        self.username = entry("admin" if demo else "")
        self.password = entry(password=True)
        add_field(self.form, "&Логин", self.username)
        add_field(self.form, "&Пароль", self.password)
        self.show_password = QCheckBox("Показать пароль")
        self.show_password.toggled.connect(
            lambda checked: self.password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        self.form.addRow("", self.show_password)
        if demo:
            self.layout.insertWidget(
                2, label("Демонстрационная база\nadmin / DemoAdmin!2026\nmaster / DemoMaster!2026", "muted", True)
            )
        self.save_button.clicked.connect(
            lambda: self.submit(lambda: workshop.login(self.username.text(), self.password.text()))
        )
        (self.password if demo else self.username).setFocus()


class SetupDialog(FormDialog):
    def __init__(self, workshop):
        super().__init__(
            "Первый запуск",
            "Создайте администратора. После входа добавьте мастера, клиентов и устройства.",
            save_text="Создать администратора",
        )
        self.full_name = entry()
        self.username = entry()
        self.password = entry(password=True)
        self.confirm = entry(password=True)
        add_field(self.form, "&Имя администратора", self.full_name)
        add_field(self.form, "&Логин", self.username)
        add_field(self.form, "&Пароль (8–128 символов)", self.password)
        add_field(self.form, "П&овтор пароля", self.confirm)
        self.save_button.clicked.connect(lambda: self.submit(lambda: self.save(workshop)))

    def save(self, workshop):
        if self.password.text() != self.confirm.text():
            raise ValueError("Пароли не совпадают.")
        workshop.setup(self.full_name.text(), self.username.text(), self.password.text())


class ClientDialog(FormDialog):
    def __init__(self, workshop, session, record=None, parent=None):
        record = record or {}
        super().__init__("Изменить клиента" if record else "Новый клиент", parent=parent)
        self.full_name = entry(record.get("full_name"))
        self.phone = entry(record.get("phone"))
        self.email = entry(record.get("email"))
        self.notes = multiline(record.get("notes"))
        add_field(self.form, "&ФИО", self.full_name)
        add_field(self.form, "&Телефон", self.phone)
        add_field(self.form, "&Email (необязательно)", self.email)
        add_field(self.form, "&Примечание", self.notes)
        self.save_button.clicked.connect(
            lambda: self.submit(
                lambda: workshop.save_client(
                    session, self.full_name.text(), self.phone.text(), self.email.text(),
                    self.notes.toPlainText(), record.get("id")
                )
            )
        )


class DeviceDialog(FormDialog):
    def __init__(self, workshop, session, record=None, parent=None):
        record = record or {}
        super().__init__("Изменить устройство" if record else "Новое устройство", parent=parent)
        self.client = QComboBox()
        self.client.addItem("Выберите клиента", None)
        for client in workshop.list_clients(session):
            self.client.addItem(f"{client['full_name']} · {client['phone']}", client["id"])
        choose(self.client, record.get("client_id"))
        self.kind = QComboBox()
        self.kind.addItems(["Ноутбук", "Системный блок", "Моноблок", "Монитор", "Принтер", "Другое"])
        self.kind.setEditable(True)
        if record:
            self.kind.setCurrentText(record["device_type"])
        self.brand = entry(record.get("brand"))
        self.model = entry(record.get("model"))
        self.serial = entry(record.get("serial_number"))
        self.notes = multiline(record.get("notes"))
        for title, field in [
            ("&Клиент", self.client), ("&Тип", self.kind), ("&Производитель", self.brand),
            ("&Модель", self.model), ("&Серийный номер", self.serial), ("Прим&ечание", self.notes)
        ]:
            add_field(self.form, title, field)
        self.save_button.clicked.connect(
            lambda: self.submit(
                lambda: workshop.save_device(
                    session, self.client.currentData(), self.kind.currentText(), self.brand.text(),
                    self.model.text(), self.serial.text(), self.notes.toPlainText(), record.get("id")
                )
            )
        )


class UserDialog(FormDialog):
    def __init__(self, workshop, session, parent=None):
        super().__init__(
            "Новый сотрудник", "Логин: 3–40 латинских букв, цифр или символов . _ -",
            parent=parent,
        )
        self.full_name = entry()
        self.username = entry()
        self.password = entry(password=True)
        self.role = QComboBox()
        self.role.addItem("Мастер", "master")
        self.role.addItem("Администратор", "admin")
        for title, field in [
            ("&ФИО", self.full_name), ("&Логин", self.username),
            ("&Пароль (8–128 символов)", self.password), ("&Роль", self.role)
        ]:
            add_field(self.form, title, field)
        self.save_button.clicked.connect(
            lambda: self.submit(
                lambda: workshop.create_user(
                    session, self.full_name.text(), self.username.text(),
                    self.password.text(), self.role.currentData()
                )
            )
        )


class PasswordDialog(FormDialog):
    def __init__(self, workshop, session, parent=None):
        super().__init__("Изменить пароль", parent=parent)
        self.old = entry(password=True)
        self.new = entry(password=True)
        self.confirm = entry(password=True)
        add_field(self.form, "&Текущий пароль", self.old)
        add_field(self.form, "&Новый пароль", self.new)
        add_field(self.form, "П&овтор пароля", self.confirm)
        self.save_button.clicked.connect(lambda: self.submit(lambda: self.save(workshop, session)))

    def save(self, workshop, session):
        if self.new.text() != self.confirm.text():
            raise ValueError("Пароли не совпадают.")
        workshop.change_password(session, self.old.text(), self.new.text())


class ServiceDialog(FormDialog):
    def __init__(self, workshop, session, record=None, parent=None):
        record = record or {}
        super().__init__("Изменить услугу" if record else "Новая услуга", parent=parent)
        self.name = entry(record.get("name"))
        self.price = entry(f"{record.get('price_kopecks', 0) / 100:.2f}")
        self.active = QCheckBox("Услуга доступна для новых работ")
        self.active.setChecked(bool(record.get("is_active", True)))
        add_field(self.form, "&Название", self.name)
        add_field(self.form, "&Цена, руб.", self.price)
        self.form.addRow("", self.active)
        self.layout.insertWidget(
            2, label("Изменение цены справочника не меняет стоимость уже добавленных работ.", "muted", True)
        )
        self.save_button.clicked.connect(
            lambda: self.submit(
                lambda: workshop.save_service(
                    session, self.name.text(), self.price.text(), self.active.isChecked(), record.get("id")
                )
            )
        )


class OrderForm(FormDialog):
    def __init__(self, workshop, session, record=None, parent=None):
        record = record or {}
        super().__init__("Реквизиты заявки" if record else "Новая заявка", parent=parent)
        self.workshop, self.session, self.record = workshop, session, record
        self.client, self.device, self.master = QComboBox(), QComboBox(), QComboBox()
        if not record:
            self.client.addItem("Выберите клиента", None)
            for client in workshop.list_clients(session):
                self.client.addItem(client["full_name"], client["id"])
            add_field(self.form, "&Клиент", self.client)
            add_field(self.form, "&Устройство", self.device)
            self.client.currentIndexChanged.connect(self.refresh_devices)
            self.refresh_devices()
        for master in workshop.masters(session):
            self.master.addItem(master["full_name"], master["id"])
        choose(self.master, record.get("master_id"))
        add_field(self.form, "&Мастер", self.master)
        self.complaint = multiline(record.get("complaint"), 120)
        add_field(self.form, "&Неисправность", self.complaint)
        self.use_due = QCheckBox("Указать плановую дату готовности")
        self.due = QDateEdit(QDate.currentDate().addDays(3))
        self.due.setDisplayFormat("dd.MM.yyyy")
        self.due.setCalendarPopup(True)
        if record.get("due_date"):
            self.due.setDate(QDate.fromString(record["due_date"], "yyyy-MM-dd"))
            self.use_due.setChecked(True)
        self.due.setEnabled(self.use_due.isChecked())
        self.use_due.toggled.connect(self.due.setEnabled)
        self.form.addRow("", self.use_due)
        add_field(self.form, "&Плановая дата", self.due)
        if not record:
            self.layout.insertWidget(
                2, label("Клиент, устройство и мастер должны быть заранее добавлены в соответствующих разделах.", "muted", True)
            )
        self.save_button.clicked.connect(lambda: self.submit(self.save))

    def refresh_devices(self):
        self.device.clear()
        self.device.addItem("Выберите устройство", None)
        if self.client.currentData():
            for device in self.workshop.list_devices(self.session, self.client.currentData()):
                self.device.addItem(
                    f"{device['brand']} {device['model']} · {device['serial_number'] or 'без серийного номера'}",
                    device["id"],
                )

    def save(self):
        due = self.due.date().toString("yyyy-MM-dd") if self.use_due.isChecked() else None
        if self.record:
            return self.workshop.update_order(
                self.session, self.record["id"], self.complaint.toPlainText(), self.master.currentData(), due
            )
        return self.workshop.create_order(
            self.session, self.device.currentData(), self.master.currentData(),
            self.complaint.toPlainText(), due
        )


class OrderDialog(QDialog):
    def __init__(self, workshop, session, order_id, parent=None):
        super().__init__(parent)
        self.workshop, self.session, self.order_id = workshop, session, order_id
        self.setWindowTitle(f"Заявка №{order_id:05d}")
        self.resize(1000, 720)
        self.setMinimumSize(880, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.heading = label(f"Заявка №{order_id:05d}", "title")
        layout.addWidget(self.heading)
        self.metadata = label("", "muted", True)
        layout.addWidget(self.metadata)
        self.error = label("", "error", True)
        self.error.hide()
        layout.addWidget(self.error)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 16, 0, 0)
        form = QFormLayout()
        form.setSpacing(10)
        self.complaint = multiline(height=82)
        self.complaint.setReadOnly(True)
        self.diagnosis = multiline(height=100)
        add_field(form, "Неисправность", self.complaint)
        add_field(form, "&Результат диагностики", self.diagnosis)
        info_layout.addLayout(form)
        actions = QHBoxLayout()
        self.save_diagnosis_button = button("Сохранить диагностику", self.save_diagnosis, True)
        actions.addWidget(self.save_diagnosis_button)
        self.edit_button = button("Изменить реквизиты", self.edit_order)
        self.edit_button.setVisible(session.role == "admin")
        actions.addWidget(self.edit_button)
        actions.addStretch()
        info_layout.addLayout(actions)
        info_layout.addStretch()
        self.tabs.addTab(info, "Сведения")

        works = QWidget()
        work_layout = QVBoxLayout(works)
        work_layout.setContentsMargins(0, 16, 0, 0)
        self.works_table = DataTable([
            ("Услуга", "name", 330), ("Кол-во", "quantity", 90),
            ("Цена", "unit_price_kopecks", 140), ("Сумма", "amount", 140)
        ])
        work_layout.addWidget(self.works_table, 1)
        add_form = QFormLayout()
        self.service, self.quantity, self.price = QComboBox(), QSpinBox(), entry()
        self.quantity.setRange(1, 1000)
        self.service_rows = workshop.list_services(session, active_only=True)
        for service in self.service_rows:
            self.service.addItem(service["name"], service["id"])
        self.service.currentIndexChanged.connect(self.select_price)
        self.select_price()
        add_field(add_form, "&Услуга", self.service)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(label("Количество"))
        self.quantity.setAccessibleName("Количество услуг")
        row_layout.addWidget(self.quantity)
        price_label = label("Цена, руб.")
        price_label.setBuddy(self.price)
        row_layout.addWidget(price_label)
        row_layout.addWidget(self.price)
        add_form.addRow("", row)
        work_layout.addLayout(add_form)
        work_actions = QHBoxLayout()
        self.add_service_button = button("Добавить работу", self.add_service, True)
        self.remove_service_button = button("Убрать выбранную работу", self.remove_service)
        work_actions.addWidget(self.add_service_button)
        work_actions.addWidget(self.remove_service_button)
        work_actions.addStretch()
        work_layout.addLayout(work_actions)
        self.tabs.addTab(works, "Работы и стоимость")

        history = QWidget()
        history_layout = QVBoxLayout(history)
        history_layout.setContentsMargins(0, 16, 0, 0)
        self.history_table = DataTable([
            ("Дата", "changed_at", 155), ("Было", "from_name", 135),
            ("Стало", "to_name", 145), ("Сотрудник", "employee", 175),
            ("Комментарий", "note", 220)
        ])
        history_layout.addWidget(self.history_table)
        self.tabs.addTab(history, "История статусов")
        status_form = QFormLayout()
        self.next_status, self.status_note = QComboBox(), entry()
        self.status_note.setMaxLength(2000)
        add_field(status_form, "&Следующий статус", self.next_status)
        add_field(status_form, "&Комментарий", self.status_note)
        layout.addLayout(status_form)
        footer = QHBoxLayout()
        self.status_button = button("Изменить статус", self.change_status)
        footer.addWidget(self.status_button)
        self.total_label = label("", "mono")
        footer.addStretch()
        footer.addWidget(self.total_label)
        footer.addWidget(button("Закрыть", self.reject))
        layout.addLayout(footer)
        self.refresh()

    def select_price(self):
        service_id = self.service.currentData()
        row = next((row for row in self.service_rows if row["id"] == service_id), None)
        self.price.setText(f"{row['price_kopecks'] / 100:.2f}" if row else "0.00")

    def run(self, operation):
        try:
            operation()
        except USER_ERRORS as error:
            self.error.setText(str(error))
            self.error.show()
            return False
        self.error.hide()
        self.refresh()
        return True

    def refresh(self):
        order = self.workshop.order_detail(self.session, self.order_id)
        self.order = order
        self.heading.setText(f"Заявка №{self.order_id:05d} · {order['status_name']}")
        self.metadata.setText(
            f"{order['client_name']} · {order['phone']}\n"
            f"{order['device_type']} {order['brand']} {order['model']} · "
            f"серийный № {order['serial_number'] or 'не указан'}\n"
            f"Мастер: {order['master_name']} · "
            f"Плановая дата: {order['due_date'] or 'не указана'}"
        )
        self.complaint.setPlainText(order["complaint"])
        if not self.diagnosis.document().isModified():
            self.diagnosis.setPlainText(order["diagnosis"])
            self.diagnosis.document().setModified(False)
        self.next_status.clear()
        for code in TRANSITIONS[order["status_code"]]:
            self.next_status.addItem(dict(STATUSES)[code], code)
        editable = not order["is_terminal"]
        for widget in [
            self.diagnosis, self.save_diagnosis_button, self.edit_button, self.service,
            self.quantity, self.price, self.add_service_button, self.remove_service_button,
            self.next_status, self.status_note, self.status_button
        ]:
            widget.setEnabled(editable)
        self.total_label.setText("Итого: " + money(order["total_kopecks"]))
        self.works_table.set_rows(
            [{**row, "amount": row["quantity"] * row["unit_price_kopecks"]} for row in order["services"]],
            {"unit_price_kopecks": money, "amount": money},
            numeric=("quantity", "unit_price_kopecks", "amount"),
        )
        self.history_table.set_rows(order["history"], {"from_name": lambda value: value or "—"})
        self.history_table.sortItems(0, Qt.DescendingOrder)

    def save_diagnosis(self):
        if self.run(
            lambda: self.workshop.save_diagnosis(self.session, self.order_id, self.diagnosis.toPlainText())
        ):
            self.diagnosis.document().setModified(False)

    def add_service(self):
        self.run(
            lambda: self.workshop.add_order_service(
                self.session, self.order_id, self.service.currentData(),
                self.quantity.value(), self.price.text()
            )
        )

    def remove_service(self):
        selected = self.works_table.record()
        if not selected:
            self.error.setText("Выберите работу в таблице.")
            self.error.show()
            return
        if QMessageBox.question(
            self, "Удалить работу", f"Убрать «{selected['name']}» из заявки?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            self.run(lambda: self.workshop.remove_order_service(self.session, self.order_id, selected["id"]))

    def change_status(self):
        if self.diagnosis.document().isModified():
            self.error.setText("Сначала сохраните изменённый результат диагностики.")
            self.error.show()
            return
        if self.run(
            lambda: self.workshop.change_status(
                self.session, self.order_id, self.next_status.currentData(), self.status_note.text()
            )
        ):
            self.status_note.clear()

    def edit_order(self):
        dialog = OrderForm(self.workshop, self.session, self.order, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh()

    def reject(self):
        if self.diagnosis.document().isModified() and QMessageBox.question(
            self, "Несохранённые изменения", "Закрыть карточку без сохранения диагностики?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        super().reject()
