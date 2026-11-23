"""Изолированные вымышленные данные для демонстрации и снимков интерфейса."""

from datetime import date, datetime, timedelta

from .workshop import Workshop

DEMO_ADMIN_PASSWORD = "DemoAdmin!2026"
DEMO_MASTER_PASSWORD = "DemoMaster!2026"


def seed_demo(workshop: Workshop) -> bool:
    if not workshop.needs_setup():
        return False
    workshop.setup("Администратор Сервиса", "admin", DEMO_ADMIN_PASSWORD)
    admin = workshop.login("admin", DEMO_ADMIN_PASSWORD)
    master = workshop.create_user(admin, "Алексей Орлов", "master", DEMO_MASTER_PASSWORD, "master")
    second = workshop.create_user(admin, "Ирина Волкова", "master2", DEMO_MASTER_PASSWORD, "master")
    services = [
        workshop.save_service(admin, "Диагностика устройства", "500"),
        workshop.save_service(admin, "Чистка системы охлаждения", "1500"),
        workshop.save_service(admin, "Замена термопасты", "800"),
        workshop.save_service(admin, "Установка операционной системы", "1800"),
        workshop.save_service(admin, "Замена разъёма питания", "2400"),
        workshop.save_service(admin, "Замена накопителя SSD", "1200"),
    ]
    examples = [
        ("Анна Миронова", "Ноутбук", "Lenovo", "IdeaPad 5", "Перегревается и выключается под нагрузкой.", "repair"),
        ("Дмитрий Соколов", "Системный блок", "ASUS", "Prime B550", "Не включается после перепада напряжения.", "diagnostics"),
        ("Мария Лебедева", "Ноутбук", "HP", "ProBook 450", "Медленная загрузка системы, требуется замена накопителя.", "ready"),
        ("Сергей Крылов", "Монитор", "Samsung", "S24F350", "Экран мерцает после нескольких минут работы.", "accepted"),
        ("Ольга Белова", "Ноутбук", "Acer", "Aspire 7", "Разъём питания работает только в одном положении.", "repair"),
        ("Павел Новиков", "Системный блок", "MSI", "PRO H610M", "Требуется установка системы и настройка драйверов.", "issued"),
        ("Елена Морозова", "Ноутбук", "Dell", "Latitude 5420", "Вентилятор шумит, корпус сильно нагревается.", "ready"),
        ("Артём Громов", "Моноблок", "Lenovo", "IdeaCentre AIO", "Не загружается операционная система.", "cancelled"),
        ("Иван Фомин", "Ноутбук", "ASUS", "VivoBook 15", "Требуется диагностика после падения устройства.", "accepted"),
    ]
    for index, (name, kind, brand, model, complaint, target) in enumerate(examples):
        client = workshop.save_client(admin, name, f"+7 (900) 000-00-{index + 1:02d}")
        device = workshop.save_device(admin, client, kind, brand, model, f"DEMO-{index + 1:04d}")
        order = workshop.create_order(
            admin, device, master if index % 2 == 0 else second, complaint,
            (date.today() + timedelta(days=index % 4)).isoformat()
        )
        if target != "accepted":
            workshop.change_status(admin, order, "diagnostics", "Устройство принято на диагностику")
            workshop.save_diagnosis(admin, order, "Выполнен осмотр. Причина неисправности установлена; объём работ согласован.")
            workshop.add_order_service(admin, order, services[0])
        if target in ("repair", "ready", "issued"):
            workshop.change_status(admin, order, "repair", "Приступили к выполнению работ")
            workshop.add_order_service(admin, order, services[1 + index % 5])
        if target in ("ready", "issued"):
            workshop.change_status(admin, order, "ready", "Проверка завершена, устройство готово")
        if target == "issued":
            workshop.change_status(admin, order, "issued", "Устройство выдано клиенту")
        if target == "cancelled":
            workshop.change_status(admin, order, "cancelled", "Клиент отказался от ремонта")
        # Для наглядного журнала меняем только даты вымышленных примеров.
        created = datetime.now() - timedelta(days=8 - index)
        with workshop.db.transaction() as conn:
            conn.execute(
                "UPDATE repair_orders SET created_at = ? WHERE id = ?",
                (created.isoformat(sep=" ", timespec="seconds"), order),
            )
    workshop.logout(admin)
    return True
