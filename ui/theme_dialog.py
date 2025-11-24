from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                           QComboBox, QColorDialog, QGroupBox, QFormLayout)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
import json
import os

class ThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("颜色主题配置")
        self.setMinimumWidth(500)
        self.init_ui()
        self.load_themes()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 预设主题选择
        theme_select = QHBoxLayout()
        theme_select.addWidget(QLabel("选择预设主题:"))
        self.theme_combo = QComboBox()
        self.theme_combo.currentIndexChanged.connect(self.on_theme_selected)
        theme_select.addWidget(self.theme_combo)
        layout.addLayout(theme_select)

        # 颜色配置组
        colors_group = QGroupBox("颜色设置")
        form_layout = QFormLayout()

        # 创建颜色选择按钮
        self.color_buttons = {}
        color_items = {
            'background_color': '背景颜色',
            'text_color': '文字颜色',
            'button_color': '按钮颜色',
            'button_hover_color': '按钮悬停颜色',
            'table_header_color': '表格表头颜色',
            'table_border_color': '表格边框颜色',
            'table_gridline_color': '表格网格颜色',
            'groupbox_border_color': '分组框边框颜色'
        }

        for key, label in color_items.items():
            btn = QPushButton()
            btn.setFixedSize(80, 25)
            btn.clicked.connect(lambda checked, k=key: self.choose_color(k))
            self.color_buttons[key] = btn
            form_layout.addRow(label, btn)

        colors_group.setLayout(form_layout)
        layout.addWidget(colors_group)

        # 按钮区域
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存为新主题")
        save_btn.clicked.connect(self.save_theme)
        apply_btn = QPushButton("应用")
        apply_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        # 预设主题
        self.preset_themes = {
            "Win11 亮色": {
                'background_color': '#FFFFFF',
                'text_color': '#202020',
                'button_color': '#0067C0',
                'button_hover_color': '#0078D4',
                'table_header_color': '#F5F5F5',
                'table_border_color': '#E6E6E6',
                'table_gridline_color': '#F0F0F0',
                'groupbox_border_color': '#E6E6E6'
            },
            "Win11 暗色": {
                'background_color': '#202020',
                'text_color': '#FFFFFF',
                'button_color': '#0067C0',
                'button_hover_color': '#0078D4',
                'table_header_color': '#2D2D2D',
                'table_border_color': '#404040',
                'table_gridline_color': '#333333',
                'groupbox_border_color': '#404040'
            },
            "VS Code 深色": {
                'background_color': '#1E1E1E',
                'text_color': '#D4D4D4',
                'button_color': '#0E639C',
                'button_hover_color': '#1177BB',
                'table_header_color': '#252526',
                'table_border_color': '#3C3C3C',
                'table_gridline_color': '#2D2D2D',
                'groupbox_border_color': '#3C3C3C'
            },
            "IntelliJ 浅色": {
                'background_color': '#F2F2F2',
                'text_color': '#2B2B2B',
                'button_color': '#4A7AB7',
                'button_hover_color': '#5689C7',
                'table_header_color': '#E6E6E6',
                'table_border_color': '#D1D1D1',
                'table_gridline_color': '#EBEBEB',
                'groupbox_border_color': '#D1D1D1'
            },
            "Material 深邃蓝": {
                'background_color': '#263238',
                'text_color': '#EEFFFF',
                'button_color': '#82AAFF',
                'button_hover_color': '#92BAFF',
                'table_header_color': '#2E3C43',
                'table_border_color': '#37474F',
                'table_gridline_color': '#314549',
                'groupbox_border_color': '#37474F'
            },
            "Material 翡翠绿": {
                'background_color': '#1B2820',
                'text_color': '#E0F2F1',
                'button_color': '#00BFA5',
                'button_hover_color': '#1DE9B6',
                'table_header_color': '#243229',
                'table_border_color': '#2E3F35',
                'table_gridline_color': '#28382F',
                'groupbox_border_color': '#2E3F35'
            },
            "Solarized 浅色": {
                'background_color': '#FDF6E3',
                'text_color': '#586E75',
                'button_color': '#268BD2',
                'button_hover_color': '#2AA198',
                'table_header_color': '#EEE8D5',
                'table_border_color': '#D3CBB7',
                'table_gridline_color': '#E9E2C8',
                'groupbox_border_color': '#D3CBB7'
            },
            "Solarized 暗色": {
                'background_color': '#002B36',
                'text_color': '#839496',
                'button_color': '#268BD2',
                'button_hover_color': '#2AA198',
                'table_header_color': '#073642',
                'table_border_color': '#094352',
                'table_gridline_color': '#083945',
                'groupbox_border_color': '#094352'
            },
            "Nord": {
                'background_color': '#2E3440',
                'text_color': '#D8DEE9',
                'button_color': '#5E81AC',
                'button_hover_color': '#81A1C1',
                'table_header_color': '#3B4252',
                'table_border_color': '#434C5E',
                'table_gridline_color': '#3B4252',
                'groupbox_border_color': '#434C5E'
            },
            "GitHub 浅色": {
                'background_color': '#FFFFFF',
                'text_color': '#24292E',
                'button_color': '#2EA44F',
                'button_hover_color': '#2C974B',
                'table_header_color': '#F6F8FA',
                'table_border_color': '#E1E4E8',
                'table_gridline_color': '#F0F2F4',
                'groupbox_border_color': '#E1E4E8'
            },
            "Qt Creator": {
                'background_color': '#F6F6F6',
                'text_color': '#000000',
                'button_color': '#0060A8',
                'button_hover_color': '#0070C8',
                'table_header_color': '#E6E6E6',
                'table_border_color': '#C0C0C0',
                'table_gridline_color': '#E0E0E0',
                'groupbox_border_color': '#C0C0C0'
            },
            "Qt 原生": {
                'background_color': '#F0F0F0',
                'text_color': '#000000',
                'button_color': '#E1E1E1',
                'button_hover_color': '#D4D4D4',
                'table_header_color': '#F0F0F0',
                'table_border_color': '#B4B4B4',
                'table_gridline_color': '#D9D9D9',
                'groupbox_border_color': '#B4B4B4'
            },
            "Wireshark": {
                'background_color': '#FFFFFF',
                'text_color': '#222222',
                'button_color': '#346E9E',
                'button_hover_color': '#4183B7',
                'table_header_color': '#E9ECEF',
                'table_border_color': '#DEE2E6',
                'table_gridline_color': '#E9ECEF',
                'groupbox_border_color': '#DEE2E6'
            },
            "QtDesigner": {
                'background_color': '#FFFFFF',
                'text_color': '#1A1A1A',
                'button_color': '#007ACC',
                'button_hover_color': '#0088E2',
                'table_header_color': '#F5F5F5',
                'table_border_color': '#DDDDDD',
                'table_gridline_color': '#EEEEEE',
                'groupbox_border_color': '#DDDDDD'
            }
        }

    def choose_color(self, key):
        current_color = self.color_buttons[key].palette().button().color()
        color = QColorDialog.getColor(current_color, self, f"选择{key}颜色")
        if color.isValid():
            self.set_button_color(key, color)

    def set_button_color(self, key, color):
        self.color_buttons[key].setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #ccc;"
        )

    def get_current_theme(self):
        return {
            key: self.color_buttons[key].palette().button().color().name()
            for key in self.color_buttons
        }

    def apply_theme(self, theme):
        for key, color in theme.items():
            if key in self.color_buttons:
                self.set_button_color(key, QColor(color))

    def save_theme(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "保存主题", "请输入主题名称:")
        if ok and name:
            theme = self.get_current_theme()
            self.preset_themes[name] = theme
            self.save_themes_to_file()
            if self.theme_combo.findText(name) == -1:
                self.theme_combo.addItem(name)

    def load_themes(self):
        try:
            if os.path.exists('config/themes.json'):
                with open('config/themes.json', 'r', encoding='utf-8') as f:
                    saved_themes = json.load(f)
                    self.preset_themes.update(saved_themes)
        except Exception as e:
            print(f"加载主题配置失败: {e}")

        # 添加所有主题到下拉框
        self.theme_combo.addItems(self.preset_themes.keys())

    def save_themes_to_file(self):
        try:
            if not os.path.exists('config'):
                os.makedirs('config')
            with open('config/themes.json', 'w', encoding='utf-8') as f:
                json.dump(self.preset_themes, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存主题配置失败: {e}")

    def on_theme_selected(self, index):
        theme_name = self.theme_combo.currentText()
        if theme_name in self.preset_themes:
            self.apply_theme(self.preset_themes[theme_name]) 