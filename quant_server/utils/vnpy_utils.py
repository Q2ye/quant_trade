# vnpy_utils.py
"""vn.py 工具函数集合"""
from PyQt5 import QtWidgets, QtCore, QtGui


def load_qt_style(widget, style_name="dark"):
    """
    加载Qt样式表

    :param widget: 要应用样式的Qt部件
    :param style_name: 样式名称 (dark/light)
    """
    if style_name == "dark":
        # 深色主题样式
        dark_style = """
        QWidget {
            background-color: #2D2D30;
            color: #DCDCDC;
            font-family: "Segoe UI", "Microsoft YaHei";
        }

        QMainWindow, QDialog {
            background-color: #252526;
            border: 1px solid #3F3F46;
        }

        QTabWidget::pane {
            border: 1px solid #3F3F46;
            background: #252526;
        }

        QTabBar::tab {
            background: #333337;
            color: #BBBBBB;
            padding: 8px 15px;
            border: 1px solid #3F3F46;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }

        QTabBar::tab:selected {
            background: #252526;
            color: #FFFFFF;
            border-bottom: 2px solid #007ACC;
        }

        QDockWidget {
            titlebar-close-icon: url(:/icons/close.png);
            titlebar-normal-icon: url(:/icons/undock.png);
            background: #252526;
        }

        QDockWidget::title {
            background: #333337;
            padding: 5px;
            text-align: center;
        }

        QTreeView, QTableView, QListView {
            background-color: #1E1E1E;
            alternate-background-color: #252526;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
            gridline-color: #3F3F46;
        }

        QHeaderView::section {
            background-color: #333337;
            color: #DCDCDC;
            padding: 4px;
            border: 1px solid #3F3F46;
        }

        QMenuBar {
            background-color: #333337;
            color: #DCDCDC;
        }

        QMenuBar::item:selected {
            background: #3F3F46;
        }

        QMenu {
            background-color: #333337;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
        }

        QMenu::item:selected {
            background-color: #007ACC;
        }

        QToolBar {
            background: #333337;
            border: none;
            padding: 2px;
        }

        QToolButton {
            background: #333337;
            color: #DCDCDC;
            padding: 5px;
            border: 1px solid #3F3F46;
            border-radius: 3px;
        }

        QToolButton:hover {
            background: #3F3F46;
        }

        QToolButton:pressed {
            background: #007ACC;
        }

        QStatusBar {
            background: #333337;
            color: #DCDCDC;
        }

        QScrollBar:vertical {
            background: #1E1E1E;
            width: 12px;
        }

        QScrollBar::handle:vertical {
            background: #3F3F46;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background: #007ACC;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: none;
        }

        QPushButton {
            background-color: #333337;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
            padding: 5px 15px;
            border-radius: 3px;
        }

        QPushButton:hover {
            background-color: #3F3F46;
        }

        QPushButton:pressed {
            background-color: #007ACC;
        }

        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #1E1E1E;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
            padding: 5px;
            selection-background-color: #007ACC;
        }

        QLabel {
            color: #DCDCDC;
        }

        QProgressBar {
            border: 1px solid #3F3F46;
            border-radius: 3px;
            text-align: center;
            background: #1E1E1E;
        }

        QProgressBar::chunk {
            background: #007ACC;
        }

        QComboBox {
            background-color: #1E1E1E;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
            padding: 5px;
        }

        QComboBox QAbstractItemView {
            background-color: #1E1E1E;
            color: #DCDCDC;
            border: 1px solid #3F3F46;
        }
        """
        widget.setStyleSheet(dark_style)
    elif style_name == "light":
        # 浅色主题样式
        light_style = """
        QWidget {
            background-color: #F0F0F0;
            color: #000000;
            font-family: "Segoe UI", "Microsoft YaHei";
        }

        QMainWindow, QDialog {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
        }

        QTabWidget::pane {
            border: 1px solid #CCCCCC;
            background: #FFFFFF;
        }

        QTabBar::tab {
            background: #E0E0E0;
            color: #333333;
            padding: 8px 15px;
            border: 1px solid #CCCCCC;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }

        QTabBar::tab:selected {
            background: #FFFFFF;
            color: #000000;
            border-bottom: 2px solid #007ACC;
        }

        QDockWidget {
            titlebar-close-icon: url(:/icons/close.png);
            titlebar-normal-icon: url(:/icons/undock.png);
            background: #FFFFFF;
        }

        QDockWidget::title {
            background: #E0E0E0;
            padding: 5px;
            text-align: center;
        }

        QTreeView, QTableView, QListView {
            background-color: #FFFFFF;
            alternate-background-color: #F5F5F5;
            color: #000000;
            border: 1px solid #CCCCCC;
            gridline-color: #CCCCCC;
        }

        QHeaderView::section {
            background-color: #E0E0E0;
            color: #000000;
            padding: 4px;
            border: 1px solid #CCCCCC;
        }

        QMenuBar {
            background-color: #E0E0E0;
            color: #000000;
        }

        QMenuBar::item:selected {
            background: #CCCCCC;
        }

        QMenu {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCCCCC;
        }

        QMenu::item:selected {
            background-color: #007ACC;
            color: #FFFFFF;
        }

        QToolBar {
            background: #E0E0E0;
            border: none;
            padding: 2px;
        }

        QToolButton {
            background: #E0E0E0;
            color: #000000;
            padding: 5px;
            border: 1px solid #CCCCCC;
            border-radius: 3px;
        }

        QToolButton:hover {
            background: #CCCCCC;
        }

        QToolButton:pressed {
            background: #007ACC;
            color: #FFFFFF;
        }

        QStatusBar {
            background: #E0E0E0;
            color: #000000;
        }

        QScrollBar:vertical {
            background: #F0F0F0;
            width: 12px;
        }

        QScrollBar::handle:vertical {
            background: #CCCCCC;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background: #007ACC;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: none;
        }

        QPushButton {
            background-color: #E0E0E0;
            color: #000000;
            border: 1px solid #CCCCCC;
            padding: 5px 15px;
            border-radius: 3px;
        }

        QPushButton:hover {
            background-color: #CCCCCC;
        }

        QPushButton:pressed {
            background-color: #007ACC;
            color: #FFFFFF;
        }

        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCCCCC;
            padding: 5px;
            selection-background-color: #007ACC;
            selection-color: #FFFFFF;
        }

        QLabel {
            color: #000000;
        }

        QProgressBar {
            border: 1px solid #CCCCCC;
            border-radius: 3px;
            text-align: center;
            background: #F0F0F0;
        }

        QProgressBar::chunk {
            background: #007ACC;
        }

        QComboBox {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCCCCC;
            padding: 5px;
        }

        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCCCCC;
        }
        """
        widget.setStyleSheet(light_style)
    else:
        # 默认系统样式
        pass