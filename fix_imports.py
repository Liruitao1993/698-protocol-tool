#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复main_window.py的导入语句"""

# 读取损坏的文件
with open('ui/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 正确的导入语句（前20行）
correct_imports = """from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QComboBox, QLineEdit, QPushButton, QLabel, 
                           QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout, QSpinBox, QHeaderView,
                           QFileDialog, QMessageBox, QTextEdit, QCheckBox, QDockWidget, QScrollArea, 
                           QActionGroup, QMenu, QAction, QDialog, QDialogButtonBox, QSizePolicy, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QRegExpValidator, QFont, QColor
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QApplication, QStyleFactory
import configparser
import os
import csv
from functools import partial
import re
from PyQt5.QtCore import QDateTime
import json
import serial.tools.list_ports
import threading
from utils.logger import Logger

"""

# 从第21行开始保留（class MainWindow开始）
fixed_content = correct_imports + ''.join(lines[21:])

# 写入修复后的文件
with open('ui/main_window.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print(f"✅ 文件修复完成！")
print(f"   - 删除了前21行重复导入")
print(f"   - 保留了{len(lines) - 21}行有效代码")
print(f"   - 总行数从{len(lines)}行减少到{len(fixed_content.split(chr(10)))}行")
