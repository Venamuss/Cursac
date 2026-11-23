"""Прикладная логика. Все проверки прав и данных независимы от интерфейса."""

import re
import secrets
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .database import TRANSITIONS, Database
from .security import hash_password, verify_password

MAX_PRICE = 1_000_000_000


@dataclass(frozen=True)
class Session:
    token: str
    user_id: int
    full_name: str
    role: str


def text(value, label: str, minimum=1, maximum=150) -> str:
    value = str(value or "").strip()
    if not minimum <= len(value) <= maximum:
        raise ValueError(f"{label}: требуется от {minimum} до {maximum} символов.")
    return value


def price_to_kopecks(value: str) -> int:
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
        if not amount.is_finite() or amount < 0 or amount > MAX_PRICE / 100:
            raise ValueError
        kopecks = amount * 100
        if kopecks != kopecks.to_integral_value():
            raise ValueError
        return int(kopecks)
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError(
            "Цена: введите сумму от 0 до 10 000 000 рублей, не более двух знаков после запятой."
        ) from error


def money(kopecks: int) -> str:
    return f"{kopecks // 100:,}".replace(",", " ") + f",{kopecks % 100:02d} ₽"


class Workshop:
    def __init__(self, database: Database):
        self.db = database
        self._sessions: dict[str, int] = {}

    def _rows(self, sql, parameters=()):
        return [dict(row) for row in self.db.connection.execute(sql, parameters).fetchall()]

    def _one(self, sql, parameters=()):
        row = self.db.connection.execute(sql, parameters).fetchone()
        return dict(row) if row else None

    def needs_setup(self) -> bool:
        return not self.db.connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()

    def setup(self, full_name, username, password) -> None:
        if not self.needs_setup():
            raise ValueError("Первоначальная настройка уже выполнена.")
        self._save_user(full_name, username, password, "admin")

    def _save_user(self, full_name, username, password, role):
        full_name = text(full_name, "Имя сотрудника", 2)
        username = text(username, "Логин", 3, 40)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
            raise ValueError("Логин: используйте латинские буквы, цифры, точку, дефис или _.")
        if role not in ("admin", "master"):
            raise ValueError("Неизвестная роль сотрудника.")
        encoded = hash_password(password)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO users(full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                (full_name, username, encoded, role),
            )
        return cursor.lastrowid

    def login(self, username, password) -> Session:
        user = self._one("SELECT * FROM users WHERE username = ?", (str(username).strip(),))
        if not user or not user["is_active"] or not verify_password(password, user["password_hash"]):
            raise ValueError("Неверный логин или пароль либо учётная запись отключена.")
        token = secrets.token_urlsafe(32)
        self._sessions[token] = user["id"]
        return Session(token, user["id"], user["full_name"], user["role"])

    def logout(self, session):
        self._sessions.pop(session.token, None)

    def _actor(self, session: Session):
        user_id = self._sessions.get(session.token)
        user = self._one("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
        if not user:
            raise PermissionError("Сеанс завершён. Войдите в систему заново.")
        return user

    def _admin(self, session):
        user = self._actor(session)
        if user["role"] != "admin":
            raise PermissionError("Эта операция доступна только администратору.")
        return user

    def list_users(self, session):
        self._admin(session)
        return self._rows(
            "SELECT id, full_name, username, role, is_active FROM users ORDER BY full_name"
        )

    def masters(self, session):
        self._admin(session)
        return self._rows(
            "SELECT id, full_name FROM users WHERE role = 'master' AND is_active = 1 ORDER BY full_name"
        )

    def create_user(self, session, full_name, username, password, role):
        self._admin(session)
        return self._save_user(full_name, username, password, role)

    def set_user_active(self, session, user_id, active):
        actor = self._admin(session)
        if actor["id"] == user_id:
            raise ValueError("Нельзя отключить собственную учётную запись.")
        if not self._one("SELECT id FROM users WHERE id = ?", (user_id,)):
            raise ValueError("Сотрудник не найден.")
        if not active and self._one(
            """SELECT o.id FROM repair_orders o JOIN repair_statuses s ON s.id = o.status_id
               WHERE o.master_id = ? AND s.is_terminal = 0 LIMIT 1""",
            (user_id,),
        ):
            raise ValueError("Сначала переназначьте незавершённые заявки этого мастера.")
        with self.db.transaction() as conn:
            conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(bool(active)), user_id))
        if not active:
            self._sessions = {k: v for k, v in self._sessions.items() if v != user_id}

    def change_password(self, session, old_password, new_password):
        user = self._actor(session)
        if not verify_password(old_password, user["password_hash"]):
            raise ValueError("Текущий пароль указан неверно.")
        encoded = hash_password(new_password)
        with self.db.transaction() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (encoded, user["id"]))
        self._sessions = {
            token: uid
            for token, uid in self._sessions.items()
            if uid != user["id"] or token == session.token
        }

    def list_clients(self, session):
        self._admin(session)
        return self._rows(
            """SELECT c.*, (SELECT count(*) FROM devices d WHERE d.client_id = c.id) device_count
               FROM clients c ORDER BY c.full_name"""
        )

    def save_client(self, session, full_name, phone, email="", notes="", client_id=None):
        self._admin(session)
        full_name = text(full_name, "Имя клиента", 2)
        phone = text(phone, "Телефон", 7, 30)
        if not re.fullmatch(r"[+0-9() .-]+", phone) or not 7 <= sum(c.isdigit() for c in phone) <= 15:
            raise ValueError("Телефон должен содержать от 7 до 15 цифр.")
        email = str(email or "").strip()
        if email and (len(email) > 150 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
            raise ValueError("Укажите корректный адрес электронной почты или оставьте поле пустым.")
        notes = text(notes, "Примечание", 0, 2000)
        with self.db.transaction() as conn:
            if client_id is None:
                client_id = conn.execute(
                    "INSERT INTO clients(full_name, phone, email, notes) VALUES (?, ?, ?, ?)",
                    (full_name, phone, email, notes),
                ).lastrowid
            else:
                if not conn.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone():
                    raise ValueError("Клиент не найден.")
                conn.execute(
                    "UPDATE clients SET full_name = ?, phone = ?, email = ?, notes = ? WHERE id = ?",
                    (full_name, phone, email, notes, client_id),
                )
        return client_id

    def delete_client(self, session, client_id):
        self._admin(session)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

    def list_devices(self, session, client_id=None):
        self._admin(session)
        return self._rows(
            """SELECT d.*, c.full_name client_name FROM devices d
               JOIN clients c ON c.id = d.client_id"""
            + (" WHERE d.client_id = ?" if client_id else "")
            + " ORDER BY d.id DESC",
            (client_id,) if client_id else (),
        )

    def save_device(
        self, session, client_id, device_type, brand, model, serial_number="", notes="", device_id=None
    ):
        self._admin(session)
        device_type = text(device_type, "Тип устройства", 2, 50)
        brand = text(brand, "Производитель", 1, 60)
        model = text(model, "Модель", 1, 100)
        serial_number = text(serial_number, "Серийный номер", 0, 100) or None
        notes = text(notes, "Примечание", 0, 2000)
        if not self._one("SELECT id FROM clients WHERE id = ?", (client_id,)):
            raise ValueError("Выберите существующего клиента.")
        values = (client_id, device_type, brand, model, serial_number, notes)
        with self.db.transaction() as conn:
            if device_id is None:
                device_id = conn.execute(
                    """INSERT INTO devices(client_id, device_type, brand, model, serial_number, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""", values
                ).lastrowid
            else:
                old = self._one("SELECT * FROM devices WHERE id = ?", (device_id,))
                if not old:
                    raise ValueError("Устройство не найдено.")
                if old["client_id"] != client_id and self._one(
                    "SELECT id FROM repair_orders WHERE device_id = ?", (device_id,)
                ):
                    raise ValueError("Нельзя сменить владельца устройства, для которого есть заявки.")
                conn.execute(
                    """UPDATE devices SET client_id = ?, device_type = ?, brand = ?, model = ?,
                       serial_number = ?, notes = ? WHERE id = ?""", (*values, device_id)
                )
        return device_id

    def delete_device(self, session, device_id):
        self._admin(session)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    def list_services(self, session, active_only=False):
        self._actor(session)
        return self._rows(
            "SELECT * FROM services" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY name"
        )

    def save_service(self, session, name, price, active=True, service_id=None):
        self._admin(session)
        name = text(name, "Название услуги", 2)
        kopecks = price_to_kopecks(price)
        with self.db.transaction() as conn:
            if conn.execute(
                "SELECT id FROM services WHERE casefold(name) = casefold(?) AND id != coalesce(?, -1)",
                (name, service_id),
            ).fetchone():
                raise ValueError("Услуга с таким названием уже существует.")
            if service_id is None:
                service_id = conn.execute(
                    "INSERT INTO services(name, price_kopecks, is_active) VALUES (?, ?, ?)",
                    (name, kopecks, int(bool(active))),
                ).lastrowid
            else:
                if not self._one("SELECT id FROM services WHERE id = ?", (service_id,)):
                    raise ValueError("Услуга не найдена.")
                conn.execute(
                    "UPDATE services SET name = ?, price_kopecks = ?, is_active = ? WHERE id = ?",
                    (name, kopecks, int(bool(active)), service_id),
                )
        return service_id

    def statuses(self, session):
        self._actor(session)
        return self._rows("SELECT * FROM repair_statuses ORDER BY sort_order")

    def _status(self, code):
        status = self._one("SELECT * FROM repair_statuses WHERE code = ?", (code,))
        if not status:
            raise ValueError("Неизвестный статус.")
        return status

    def _valid_master(self, master_id):
        if not self._one(
            "SELECT id FROM users WHERE id = ? AND role = 'master' AND is_active = 1", (master_id,)
        ):
            raise ValueError("Выберите действующего мастера.")

    @staticmethod
    def _due_date(value):
        if not value:
            return None
        try:
            result = date.fromisoformat(str(value))
        except ValueError as error:
            raise ValueError("Дата готовности должна иметь формат ГГГГ-ММ-ДД.") from error
        if result < date.today():
            raise ValueError("Плановая дата не может быть раньше сегодняшней.")
        return result.isoformat()

    def create_order(self, session, device_id, master_id, complaint, due_date=None):
        actor = self._admin(session)
        self._valid_master(master_id)
        complaint = text(complaint, "Описание неисправности", 5, 3000)
        due_date = self._due_date(due_date)
        if not self._one("SELECT id FROM devices WHERE id = ?", (device_id,)):
            raise ValueError("Выберите зарегистрированное устройство.")
        accepted = self._status("accepted")
        with self.db.transaction() as conn:
            order_id = conn.execute(
                """INSERT INTO repair_orders(device_id, created_by, master_id, status_id, complaint, due_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, actor["id"], master_id, accepted["id"], complaint, due_date),
            ).lastrowid
            conn.execute(
                """INSERT INTO order_status_history(order_id, to_status_id, changed_by, note)
                   VALUES (?, ?, ?, 'Заявка зарегистрирована')""",
                (order_id, accepted["id"], actor["id"]),
            )
        return order_id

    def list_orders(self, session, search="", status_code=None, master_id=None, start=None, end=None):
        actor = self._actor(session)
        conditions, parameters = [], []
        if actor["role"] == "master":
            conditions.append("o.master_id = ?")
            parameters.append(actor["id"])
        if search:
            conditions.append(
                """instr(casefold(c.full_name || ' ' || c.phone || ' ' || d.brand || ' ' || d.model
                   || ' ' || coalesce(d.serial_number, '') || ' ' || o.id), casefold(?)) > 0"""
            )
            parameters.append(str(search).strip().removeprefix("№").strip().lstrip("#"))
        if status_code:
            conditions.append("s.code = ?")
            parameters.append(status_code)
        if master_id:
            conditions.append("o.master_id = ?")
            parameters.append(master_id)
        if start:
            conditions.append("date(o.created_at) >= ?")
            parameters.append(start)
        if end:
            conditions.append("date(o.created_at) <= ?")
            parameters.append(end)
        return self._rows(
            """SELECT o.*, c.full_name client_name, c.phone, c.email,
               d.device_type, d.brand, d.model, d.serial_number,
               u.full_name master_name, s.code status_code, s.name status_name, s.is_terminal,
               coalesce((SELECT sum(os.quantity * os.unit_price_kopecks)
                         FROM order_services os WHERE os.order_id = o.id), 0) total_kopecks
               FROM repair_orders o
               JOIN devices d ON d.id = o.device_id
               JOIN clients c ON c.id = d.client_id
               JOIN users u ON u.id = o.master_id
               JOIN repair_statuses s ON s.id = o.status_id"""
            + (" WHERE " + " AND ".join(conditions) if conditions else "")
            + " ORDER BY o.id DESC",
            parameters,
        )

    def order_detail(self, session, order_id):
        actor = self._actor(session)
        order = self._one(
            """SELECT o.*, s.code status_code, s.name status_name, s.is_terminal,
               d.device_type, d.brand, d.model, d.serial_number, c.full_name client_name,
               c.phone, c.email, u.full_name master_name
               FROM repair_orders o JOIN repair_statuses s ON s.id = o.status_id
               JOIN devices d ON d.id = o.device_id JOIN clients c ON c.id = d.client_id
               JOIN users u ON u.id = o.master_id WHERE o.id = ?""", (order_id,)
        )
        if not order:
            raise ValueError("Заявка не найдена.")
        if actor["role"] != "admin" and order["master_id"] != actor["id"]:
            raise PermissionError("Нет доступа к заявке другого мастера.")
        order["services"] = self._rows(
            """SELECT os.*, s.name FROM order_services os
               JOIN services s ON s.id = os.service_id WHERE os.order_id = ? ORDER BY os.id""",
            (order_id,),
        )
        order["history"] = self._rows(
            """SELECT h.*, f.name from_name, t.name to_name, u.full_name employee
               FROM order_status_history h LEFT JOIN repair_statuses f ON f.id = h.from_status_id
               JOIN repair_statuses t ON t.id = h.to_status_id JOIN users u ON u.id = h.changed_by
               WHERE h.order_id = ? ORDER BY h.id DESC""", (order_id,)
        )
        order["total_kopecks"] = sum(
            row["quantity"] * row["unit_price_kopecks"] for row in order["services"]
        )
        return order

    def _editable_order(self, session, order_id):
        order = self.order_detail(session, order_id)
        if order["is_terminal"]:
            raise ValueError("Завершённая или отменённая заявка доступна только для просмотра.")
        return order

    def update_order(self, session, order_id, complaint, master_id, due_date):
        self._admin(session)
        previous = self._editable_order(session, order_id)
        self._valid_master(master_id)
        complaint = text(complaint, "Описание неисправности", 5, 3000)
        # Существующий просроченный срок разрешаем сохранить без изменения.
        if due_date != previous["due_date"]:
            due_date = self._due_date(due_date)
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE repair_orders SET complaint = ?, master_id = ?, due_date = ?,
                   updated_at = datetime('now', 'localtime') WHERE id = ?""",
                (complaint, master_id, due_date, order_id),
            )

    def save_diagnosis(self, session, order_id, diagnosis):
        self._editable_order(session, order_id)
        diagnosis = text(diagnosis, "Диагностика", 0, 4000)
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE repair_orders SET diagnosis = ?, updated_at = datetime('now', 'localtime')
                   WHERE id = ?""", (diagnosis, order_id)
            )

    def change_status(self, session, order_id, status_code, note=""):
        actor = self._actor(session)
        order = self._editable_order(session, order_id)
        if status_code not in TRANSITIONS[order["status_code"]]:
            raise ValueError("Такой переход статуса недопустим для текущего этапа ремонта.")
        target = self._status(status_code)
        note = text(note, "Комментарий", 0, 2000)
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE repair_orders SET status_id = ?, updated_at = datetime('now', 'localtime'),
                   closed_at = CASE WHEN ? THEN datetime('now', 'localtime') ELSE NULL END WHERE id = ?""",
                (target["id"], target["is_terminal"], order_id),
            )
            conn.execute(
                """INSERT INTO order_status_history
                   (order_id, from_status_id, to_status_id, changed_by, note) VALUES (?, ?, ?, ?, ?)""",
                (order_id, order["status_id"], target["id"], actor["id"], note),
            )

    def add_order_service(self, session, order_id, service_id, quantity=1, price=None):
        self._editable_order(session, order_id)
        if type(quantity) is not int or not 1 <= quantity <= 1000:
            raise ValueError("Количество должно быть целым числом от 1 до 1000.")
        service = self._one("SELECT * FROM services WHERE id = ? AND is_active = 1", (service_id,))
        if not service:
            raise ValueError("Выберите действующую услугу из справочника.")
        unit_price = service["price_kopecks"] if price is None else price_to_kopecks(price)
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO order_services(order_id, service_id, quantity, unit_price_kopecks)
                   VALUES (?, ?, ?, ?)""", (order_id, service_id, quantity, unit_price)
            )

    def remove_order_service(self, session, order_id, item_id):
        self._editable_order(session, order_id)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM order_services WHERE id = ? AND order_id = ?", (item_id, order_id))

    def report(self, session, start, end):
        try:
            start, end = date.fromisoformat(start), date.fromisoformat(end)
        except (TypeError, ValueError) as error:
            raise ValueError("Укажите корректный период отчёта.") from error
        if start > end:
            raise ValueError("Начало периода не может быть позже окончания.")
        rows = self.list_orders(session, start=start.isoformat(), end=end.isoformat())
        return {
            "rows": rows,
            "count": len(rows),
            "active": sum(not row["is_terminal"] for row in rows),
            "ready": sum(row["status_code"] == "ready" for row in rows),
            "issued_amount": sum(
                row["total_kopecks"] for row in rows if row["status_code"] == "issued"
            ),
        }
