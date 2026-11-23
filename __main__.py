"""Запуск: python -m repair_service [--demo] [--database путь]."""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from PyQt5.QtCore import QLibraryInfo, QLocale, QTranslator
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from .database import Database
from .demo import seed_demo
from .ui.dialogs import LoginDialog, SetupDialog
from .ui.theme import apply_theme
from .ui.window import MainWindow
from .workshop import Workshop


def main():
    parser = argparse.ArgumentParser(description="Оконная система учёта ремонта компьютерной техники")
    parser.add_argument("--demo", action="store_true", help="Отдельная база с вымышленными примерами")
    parser.add_argument("--database", type=Path, help="Путь к отдельному файлу базы SQLite")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Ремонт")
    app.setOrganizationName("Coursework")
    app.setQuitOnLastWindowClosed(False)
    QLocale.setDefault(QLocale(QLocale.Russian, QLocale.Russia))
    translator = QTranslator(app)
    translator.load("qt_ru", QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    app.installTranslator(translator)
    apply_theme(app)
    path = args.database or Path(__file__).parent / "data" / (
        "demo.sqlite3" if args.demo else "workshop.sqlite3"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path.parent / "application.log",
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    def unhandled(error_type, value, traceback):
        logging.error("Необработанная ошибка", exc_info=(error_type, value, traceback))
        QMessageBox.critical(
            None, "Ошибка приложения",
            "Возникла непредвиденная ошибка. Подробности записаны в application.log рядом с базой данных."
        )

    sys.excepthook = unhandled
    try:
        database = Database(path)
    except (OSError, ValueError, sqlite3.Error) as error:
        # Здесь приложение ещё не запущено; не оставляем пользователя без сообщения.
        logging.exception("Не удалось открыть базу данных")
        QMessageBox.critical(None, "Ошибка базы данных", str(error))
        return 1
    workshop = Workshop(database)
    try:
        if args.demo:
            seed_demo(workshop)
        if workshop.needs_setup() and SetupDialog(workshop).exec_() != QDialog.Accepted:
            return 0
        while True:
            login = LoginDialog(workshop, args.demo)
            if login.exec_() != QDialog.Accepted:
                break
            window = MainWindow(workshop, login.result_value, args.demo)
            window.show()
            app.exec_()
            if not window.relogin:
                break
            window.deleteLater()
        return 0
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
