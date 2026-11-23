"""Адаптер дизайн-токенов в Qt Style Sheets."""

from pathlib import Path

from PyQt5.QtGui import QFont, QFontDatabase

COLORS = {
    "bg": "#f3f5f7",
    "surface": "#ffffff",
    "fg": "#202b36",
    "muted": "#536170",
    "border": "#7e8d9b",
    "rule": "#dce2e8",
    "accent": "#a34117",
    "accent_hover": "#873412",
    "selection": "#f9e9df",
    "success": "#246849",
    "warning": "#775516",
    "error": "#a02e2e",
}


def apply_theme(application):
    assets = Path(__file__).resolve().parents[1] / "assets"
    for font in sorted(assets.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(font))
    application.setStyle("Fusion")
    application.setFont(QFont("Fira Sans", 10))
    c = COLORS
    application.setStyleSheet(
        f"""
        QWidget {{
            color: {c['fg']}; font-family: "Fira Sans", "Noto Sans"; font-size: 14px;
        }}
        QMainWindow, QDialog {{ background: {c['bg']}; }}
        QLabel {{ background: transparent; }}
        QLabel[role="title"] {{ font-size: 24px; font-weight: 600; }}
        QLabel[role="subtitle"], QLabel[role="muted"] {{ color: {c['muted']}; }}
        QLabel[role="mono"] {{ font-family: "DejaVu Sans Mono"; }}
        QLabel[role="error"] {{
            color: {c['error']}; background: #fceeee; padding: 12px; border-radius: 4px;
        }}
        QFrame#brand {{ background: {c['fg']}; }}
        QFrame#brand QLabel {{ color: #ffffff; }}
        QFrame#brand QLabel[role="subtitle"] {{ color: #ced7df; }}
        QFrame#brand QPushButton {{
            color: #ffffff; background: #364553; border-color: #8795a3;
        }}
        QFrame#brand QPushButton:hover {{ background: #475968; }}
        QFrame#brand QPushButton:focus {{ border: 2px solid #ffffff; }}
        QFrame#preview {{
            background: {c['surface']}; border: 1px solid {c['rule']}; border-radius: 4px;
        }}
        QPushButton {{
            min-height: 32px; padding: 0 14px; border: 2px solid {c['border']};
            border-radius: 4px; background: {c['surface']};
        }}
        QPushButton:hover {{ background: #e9eef2; }}
        QPushButton:pressed {{ background: #dce2e8; }}
        QPushButton:focus {{ border: 2px solid {c['accent']}; }}
        QPushButton[primary="true"] {{
            background: {c['accent']}; color: #ffffff; border-color: {c['accent']};
            min-height: 36px; font-weight: 500;
        }}
        QPushButton[primary="true"]:hover {{ background: {c['accent_hover']}; }}
        QPushButton[primary="true"]:pressed {{ background: #6e2b10; }}
        QPushButton[primary="true"]:focus {{ border: 2px solid {c['fg']}; }}
        QPushButton:disabled {{
            color: #65717b; background: #e6eaee; border-color: #c2cbd3;
        }}
        QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox {{
            background: {c['surface']}; border: 2px solid {c['border']};
            border-radius: 4px; padding: 5px 8px; min-height: 24px;
            selection-background-color: {c['accent']}; selection-color: #ffffff;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
        QDateEdit:focus, QSpinBox:focus {{ border-color: {c['accent']}; }}
        QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
            color: #65717b; background: #e6eaee; border-color: #c2cbd3;
        }}
        QComboBox::drop-down, QDateEdit::drop-down {{
            width: 24px; border-left: 1px solid {c['border']};
        }}
        QComboBox::down-arrow, QDateEdit::down-arrow {{
            image: url("{(assets / 'chevron-down.svg').as_posix()}"); width: 16px; height: 16px;
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border; subcontrol-position: top right; width: 24px;
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border; subcontrol-position: bottom right; width: 24px;
        }}
        QSpinBox::up-arrow {{
            image: url("{(assets / 'chevron-up.svg').as_posix()}"); width: 12px; height: 12px;
        }}
        QSpinBox::down-arrow {{
            image: url("{(assets / 'chevron-down.svg').as_posix()}"); width: 12px; height: 12px;
        }}
        QComboBox QAbstractItemView {{
            background: {c['surface']}; selection-background-color: {c['selection']};
            selection-color: {c['fg']}; padding: 4px;
        }}
        QCheckBox {{ spacing: 8px; min-height: 28px; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; }}
        QCheckBox:focus {{ outline: 2px solid {c['accent']}; }}
        QTabWidget::pane {{ border: 0; background: {c['bg']}; }}
        QTabBar::tab {{
            padding: 12px 18px; margin-right: 4px; background: #e4e9ee;
            border: 2px solid transparent; border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:selected {{
            color: {c['accent']}; background: {c['surface']};
            border-bottom: 2px solid {c['accent']};
        }}
        QTabBar::tab:hover {{ background: #ffffff; }}
        QTabBar::tab:focus {{ border: 2px solid {c['accent']}; }}
        QTableWidget {{
            background: {c['surface']}; border: 1px solid {c['rule']};
            selection-background-color: {c['selection']}; selection-color: {c['fg']};
            gridline-color: {c['rule']};
        }}
        QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {c['rule']}; }}
        QTableWidget::item:focus {{ border: 2px solid {c['accent']}; }}
        QHeaderView::section {{
            background: #e8edf1; color: {c['muted']}; padding: 10px 8px;
            border: 0; border-bottom: 1px solid {c['rule']};
        }}
        QTableCornerButton::section {{ background: #e8edf1; border: 0; }}
        QGroupBox {{
            margin-top: 12px; padding-top: 16px; border: 1px solid {c['rule']};
            background: {c['surface']}; border-radius: 4px;
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
        QStatusBar {{ background: #e8edf1; color: {c['muted']}; }}
        QSplitter::handle {{ background: transparent; width: 16px; }}
        QToolTip {{ background: {c['fg']}; color: #ffffff; padding: 6px; border: 0; }}
        """
    )
