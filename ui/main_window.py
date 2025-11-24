from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
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

class MainWindow(QMainWindow):
    frame_send_requested = pyqtSignal(tuple)  # (frame_name, row)
    serial_connect_requested = pyqtSignal(dict)  # 添加串口连接请求信号
    
    def __init__(self):
        super().__init__()
        self.protocol = None  # 将在外部设置
        self.setWindowTitle("698.45协议测试系统")
        self.setMinimumSize(800, 600)
        
        # 确保配置目录存在
        if not os.path.exists('config'):
            os.makedirs('config')
        
        # 载入OAD配置
        self.oad_config = self.load_oad_config()
        if not self.oad_config:
            self.create_default_oad_config()
            self.oad_config = self.load_oad_config()
        
        # 初始化日志相关属性
        self.log_file = None
        self.log_file_name = ""
        self.log_buffer_size = 0
        self.MAX_BUFFER_SIZE = 500 * 1024 * 1024  # 500MB
        
        # 初始化窗口状态标志
        self.is_log_maximized = False
        self.is_config_maximized = False
        
        # 初始化UI
        self.init_ui()
        self.init_signals()
        
        # 更新串口列表
        self.update_port_list()
        
        # 加载配置（在UI初始化之后）
        self.load_serial_config()
        self.load_theme_config()
        
        # 应用样式
        self.apply_styles()
        
        # 创建日志窗口
        self.create_dockable_log_window()
        
        # 添加表格缩放功能
        self.table_zoom_factor = 1.0
        self.frame_table.viewport().installEventFilter(self)
        
        # 创建定时器定期更新串口列表
        self.port_update_timer = QTimer(self)
        self.port_update_timer.timeout.connect(self.update_port_list)
        self.port_update_timer.start(1000)
        
        # 加载保存的主题
        self.load_saved_theme()
        
        # 设置应用程序为 Fusion
        QApplication.setStyle("Fusion")
        
        # 设置全局边距
        self.setContentsMargins(10, 10, 10, 10)
        
        # 初始化日志系统
        self.logger = Logger()
        self.logger.info("应用程序启动")
        
        # 添加接收数据的处理方法
        self.init_receive_handler()

    def set_protocol(self, protocol):
        """设置协议对象"""
        self.protocol = protocol

    def init_signals(self):
        """初始化所有信号连接"""
        # 先断开所有已存在的连接，避免重复
        try:
            self.frame_table.cellChanged.disconnect()
            self.frame_table.itemDoubleClicked.disconnect()
            self.connect_btn.clicked.disconnect()
            # self.add_frame_btn.clicked.disconnect()  # 由TestSystem管理，此处不断开
            self.delete_frame_btn.clicked.disconnect()
            self.send_frame_btn.clicked.disconnect()
            self.clear_results_btn.clicked.disconnect()
            self.export_btn.clicked.disconnect()
            self.import_btn.clicked.disconnect()
        except:
            pass  # 忽略断开失败的错误
        
        # 重新连接信号
        # 表格相关信号
        self.frame_table.cellChanged.connect(self.on_cell_changed)
        self.frame_table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 串口相关信号
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        
        # 按钮相关信号（由TestSystem处理，此处不再连接add_frame_btn）
        # self.add_frame_btn.clicked.connect(self.add_new_frame)  # 已在main.py中连接
        self.delete_frame_btn.clicked.connect(self.delete_selected_frames)
        self.send_frame_btn.clicked.connect(self.send_all_frames)
        self.clear_results_btn.clicked.connect(self.clear_test_results)
        self.export_btn.clicked.connect(self.export_frames)
        self.import_btn.clicked.connect(self.import_frames)

    def update_port_list(self):
        """更新串口列表"""
        # 获取当前选中的串口
        current_port = self.port_combo.currentText()
        
        # 清空并更新串口列表
        self.port_combo.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports)
        
        # 如果之前选中的串口仍然在，则选中它
        index = self.port_combo.findText(current_port)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)

    def apply_styles(self):
        """应用样式表"""
        # 使用最小的样式设置，保持原生外观
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F0F0F0;
            }
            QGroupBox {
                margin-top: 6px;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
            }
        """)

    def init_ui(self):
        # 创建菜单栏
        menubar = self.menuBar()
        
        # 创建视图菜单
        self.view_menu = menubar.addMenu("视图")
        
        # 创建窗口显示子菜单
        windows_menu = QMenu("窗口", self)
        windows_menu.setObjectName("窗口")  # 设置对象名称
        self.view_menu.addMenu(windows_menu)
        
        # 添加主题风格子菜单
        style_menu = QMenu("主题风格", self)
        style_menu.setObjectName("主题风格")  # 设置对象名称
        self.view_menu.addMenu(style_menu)
        
        # 获取系统支持的所有样式
        available_styles = QStyleFactory.keys()
        
        # 建样式选择动作组
        style_group = QActionGroup(self)
        style_group.setExclusive(True)  # 确保只能选择一个样式
        
        # 添加所有可用的样式
        for style_name in available_styles:
            style_action = QAction(style_name, self)
            style_action.setCheckable(True)
            style_action.setChecked(QApplication.style().objectName() == style_name)
            style_action.triggered.connect(lambda checked, name=style_name: self.change_style(name))
            style_group.addAction(style_action)
            style_menu.addAction(style_action)
        
        # 保存子菜单的引用
        self.windows_menu = windows_menu
        self.style_menu = style_menu
        
        # 先创建所有控件
        # 控制域控件
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(['客户机发出(0)', '服务器发出(1)'])
        
        self.prm_combo = QComboBox()
        self.prm_combo.addItems(['从动站(0)', '启动站(1)'])
        
        self.split_combo = QComboBox()
        self.split_combo.addItems(['不分帧(0)', '分帧(1)'])
        
        self.sc_combo = QComboBox()
        self.sc_combo.addItems(['无数据域(0)', '有数据域(1)'])
        
        self.func_combo = QComboBox()
        self.func_combo.addItems([
            '保留(0)',
            '链路管理(1)',  # 链路连接管理（登录、心跳、退出登录）
            '保留(2)',
            '用户数据(3)',  # 应用连接管理及数据交换服务
            '保留(4)',
            '保留(5)',
            '保留(6)',
            '保留(7)'
        ])
        self.func_combo.setCurrentText('用户数据(3)')  # 设置默认选项
        
        # SA标志控件
        self.addr_type_combo = QComboBox()
        self.addr_type_combo.addItems([
            '单地址(0)',
            '通配地址(1)',
            '组地址(2)',
            '广播地址(3)'
        ])
        
        self.ext_logic_addr_combo = QComboBox()
        self.ext_logic_addr_combo.addItems([
            '无扩展逻辑地址(0)',
            '有扩展逻辑地址(1)'
        ])
        
        self.logic_addr_flag_combo = QComboBox()
        self.logic_addr_flag_combo.addItems([
            '无逻辑地址(0)',
            '有逻辑地址(1)'
        ])
        self.logic_addr_flag_combo.currentTextChanged.connect(self.on_logic_addr_flag_changed)
        
        # 修改地址长度为输入框
        self.addr_len_input = QLineEdit()
        self.addr_len_input.setText("6")  # 默认值为6
        self.addr_len_input.setPlaceholderText("范围0-15")
        # 限制输入范围为0-15的数字
        addr_len_validator = QIntValidator(0, 15)
        self.addr_len_input.setValidator(addr_len_validator)
        self.addr_len_input.setFixedWidth(60)  # 设置固定宽度
        self.addr_len_input.setAlignment(Qt.AlignCenter)  # 文本居中对齐

        self.sa_logic_addr = QLineEdit()
        self.sa_logic_addr.setPlaceholderText("如: 00")
        hex_validator = QRegExpValidator(QRegExp("^[0-9A-Fa-f]{2}$"))
        self.sa_logic_addr.setValidator(hex_validator)
        self.sa_logic_addr.setEnabled(False)  # 默认禁用

        # 创建客户机地址CA输入框（十进制输入，范围0-255）
        self.logic_addr = QLineEdit()
        self.logic_addr.setPlaceholderText("如: 16")
        self.logic_addr.setText("16")  # 默认值16
        dec_validator = QIntValidator(0, 255)
        self.logic_addr.setValidator(dec_validator)
        
        # 创建通信地址输入框（十六进制输入）
        self.comm_addr = QLineEdit()
        self.comm_addr.setText("010203040506")  # 设置默认值
        self.comm_addr.setPlaceholderText("如: 010203040506 (6字节)")
        comm_addr_validator = QRegExpValidator(QRegExp("^[0-9A-Fa-f]{1,12}$"))
        self.comm_addr.setValidator(comm_addr_validator)
        
        # 创建自定义数据输入框
        self.custom_data = QLineEdit()
        self.custom_data.setPlaceholderText("输入十六进制数据（可选）")
        hex_validator = QRegExpValidator(QRegExp("^[0-9A-Fa-f]*$"))
        self.custom_data.setValidator(hex_validator)
        
        # 创建SA逻辑地址输入框
        self.sa_logic_addr = QLineEdit()
        self.sa_logic_addr.setPlaceholderText("如: 00")
        sa_logic_validator = QRegExpValidator(QRegExp("^[0-9A-Fa-f]{2}$"))
        self.sa_logic_addr.setValidator(sa_logic_validator)
        self.sa_logic_addr.setEnabled(False)  # 默认禁用
        
        # 创建服务类型和数据类型选择框
        self.service_type_combo = QComboBox()
        self.service_type_combo.addItems([
            '建立应用连接请求',
            '断开应用连接请求',
            '读取请求',
            '设置请求',
            '操作请求',
            '上报应答',
            '代理请求'
        ])
        self.service_type_combo.currentTextChanged.connect(self.on_service_type_changed)
        
        self.service_data_type_combo = QComboBox()
        self.service_data_type_label = QLabel("数据类型:")
        self.service_data_type_label.setVisible(False)
        self.service_data_type_combo.setVisible(False)
        
        # 创建服务优先级和序号输入
        self.service_priority_combo = QComboBox()
        self.service_priority_combo.addItems(['0', '1', '2', '3'])
        self.service_priority = self.service_priority_combo.currentText()  # Initialize service_priority
        
        self.service_number_spin = QSpinBox()
        self.service_number_spin.setRange(0, 63)
        
        # 创建OAD控件
        self.oad_combo = QComboBox()
        if self.oad_config and 'OAD' in self.oad_config:
            self.oad_combo.addItems(self.oad_config['OAD'].keys())
        self.oad_combo.currentTextChanged.connect(self.on_oad_selected)
        
        self.oad_input = QLineEdit()
        self.oad_input.setPlaceholderText("输入OAD值（4字节十六进制）")
        oad_validator = QRegExpValidator(QRegExp("^[0-9A-Fa-f]{8}$"))
        self.oad_input.setValidator(oad_validator)
        
        
        # 创建主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 串口设置区域
        serial_group = QGroupBox("串口设置")
        serial_layout = QHBoxLayout()
        serial_layout.setSpacing(4)  # 减小控件间距
        serial_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        
        # 串口选择
        serial_layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setFixedWidth(80)  # 设置固定宽度
        serial_layout.addWidget(self.port_combo)

        # 波特率
        serial_layout.addWidget(QLabel("波特率:"))
        self.baud_combo = QComboBox()
        self.baud_combo.setFixedWidth(70)
        self.baud_combo.addItems(['9600', '19200', '38400', '115200'])
        serial_layout.addWidget(self.baud_combo)

        # 校验位
        serial_layout.addWidget(QLabel("校验位:"))
        self.parity_combo = QComboBox()
        self.parity_combo.setFixedWidth(90)
        self.parity_combo.addItems([
            '无校验(N)',
            '奇校验(O)',
            '偶校验(E)',
            '标记(M)',
            '空格(S)'
        ])
        serial_layout.addWidget(self.parity_combo)

        # 数据位
        serial_layout.addWidget(QLabel("数据位:"))
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.setFixedWidth(50)
        self.bytesize_combo.addItems(['8', '7', '6', '5'])
        serial_layout.addWidget(self.bytesize_combo)

        # 停止位
        serial_layout.addWidget(QLabel("停止位:"))
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.setFixedWidth(50)
        self.stopbits_combo.addItems(['1', '1.5', '2'])
        serial_layout.addWidget(self.stopbits_combo)

        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setFixedWidth(60)
        serial_layout.addWidget(self.connect_btn)
        
        serial_layout.addStretch()
        serial_group.setLayout(serial_layout)
        serial_group.setFixedHeight(60)  # 减小高度
        main_layout.addWidget(serial_group)

        # 创建协议配置的停靠口
        self.create_protocol_config_window()

        # 帧列表区域（主窗中心）
        frame_group = QGroupBox("帧列表")
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(6)
        frame_layout.setContentsMargins(10, 15, 10, 10)
        
        # 表格使用默认样式
        self.frame_table = QTableWidget()
        self.frame_table.setStyleSheet("")  # 移除自定义���式
        
        # 设置表格基本属性
        self.frame_table.setColumnCount(10)
        self.frame_table.setHorizontalHeaderLabels([
            '序号', '名称', '帧内容', '操作', '状态', '启用匹配', 
            '匹配规则', '匹配模式', '测试结果', '超时(ms)'
        ])
        
        # 设置各列的默认宽度和调整模式
        column_widths = {
            0: (40, QHeaderView.Fixed),              # 序号列
            1: (100, QHeaderView.Interactive),       # 名称列
            2: (300, QHeaderView.Interactive),       # 帧内容列
            3: (150, QHeaderView.Fixed),             # 操作列
            4: (80, QHeaderView.Fixed),              # 状态列
            5: (80, QHeaderView.Fixed),              # 启用匹配列
            6: (300, QHeaderView.Interactive),       # 匹配规则列
            7: (80, QHeaderView.Fixed),              # 匹配模式列
            8: (100, QHeaderView.Interactive),       # 测试结果列
            9: (80, QHeaderView.Fixed)               # 超时列
        }
        
        # 应用列宽设置
        header = self.frame_table.horizontalHeader()
        for col, (width, mode) in column_widths.items():
            self.frame_table.setColumnWidth(col, width)
            header.setSectionResizeMode(col, mode)
        
        # 允许用户调整列宽
        header.setStretchLastSection(False)
        
        # 设置表格的最小宽度，确保能显示所有内容
        min_total_width = sum(width for width, _ in column_widths.values())
        self.frame_table.setMinimumWidth(min_total_width)
        
        # 设置表格的其他属性
        self.frame_table.setShowGrid(True)
        self.frame_table.setAlternatingRowColors(True)  # 交替行颜色
        self.frame_table.verticalHeader().setVisible(False)  # 隐藏垂直表头
        
        # 设置表格内容的对齐方式
        self.frame_table.setStyleSheet("""
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget QLineEdit {
                padding: 2px;
            }
            /* 设置表格内容居中对齐 */
            QTableWidget::item {
                text-align: center;
            }
            /* 设置表头样式 */
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: none;
                border-right: 1px solid #d0d0d0;
                border-bottom: 1px solid #d0d0d0;
            }
        """)
        
        frame_layout.addWidget(self.frame_table)
        
        frame_group.setLayout(frame_layout)
        main_layout.addWidget(frame_group, 1)  # 让帧列表占主要间

        # 底部操作组
        button_group = QGroupBox("操作")
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(10, 5, 10, 5)
        
        # 左侧按钮组
        left_buttons = QHBoxLayout()
        self.add_frame_btn = QPushButton("添加新帧")
        self.delete_frame_btn = QPushButton("删除帧")
        self.send_frame_btn = QPushButton("发送")
        self.clear_results_btn = QPushButton("清除结果")
        
        # 设置按钮的固定大小
        for btn in [self.add_frame_btn, self.delete_frame_btn, 
                    self.send_frame_btn, self.clear_results_btn]:
            btn.setFixedSize(90, 28)  # 统一按钮大小
            btn.setFont(QFont("黑体", 9))
            left_buttons.addWidget(btn)
        
        # 特别设置发送按钮的式
        self.send_frame_btn.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0088E2;
            }
            QPushButton:pressed {
                background-color: #006BB3;
            }
        """)
        
        # 右侧按钮组
        right_buttons = QHBoxLayout()
        self.export_btn = QPushButton("导出帧列表")
        self.import_btn = QPushButton("导入帧列表")
        
        # 设置导入导出按钮的大小和样式
        for btn in [self.export_btn, self.import_btn]:
            btn.setFixedSize(90, 28)
            btn.setFont(QFont("黑体", 9))
            right_buttons.addWidget(btn)
        
        # 超时设置组
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("默认超时时间(ms):")
        timeout_label.setFont(QFont("黑体", 9))
        self.default_timeout = QSpinBox()
        self.default_timeout.setRange(0, 60000)
        self.default_timeout.setValue(1000)
        self.default_timeout.setFixedWidth(70)
        self.default_timeout.setFixedHeight(28)
        
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.default_timeout)
        timeout_layout.addStretch()
        
        # 将所有组件添加到布局
        button_layout.addLayout(left_buttons)
        button_layout.addStretch(1)  # 添加弹性空间
        button_layout.addLayout(timeout_layout)
        button_layout.addStretch(1)  # 添加弹性空间
        button_layout.addLayout(right_buttons)
        
        button_group.setLayout(button_layout)
        button_group.setFixedHeight(60)  # 固定操作组的高度
        
        # 设置操作组的样式
        button_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                margin-top: 5px;
                font-family: 黑体;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #E5E5E5;
                border-color: #BBBBBB;
            }
            QPushButton:pressed {
                background-color: #D5D5D5;
                border-color: #AAAAAA;
            }
            QSpinBox {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        
        main_layout.addWidget(button_group)

        # 连接单格变化信号
        self.frame_table.cellChanged.connect(self.on_cell_changed)
        # 添加编辑开始信号接
        self.frame_table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 添加属性来存储原始名称
        self.editing_frame_name = None

        # 创建主题菜单
        theme_menu = self.view_menu.addMenu("主题设置")
        
        # 添加主题配置动作
        theme_config_action = QAction("主题配置...", self)
        theme_config_action.triggered.connect(self.show_theme_dialog)
        theme_menu.addAction(theme_config_action)

        # 设置所有下拉框的大小策略
        for combo in [self.dir_combo, self.prm_combo, self.split_combo, 
                     self.sc_combo, self.func_combo, self.addr_type_combo,
                     self.ext_logic_addr_combo, self.logic_addr_flag_combo]:
            combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            combo.setFixedHeight(20)
        
        # 设置所有入框的大小策略
        for line_edit in [self.logic_addr, self.comm_addr, self.custom_data]:
            line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            line_edit.setFixedHeight(20)

        # 设置表格的默认对齐方式
        self.frame_table.setStyleSheet("""
            QTableWidget::item {
                padding: 5px;
                text-align: center;
            }
            QTableWidget QLineEdit {
                text-align: center;
            }
            QTableWidget QComboBox {
                text-align: center;
            }
        """)

        # 创建状态栏
        self.statusBar = self.statusBar()
        
        # 创建状态栏标签
        self.case_count_label = QLabel("用例数: 0")
        self.success_count_label = QLabel("成功: 0")
        self.fail_count_label = QLabel("失败: 0")
        self.timeout_count_label = QLabel("超时: 0")
        self.thread_count_label = QLabel("线程数: 0")
        self.thread_list_label = QLabel("线程列表: []")
        
        # 添加标签到状态栏
        self.statusBar.addWidget(self.case_count_label)
        self.statusBar.addWidget(self.success_count_label)
        self.statusBar.addWidget(self.fail_count_label)
        self.statusBar.addWidget(self.timeout_count_label)
        self.statusBar.addWidget(self.thread_count_label)
        self.statusBar.addWidget(self.thread_list_label)
        
        # 初始化计数器
        self.case_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.timeout_count = 0

    def on_logic_addr_flag_changed(self, text):
        """处理辑地址标志改变事件"""
        self.sa_logic_addr.setEnabled(text == '有逻辑地址(1)')
        if text == '无逻辑地址(0)':
            self.sa_logic_addr.clear()

    def on_addr_len_changed(self, text):
        """处理地址长度变化事件"""
        try:
            addr_len = int(text)
            # 更新通信地址输入框的提示
            example = "0" * (addr_len * 2)  # 生成对应长度的示例
            self.comm_addr.setPlaceholderText(f"如: {example} ({addr_len}字节)")
            
            # 获取当前通信地址值
            current_addr = self.comm_addr.text()
            if current_addr:
                # 如果当前值长度不，自动补齐
                if len(current_addr) < addr_len * 2:
                    padded_addr = current_addr.zfill(addr_len * 2)
                    self.comm_addr.setText(padded_addr)
                # 如果当前值超���，截取后面的部分
                elif len(current_addr) > addr_len * 2:
                    truncated_addr = current_addr[-addr_len * 2:]
                    self.comm_addr.setText(truncated_addr)
        except ValueError:
            # 如果输入不有效数字，使用认提示
            self.comm_addr.setPlaceholderText("请输入有效的地址长度")

    def on_oi_class_changed(self, class_name):
        """处理OI大类改变事件，更新OI小类列表"""
        self.oi_subclass_combo.clear()
        if self.oad_config and 'OI_SUBCLASS' in self.oad_config:
            if class_name in self.oad_config['OI_SUBCLASS']:
                subclass_dict = self.oad_config['OI_SUBCLASS'][class_name]
                self.oi_subclass_combo.addItems(subclass_dict.keys())
        # 更新OAD输入框
        self.update_oad_input()

    def update_oad_input(self):
        """更新OAD完整值（OI 2字节 + 属性 1字节 + 索引 1字节）"""
        try:
            # 获取OI小类值（2字节，如"4000"）
            class_name = self.oi_class_combo.currentText()
            subclass_name = self.oi_subclass_combo.currentText()
            oi_value = ""
            
            if self.oad_config and 'OI_SUBCLASS' in self.oad_config:
                if class_name in self.oad_config['OI_SUBCLASS']:
                    subclass_dict = self.oad_config['OI_SUBCLASS'][class_name]
                    if subclass_name in subclass_dict:
                        oi_value = subclass_dict[subclass_name]  # 如 "4000"
            
            # 获取属性值（1字节）
            property_name = self.property_combo.currentText()
            property_value = ""
            if self.oad_config and 'PROPERTY' in self.oad_config:
                if property_name in self.oad_config['PROPERTY']:
                    property_value = self.oad_config['PROPERTY'][property_name]
            
            # 获取索引值（1字节）
            index_name = self.index_combo.currentText()
            index_value = ""
            if self.oad_config and 'INDEX' in self.oad_config:
                if index_name in self.oad_config['INDEX']:
                    index_value = self.oad_config['INDEX'][index_name]
            
            # 组合完整的OAD值
            full_oad = oi_value + property_value + index_value
            self.oad_input.setText(full_oad)
        except Exception as e:
            print(f"OAD更新错误: {e}")

    def generate_data(self):
        """生成数据"""
        try:
            data_type = self.data_type_combo.currentText()
            
            # 根据数据类型生成示例数据
            type_code = data_type.split('(')[1].rstrip(')')
            
            # 生成示例数据
            if type_code == '0':  # NullData
                generated_data = "00"  # NULL类型
            elif type_code == '1':  # Array
                generated_data = "01 02 05 00 00 00 0A 06 00 00 00 14"  # 示例数组
            elif type_code == '2':  # Structure
                generated_data = "02 02 05 00 00 00 01 06 00 00 00 02"  # 示例结构
            elif type_code == '3':  # Bool
                generated_data = "03 01"  # True
            elif type_code == '4':  # BitString
                generated_data = "04 08 FF"  # 8位bit串
            elif type_code == '5':  # DoubleLong
                generated_data = "05 00 00 00 00"  # 0
            elif type_code == '6':  # DoubleLongUnsigned
                generated_data = "06 00 00 00 00"  # 0
            elif type_code == '9':  # OctetString
                generated_data = "09 06 01 02 03 04 05 06"  # 6字节示例
            elif type_code == '10':  # VisibleString
                generated_data = "0A 05 48 45 4C 4C 4F"  # "HELLO"
            elif type_code == '12':  # Utf8String
                generated_data = "0C 05 48 45 4C 4C 4F"  # "HELLO"
            elif type_code == '15':  # Integer
                generated_data = "0F 00"  # 0
            elif type_code == '16':  # Long
                generated_data = "10 00 00"  # 0
            elif type_code == '17':  # Unsigned
                generated_data = "11 00"  # 0
            elif type_code == '18':  # LongUnsigned
                generated_data = "12 00 00"  # 0
            elif type_code == '22':  # Enum
                generated_data = "16 00"  # 0
            elif type_code == '23':  # Float32
                generated_data = "17 00 00 00 00"  # 0.0
            elif type_code == '24':  # Float64
                generated_data = "18 00 00 00 00 00 00 00 00"  # 0.0
            elif type_code == '25':  # DateTime
                generated_data = "19 07 E7 0B 16 0E 1E 00 FF FF FF"  # 示例日期时间
            elif type_code == '26':  # Date
                generated_data = "1A 05 07 E7 0B 16 06"  # 示例日期
            elif type_code == '27':  # Time
                generated_data = "1B 04 0E 1E 00 FF"  # 示例时间
            elif type_code == '28':  # DateTimeS
                generated_data = "1C 0C 07 E7 0B 16 0E 1E 00 FF 80 00 FF FF"  # 示例
            elif type_code == '45':  # OAD
                generated_data = "2D 40 00 02 00"  # 示例OAD
            elif type_code == '80':  # OI
                generated_data = "50 40 00"  # 示例OI
            elif type_code == '81':  # OMD
                generated_data = "51 40 00 02 00"  # 示例OMD
            elif type_code == '82':  # ROAD
                generated_data = "52 40 00 02 00"  # 示例ROAD
            elif type_code == '83':  # Region
                generated_data = "53 02 40 00 02 00 40 01 02 00"  # 示例区域
            elif type_code == '84':  # ScalerUnit
                generated_data = "54 FE 1E"  # 示例比例单位
            elif type_code == '85':  # RSD
                generated_data = "55 40 00 02 00 01 02 03 04 05 06"  # 示例RSD
            elif type_code == '86':  # CSD
                generated_data = "56 40 00 02 00 01 02 03 04 05 06"  # 示例CSD
            elif type_code == '87':  # MS
                generated_data = "57 40 00 02 00 01"  # 示例MS
            elif type_code == '88':  # SID
                generated_data = "58 01 02 03 04"  # 示例SID
            elif type_code == '89':  # SIDMac
                generated_data = "59 01 02 03 04 05 06 07 08"  # 示例SIDMac
            elif type_code == '90':  # COMDCB
                generated_data = "5A 01 02 03 04 05 06 07 08 09 0A 0B 0C"  # 示例
            elif type_code == '91':  # RCSD
                generated_data = "5B 01 02 03 04 05 06 07 08 09 0A 0B 0C"  # 示例
            else:
                generated_data = "00"  # 默认NULL
            
            # 显示生成的数据
            self.data_display.setPlainText(generated_data)
            self.append_log(f"生成数据类型: {data_type}, 数据: {generated_data}", "info")
            
        except Exception as e:
            self.append_log(f"生成数据错误: {str(e)}", "error")
            QMessageBox.critical(self, "错误", f"生成数据失败：{str(e)}")

    def add_generated_data(self):
        """将生成的数据添加到自定义数据框"""
        try:
            # 获取生成的数据
            generated_data = self.data_display.toPlainText().strip().replace(' ', '')
            
            if not generated_data:
                QMessageBox.warning(self, "警告", "请先生成数据！")
                return
            
            # 获取当前自定义数据
            current_data = self.custom_data.text().strip()
            
            # 合并数据
            if current_data:
                new_data = current_data + generated_data
            else:
                new_data = generated_data
            
            # 设置到自定义数据框
            self.custom_data.setText(new_data)
            self.append_log(f"已添加数据到自定义数据框: {generated_data}", "success")
            
            # 清空生成数据显示框
            self.data_display.clear()
            
        except Exception as e:
            self.append_log(f"添加数据错误: {str(e)}", "error")
            QMessageBox.critical(self, "错误", f"添加数据失败：{str(e)}")

    def on_service_type_changed(self, text):
        """处理服务型改变事件"""
        # 根据服务类型显示不同的据类型选项
        if text == '读取请求':
            self.service_data_type_combo.clear()
            self.service_data_type_combo.addItems([
                '请求一个对象属性',
                '请求若干个对象属性',
                '请求一个记录型对象属性',
                '请求若干个记录型对象属性',
                '请求分帧传输的下一',
                '请求一个对象属性的MD5值'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
        elif text == '设置请求':
            self.service_data_type_combo.clear()
            self.service_data_type_combo.addItems([
                '请求设置一个对象性',
                '请求设若干个对象属性',
                '请求设置后若干个对象属性'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
        else:
            self.service_data_type_label.setVisible(False)
            self.service_data_type_combo.setVisible(False)

    def create_default_oad_config(self):
        """创建默认的OAD配置文件"""
        config = configparser.ConfigParser()
        config['OAD'] = {
            '日期时间': '40000200',
            '通信地址': '00100200',
            '逻辑地址': '00010200',
            '信速率': '40020200',
            '主通信参数': '40030200',
            '设备地址': '00300200',
            '件版本': '00400200',
            '硬件版本': '00500200',
            '电压数据': '20000200',
            '电流数据': '20010200',
            '有功功率': '20020200',
            '无功功率': '20030200',
            '功率因数': '20040200',
            '正向有功电': '20100200',
            '反向有功电能': '20110200',
            '需量数据': '20200200'
        }
        
        with open('config/oad_config.ini', 'w', encoding='utf-8') as f:
            config.write(f)

    def load_oad_config(self):
        """加载OAD配置"""
        try:
            if os.path.exists('config/oad_config.json'):
                with open('config/oad_config.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载OAD配置失败: {e}")
        return None

    def export_frames(self):
        """导出帧列表到CSV文件"""
        if self.frame_table.rowCount() == 0:
            self.append_log("没有可导出的帧数据！", "warning")
            QMessageBox.warning(self, "警告", "没有可导出的帧数据！")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出帧列表",
            "",
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if file_name:
            try:
                self.append_log(f"开始导出帧列表到: {file_name}", "info")
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    # 写入表头
                    headers = ['名称', '帧内容', '状态', '启用匹配', '匹配规则', 
                              '匹配模式', '测试结果', '超时(ms)']
                    writer.writerow(headers)
                    
                    # 写入数据
                    for row in range(self.frame_table.rowCount()):
                        frame_name = self.frame_table.item(row, 1).text()
                        self.append_log(f"导出帧: {frame_name}", "info")
                        # ... (导出数据的代码保持不变)
                
                self.append_log(f"成功导出 {self.frame_table.rowCount()} 个帧", "success")
                QMessageBox.information(self, "成功", "帧列表已成功导出")
            except Exception as e:
                error_msg = f"导出失败：{str(e)}"
                self.append_log(error_msg, "error")
                QMessageBox.critical(self, "错误", error_msg)

    def create_button_handler(self, frame_name, row):
        """创建按钮处理函数"""
        def handler():
            try:
                # 获取按钮
                button = self.frame_table.cellWidget(row, 3)
                if isinstance(button, QPushButton):
                    # 禁用按钮
                    button.setEnabled(False)
                    
                    # 动态取当前行的帧
                    current_frame_name = self.frame_table.item(row, 1).text()
                    self.frame_send_requested.emit((current_frame_name, row))
                    
                    # 设置定时器在超时后重新启用按钮
                    timeout_spinbox = self.frame_table.cellWidget(row, 9)
                    timeout = timeout_spinbox.value() if timeout_spinbox else 1000
                    
                    QTimer.singleShot(timeout + 100, lambda: button.setEnabled(True))
                    
            except Exception as e:
                self.append_log(f"发送帧失败: {str(e)}", "error")
                # 确保按钮被重新启用
                button = self.frame_table.cellWidget(row, 3)
                if isinstance(button, QPushButton):
                    button.setEnabled(True)
        return handler

    def import_frames(self):
        """从CSV文件导入帧列表"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "导入帧列表",
            "",
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if file_name:
            try:
                with open(file_name, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    next(reader)  # 跳过表
                    
                    # 清空现格
                    self.frame_table.setRowCount(0)
                    
                    # 添加导的数据
                    for row_data in reader:
                        row = self.frame_table.rowCount()
                        self.frame_table.insertRow(row)
                        
                        # 设序号
                        self.frame_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                        # 设置名称和内容
                        self.frame_table.setItem(row, 1, QTableWidgetItem(row_data[0]))  # 名���
                        self.frame_table.setItem(row, 2, QTableWidgetItem(row_data[1]))  # 帧内容
                        
                        # 添加发送按钮
                        send_btn = QPushButton("单帧发送")
                        send_btn.setFont(QFont("黑体", weight=QFont.Bold))
                        send_btn.setFixedWidth(130)
                        send_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #4CAF50;
                                color: white;
                                border-radius: 4px;
                                padding: 5px;
                                margin: 2px;
                            }
                            QPushButton:hover {
                                background-color: #45a049;
                            }
                        """)
                        frame_name = row_data[0]  # 存帧名称局部变量
                        
                        # 使用专门的处理函数
                        send_btn.clicked.connect(self.create_button_handler(frame_name, row))
                        self.frame_table.setCellWidget(row, 3, send_btn)
                        
                        # 设置状态
                        self.frame_table.setItem(row, 4, QTableWidgetItem(row_data[2]))  # 状态
                        
                        # 设置启用匹配复选������
                        match_checkbox = QCheckBox()
                        match_checkbox.setChecked(row_data[3] == '1')
                        self.frame_table.setCellWidget(row, 5, match_checkbox)
                        
                        # 设置匹配规则
                        self.frame_table.setItem(row, 6, QTableWidgetItem(row_data[4]))
                        
                        # 设置匹配模式
                        mode_combo = QComboBox()
                        mode_combo.addItems(["HEX", "ASCII"])
                        mode_combo.setCurrentText(row_data[5])
                        self.frame_table.setCellWidget(row, 7, mode_combo)
                        
                        # 设置测试结果
                        self.frame_table.setItem(row, 8, QTableWidgetItem(row_data[6]))
                        
                        # 设置超时时间
                        timeout_spinbox = self.create_timeout_spinbox(row)
                        timeout_spinbox.setValue(int(row_data[7]) if len(row_data) > 7 else 1000)
                        self.frame_table.setCellWidget(row, 9, timeout_spinbox)
                        
                        # 将帧数据保存到协议象中
                        frame_bytes = bytes.fromhex(row_data[1])
                        self.protocol.save_frame(row_data[0], frame_bytes)
                
                # 调整列
                self.frame_table.resizeColumnsToContents()
                # 特别处理"操作"列的宽度
                self.frame_table.setColumnWidth(3, 150)  # 设置固定宽度为150��素
                
                QMessageBox.information(self, "成功", "帧列表已成功导入！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败：{str(e)}")

    def create_dockable_log_window(self):
        """创建日志窗口"""
        dock = QDockWidget("日志输出", self)
        dock.setFeatures(QDockWidget.DockWidgetClosable | 
                        QDockWidget.DockWidgetFloatable |
                        QDockWidget.DockWidgetVerticalTitleBar)
        
        # 创建日志文本框
        self.receive_display = QTextEdit()
        self.receive_display.setReadOnly(True)
        self.receive_display.setMinimumHeight(100)  # 设置最小高度
        
        # 创建一个包含日志窗口的容器
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.receive_display)
        
        dock.setWidget(container)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def minimize_log_window(self):
        """最小化日志窗口"""
        if dock.isFloating():
            dock.showMinimized()
        else:
            dock.hide()

    def toggle_maximize_log_window(self):
        """切换日志窗口最大化状态"""
        if not dock.isFloating():
            # 如果停靠状态先设为浮动
            dock.setFloating(True)
        
        if not self.is_log_maximized:
            # 最大化
            self.normal_log_size = dock.size()  # ��存当前大小
            dock.setGeometry(self.screen().availableGeometry())
            self.max_btn.setText("❐")
            self.is_log_maximized = True
        else:
            # 还原
            dock.resize(self.normal_log_size)
            self.max_btn.setText("□")
            self.is_log_maximized = False

    def create_protocol_config_window(self):
        """创建协议配置窗口（合并为TabWidget）"""
        dock = QDockWidget("配置面板", self)
        dock.setFeatures(
            QDockWidget.DockWidgetClosable | 
            QDockWidget.DockWidgetFloatable | 
            QDockWidget.DockWidgetMovable
        )
        
        # 设置初始宽度和最小宽度
        dock.setMinimumWidth(400)
        dock.resize(600, 800)
        
        # 创建TabWidget作为主容器
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                padding: 8px 16px;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                background-color: white;
                font-weight: bold;
            }
        """)
        
        # ========== 第一个标签页：协议配置 ==========
        protocol_tab = QWidget()
        content_layout = QVBoxLayout(protocol_tab)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # 控制域配置组
        control_group = QGroupBox("控制域(CBIN)")
        control_layout = QGridLayout()
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加控制域控件
        control_layout.addWidget(QLabel("D7传输方向:"), 0, 0)
        control_layout.addWidget(self.dir_combo, 0, 1)
        control_layout.addWidget(QLabel("D6启动标志:"), 0, 2)
        control_layout.addWidget(self.prm_combo, 0, 3)
        
        control_layout.addWidget(QLabel("D5分帧标志:"), 1, 0)
        control_layout.addWidget(self.split_combo, 1, 1)
        control_layout.addWidget(QLabel("D3数据域标志:"), 1, 2)
        control_layout.addWidget(self.sc_combo, 1, 3)
        
        control_layout.addWidget(QLabel("D2-D0功能码:"), 2, 0)
        control_layout.addWidget(self.func_combo, 2, 1, 1, 3)
        
        control_group.setLayout(control_layout)
        content_layout.addWidget(control_group)
        
        # SA标志配置组
        sa_flag_group = QGroupBox("服务器地址SA标志字节(BCD)")
        sa_flag_layout = QGridLayout()
        sa_flag_layout.setSpacing(10)
        sa_flag_layout.setContentsMargins(15, 15, 15, 15)
        
        sa_flag_layout.addWidget(QLabel("D7-D6地址类型:"), 0, 0)
        sa_flag_layout.addWidget(self.addr_type_combo, 0, 1)
        sa_flag_layout.addWidget(QLabel("D5扩展逻辑地址:"), 0, 2)
        sa_flag_layout.addWidget(self.ext_logic_addr_combo, 0, 3)
        
        sa_flag_layout.addWidget(QLabel("D4逻辑地址标志:"), 1, 0)
        sa_flag_layout.addWidget(self.logic_addr_flag_combo, 1, 1)
        sa_flag_layout.addWidget(QLabel("D3-D0地址长度:"), 1, 2)
        sa_flag_layout.addWidget(self.addr_len_input, 1, 3)
        
        sa_flag_group.setLayout(sa_flag_layout)
        content_layout.addWidget(sa_flag_group)
        
        # 服务器地址配置组
        sa_group = QGroupBox("服务器地址(SA)")
        sa_layout = QGridLayout()
        sa_layout.setSpacing(10)
        sa_layout.setContentsMargins(15, 15, 15, 15)
        
        sa_layout.addWidget(QLabel("SA逻辑地址:"), 0, 0)
        sa_layout.addWidget(self.sa_logic_addr, 0, 1)
        
        sa_layout.addWidget(QLabel("客户机地址(CA):"), 1, 0)
        sa_layout.addWidget(self.logic_addr, 1, 1)
        
        sa_layout.addWidget(QLabel("通信地址(SA):"), 2, 0)
        sa_layout.addWidget(self.comm_addr, 2, 1)
        
        sa_group.setLayout(sa_layout)
        content_layout.addWidget(sa_group)
        
        # APDU配置组
        apdu_group = QGroupBox("APDU")
        apdu_layout = QGridLayout()
        apdu_layout.setSpacing(10)
        apdu_layout.setContentsMargins(15, 15, 15, 15)
        
        # 服务类型和数据类型
        apdu_layout.addWidget(QLabel("服务类型:"), 0, 0)
        apdu_layout.addWidget(self.service_type_combo, 0, 1)
        apdu_layout.addWidget(self.service_data_type_label, 0, 2)
        apdu_layout.addWidget(self.service_data_type_combo, 0, 3)
        
        # 服务优先级和序号
        apdu_layout.addWidget(QLabel("服务优先级:"), 1, 0)
        apdu_layout.addWidget(self.service_priority_combo, 1, 1)
        apdu_layout.addWidget(QLabel("服务序号:"), 1, 2)
        apdu_layout.addWidget(self.service_number_spin, 1, 3)
        
        # OAD选择和输入（GridLayout布局）
        apdu_layout.addWidget(QLabel("OAD:"), 2, 0, Qt.AlignTop)
        
        # 创建OAD配置组
        oad_group = QGroupBox()
        oad_grid = QGridLayout()
        oad_grid.setSpacing(10)
        oad_grid.setContentsMargins(10, 10, 10, 10)
        
        # 第一行：对象大类和OI
        oad_grid.addWidget(QLabel("对象大类:"), 0, 0)
        self.oi_class_combo = QComboBox()
        self.oi_class_combo.setMinimumWidth(200)
        if self.oad_config and 'OI_CLASS' in self.oad_config:
            self.oi_class_combo.addItems(self.oad_config['OI_CLASS'].keys())
        self.oi_class_combo.currentTextChanged.connect(self.on_oi_class_changed)
        oad_grid.addWidget(self.oi_class_combo, 0, 1)
        
        oad_grid.addWidget(QLabel("OI(对象标识):"), 0, 2)
        self.oi_subclass_combo = QComboBox()
        self.oi_subclass_combo.setMinimumWidth(250)
        self.oi_subclass_combo.currentTextChanged.connect(self.update_oad_input)
        oad_grid.addWidget(self.oi_subclass_combo, 0, 3)
        
        # 第二行：属性和索引
        oad_grid.addWidget(QLabel("属性ID:"), 1, 0)
        self.property_combo = QComboBox()
        if self.oad_config and 'PROPERTY' in self.oad_config:
            self.property_combo.addItems(self.oad_config['PROPERTY'].keys())
        self.property_combo.currentTextChanged.connect(self.update_oad_input)
        oad_grid.addWidget(self.property_combo, 1, 1)
        
        oad_grid.addWidget(QLabel("索引:"), 1, 2)
        self.index_combo = QComboBox()
        if self.oad_config and 'INDEX' in self.oad_config:
            self.index_combo.addItems(self.oad_config['INDEX'].keys())
        self.index_combo.currentTextChanged.connect(self.update_oad_input)
        oad_grid.addWidget(self.index_combo, 1, 3)
        
        # 第三行：OAD完整值（突出显示）
        oad_result_layout = QHBoxLayout()
        oad_result_layout.addWidget(QLabel("OAD完整值:"))
        self.oad_input.setStyleSheet("""
            QLineEdit {
                background-color: #e3f2fd;
                border: 2px solid #2196f3;
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)
        self.oad_input.setReadOnly(True)  # 设置为只读
        oad_result_layout.addWidget(self.oad_input)
        oad_grid.addLayout(oad_result_layout, 2, 0, 1, 4)
        
        oad_group.setLayout(oad_grid)
        apdu_layout.addWidget(oad_group, 2, 1, 1, 3)
        
        # 初始化OI小类列表
        if self.oi_class_combo.count() > 0:
            self.on_oi_class_changed(self.oi_class_combo.currentText())
        
        # 自定义数据
        apdu_layout.addWidget(QLabel("自定义数据:"), 4, 0)
        apdu_layout.addWidget(self.custom_data, 4, 1, 1, 3)
        
        apdu_group.setLayout(apdu_layout)
        content_layout.addWidget(apdu_group)
        
        # 添加弹性空间
        content_layout.addStretch()
        
        # 添加到TabWidget
        tab_widget.addTab(protocol_tab, "📝 协议配置")
        
        # ========== 第二个标签页：数据构造器 ==========
        data_builder_tab = QWidget()
        data_builder_layout = QVBoxLayout(data_builder_tab)
        data_builder_layout.setSpacing(10)
        data_builder_layout.setContentsMargins(10, 10, 10, 10)
        
        # 数据类型选择组
        data_type_group = QGroupBox("数据类型")
        data_type_layout = QVBoxLayout()
        data_type_layout.setSpacing(10)
        data_type_layout.setContentsMargins(15, 15, 15, 15)
        
        # 数据类型下拉框
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems([
            'NullData(0)',
            'Array(1)',
            'Structure(2)',
            'Bool(3)',
            'BitString(4)',
            'DoubleLong(5)',
            'DoubleLongUnsigned(6)',
            'OctetString(9)',
            'VisibleString(10)',
            'Utf8String(12)',
            'Integer(15)',
            'Long(16)',
            'Unsigned(17)',
            'LongUnsigned(18)',
            'Enum(22)',
            'Float32(23)',
            'Float64(24)',
            'DateTime(25)',
            'Date(26)',
            'Time(27)',
            'DateTimeS(28)',
            'OAD(45)',
            'OI(80)',
            'OMD(81)',
            'ROAD(82)',
            'Region(83)',
            'ScalerUnit(84)',
            'RSD(85)',
            'CSD(86)',
            'MS(87)',
            'SID(88)',
            'SIDMac(89)',
            'COMDCB(90)',
            'RCSD(91)'
        ])
        self.data_type_combo.setMinimumHeight(30)
        data_type_layout.addWidget(self.data_type_combo)
        
        data_type_group.setLayout(data_type_layout)
        data_builder_layout.addWidget(data_type_group)
        
        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 生成数据按钮
        self.generate_data_btn = QPushButton("生成数据")
        self.generate_data_btn.setMinimumHeight(40)
        self.generate_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
        self.generate_data_btn.clicked.connect(self.generate_data)
        button_layout.addWidget(self.generate_data_btn)
        
        # 添加数据按钮
        self.add_data_btn = QPushButton("添加数据")
        self.add_data_btn.setMinimumHeight(40)
        self.add_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
        """)
        self.add_data_btn.clicked.connect(self.add_generated_data)
        button_layout.addWidget(self.add_data_btn)
        
        data_builder_layout.addLayout(button_layout)
        
        # 数据显示区域
        data_display_group = QGroupBox("生成的数据")
        data_display_layout = QVBoxLayout()
        data_display_layout.setContentsMargins(10, 10, 10, 10)
        
        self.data_display = QTextEdit()
        self.data_display.setPlaceholderText("点击'生成数据'按钮后，生成的数据将显示在此处...")
        self.data_display.setMinimumHeight(300)
        self.data_display.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 2px solid #cccccc;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        data_display_layout.addWidget(self.data_display)
        
        data_display_group.setLayout(data_display_layout)
        data_builder_layout.addWidget(data_display_group)
        
        # 添加弹性空间
        data_builder_layout.addStretch()
        
        # 添加到TabWidget
        tab_widget.addTab(data_builder_tab, "🔧 数据构造器")
        
        # 使用滚动区域包裹TabWidget
        scroll_area = QScrollArea()
        scroll_area.setWidget(tab_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置内容窗口
        dock.setWidget(scroll_area)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        
        # 添加到窗口菜单
        toggle_action = dock.toggleViewAction()
        toggle_action.setText("配置面板")
        self.windows_menu.addAction(toggle_action)

    def minimize_config_window(self):
        """最小化配置窗口"""
        if dock.isFloating():
            dock.showMinimized()
        else:
            dock.hide()

    def toggle_maximize_config_window(self):
        """切换配置窗口最大状态"""
        if not dock.isFloating():
            dock.setFloating(True)
        
        if not self.is_config_maximized:
            self.normal_config_size = dock.size()
            dock.setGeometry(self.screen().availableGeometry())
            self.config_max_btn.setText("❐")
            self.is_config_maximized = True
        else:
            dock.resize(self.normal_config_size)
            self.config_max_btn.setText("□")
            self.is_config_maximized = False

    def create_receive_display(self):
        """这个方法不需要，因为已经在create_dockable_log_window中创建了receive_display"""
        pass

    def add_new_frame(self):
        """添加新帧"""
        try:
            self.append_log("开始添加新帧...", "info")
            
            # 获取当前行数
            row = self.frame_table.rowCount()
            self.append_log(f"当前表格行数: {row}", "info")
            
            self.frame_table.insertRow(row)
            
            # 设置序号（居中对齐）
            item = QTableWidgetItem(str(row + 1))
            item.setTextAlignment(Qt.AlignCenter)
            self.frame_table.setItem(row, 0, item)
            
            # 设置帧名称（居中对齐）
            item = QTableWidgetItem(f"Frame_{row + 1}")
            item.setTextAlignment(Qt.AlignCenter)
            self.frame_table.setItem(row, 1, item)
            
            # 创建发送按钮
            send_btn = QPushButton("单帧发送")
            send_btn.setFont(QFont("黑体", weight=QFont.Bold))
            send_btn.setFixedWidth(130)
            send_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 4px;
                    padding: 5px;
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            
            # 使用专门的处理函数
            send_btn.clicked.connect(self.create_button_handler(f"Frame_{row + 1}", row))
            self.frame_table.setCellWidget(row, 3, send_btn)
            
            # 设置状态列（居中对齐）
            item = QTableWidgetItem("未发送")
            item.setTextAlignment(Qt.AlignCenter)
            self.frame_table.setItem(row, 4, item)
            
            # 创建启用匹配复选框
            match_check = QCheckBox()
            match_check.setChecked(False)
            self.frame_table.setCellWidget(row, 5, match_check)
            
            # 创建匹配规则输入框并居中对齐
            match_rule = QLineEdit()
            match_rule.setPlaceholderText("输入匹配规则")
            match_rule.setAlignment(Qt.AlignCenter)
            self.frame_table.setCellWidget(row, 6, match_rule)
            
            # 创建匹配模式下拉框并居中对齐
            match_mode = QComboBox()
            match_mode.addItems(['HEX', 'ASCII'])
            match_mode.setCurrentText("HEX")
            # 直接使用 ComboBox，不再包装在 QWidget 中
            self.frame_table.setCellWidget(row, 7, match_mode)
            
            # 设置测试结果列
            self.frame_table.setItem(row, 8, QTableWidgetItem(""))
            
            # 创建超时设置
            timeout_spin = QSpinBox()
            timeout_spin.setRange(0, 60000)  # 0-60000ms
            timeout_spin.setValue(1000)  # 默认1000ms
            timeout_spin.setSuffix(" ms")
            self.frame_table.setCellWidget(row, 9, timeout_spin)
            
            # 创建帧数据
            frame_data = self.create_frame_data()
            if frame_data:
                # 保存帧数据到协议对象
                if self.protocol:
                    self.protocol.save_frame(f"Frame_{row + 1}", frame_data)
                    self.append_log(f"帧数据已保存: {frame_data.hex()}", "info")
                
                # 显示帧内容
                self.frame_table.setItem(row, 2, QTableWidgetItem(frame_data.hex()))
                self.append_log(f"帧 Frame_{row + 1} 添加成功", "success")
            else:
                self.append_log("创建帧数据失败", "error")
                
        except Exception as e:
            self.append_log(f"添加新帧失败: {str(e)}", "error")
            import traceback
            self.append_log(f"错误详情:\n{traceback.format_exc()}", "error")

    def clear_test_results(self):
        """清除所有测试结果"""
        for row in range(self.frame_table.rowCount()):
            # 只清除测试结果列
            result_item = QTableWidgetItem("")
            self.frame_table.setItem(row, 8, result_item)
            # 重置测试结果列的背景色
            result_item.setBackground(QColor("white"))

    def on_cell_changed(self, row, column):
        """处理表格单元格化"""
        if column == 1 and self.editing_frame_name is not None:  # 名称列
            new_name = self.frame_table.item(row, 1).text()
            if self.editing_frame_name != new_name and self.protocol:
                # 获取帧数据
                frame_data = self.protocol.get_frame(self.editing_frame_name)
                if frame_data:
                    # 使用��名称保存帧数据
                    self.protocol.save_frame(new_name, frame_data)
                    # 删除旧名称的帧数据
                    self.protocol.frames.pop(self.editing_frame_name, None)
                    
                    # 在志区域示称更新信息
                    self.append_log(f"""
                    <div style='background-color: #e8f5e9; padding: 5px; margin: 2px;'>
                        <span style='color: #2e7d32;'>帧名称已更新: {self.editing_frame_name} -> {new_name}</span>
                    </div>
                    """)
                else:
                    # 如果不到始帧数据，显示错误信息
                    self.append_log(f"""
                    <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                        <span style='color: #721c24;'>错误: 找不到原始帧 "{self.editing_frame_name}" 的数据</span>
                    </div>
                    """)
                
            # 重置编辑状态
            self.editing_frame_name = None

    def on_item_double_clicked(self, item):
        """当单元格被双击时记录原始名称"""
        if item.column() == 1:  # 名称列
            self.editing_frame_name = item.text()

    def create_timeout_spinbox(self, row):
        """创建超时设置控件"""
        timeout_spinbox = QSpinBox()
        timeout_spinbox.setRange(0, 60000)
        timeout_spinbox.setValue(1000)  # 默认值
        
        # 连接变化信号
        timeout_spinbox.valueChanged.connect(lambda value: self.on_timeout_changed(row, value))
        
        return timeout_spinbox

    def on_timeout_changed(self, row, value):
        """处理超时值变化"""
        # 更新当前行的超时设置
        if hasattr(self, 'default_timeout'):
            self.default_timeout.setValue(value)
        
        # 在日志区域显示超时更新信息
        frame_name = self.frame_table.item(row, 1).text()
        self.append_log(f"""
        <div style='background-color: #e8f5e9; padding: 5px; margin: 2px;'>
            <span style='color: #2e7d32;'>✓ 帧 {row + 1} ({frame_name}) 超时时间已更新: {value}ms</span>
        </div>
        """)

    def change_style(self, style_name):
        """更改应用程序的主题风格"""
        QApplication.setStyle(style_name)
        # ��选：��存用户的样式选择到配置文件
        self.save_style_preference(style_name)

    def save_style_preference(self, style_name):
        """保存样式选择到置文件"""
        config = configparser.ConfigParser()
        config['Style'] = {'theme': style_name}
        
        with open('config/style_config.ini', 'w') as f:
            config.write(f)

    def load_style_preference(self):
        """从配置文加载样式选择"""
        try:
            config = configparser.ConfigParser()
            config.read('config/style_config.ini')
            if 'Style' in config and 'theme' in config['Style']:
                style_name = config['Style']['theme']
                QApplication.setStyle(style_name)
                # 新菜单中的选中状态
                for action in self.view_menu.findChild(QMenu, "主题风格").actions():
                    action.setChecked(action.text() == style_name)
        except Exception as e:
            print(f"加载样式配置失败: {e}")

    def show_log_context_menu(self, pos):
        """显示日志窗口的右键菜单"""
        context_menu = QMenu(self)
        
        # 添加清除日志选项
        clear_action = QAction("清除日志", self)
        clear_action.triggered.connect(self.clear_log_display)
        context_menu.addAction(clear_action)
        
        # 添加日志设置选项
        settings_action = QAction("日志设置", self)
        settings_action.triggered.connect(self.show_log_settings)
        context_menu.addAction(settings_action)
        
        # 显示菜单
        context_menu.exec_(self.receive_display.mapToGlobal(pos))

    def show_log_settings(self):
        """显示日志设置话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("日志设置")
        layout = QVBoxLayout(dialog)
        
        # 日志文件名输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("日志文件名:"))
        name_input = QLineEdit()
        name_input.setText(self.log_file_name)
        name_input.setPlaceholderText("输入日志文件名（可选）")
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # 启用日志文件项
        enable_logging = QCheckBox("启用日志文件")
        enable_logging.setChecked(self.log_file is not None)
        layout.addWidget(enable_logging)
        
        # 确认取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            if enable_logging.isChecked():
                self.start_logging(name_input.text())
            else:
                self.stop_logging()

    def start_logging(self, base_name=""):
        """开始日志记录"""
        try:
            # 生成日志文件名
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            if base_name:
                file_name = f"{base_name}_{timestamp}.log"
            else:
                file_name = f"log_{timestamp}.log"
            
            # 确保日志目录存在
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 打开日志文件
            self.log_file_name = base_name
            self.log_file = open(os.path.join(log_dir, file_name), 'w', encoding='utf-8')
            
            self.append_log(f"""
            <div style='background-color: #e8f5e9; padding: 5px; margin: 2px;'>
                <span style='color: #2e7d32;'>✓ 日志文件已动: {file_name}</span>
            </div>
            """)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建日志文件失败：{str(e)}")

    def stop_logging(self):
        """停止日志记录"""
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_file_name = ""
            
            self.append_log("""
            <div style='background-color: #fff3cd; padding: 5px; margin: 2px;'>
                <span style='color: #856404;'>⚠ 日志文件已关闭</span>
            </div>
            """)

    def clear_log_display(self):
        """清除显示区域的日志"""
        self.receive_display.clear()
        self.log_buffer_size = 0

    def append_log(self, text, level="info"):
        """添加日志内容并同时写入文件"""
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
        
        # 根据日志级别设置样式
        style_map = {
            "info": ("background-color: #f8f9fa; color: #1a1e21;", "ℹ"),
            "success": ("background-color: #d4edda; color: #155724;", "✓"),
            "warning": ("background-color: #fff3cd; color: #856404;", "⚠"),
            "error": ("background-color: #f8d7da; color: #721c24;", "✗")
        }
        style, icon = style_map.get(level, style_map["info"])
        
        log_html = f"""
        <div style='{style} padding: 5px; margin: 2px; border-radius: 4px;'>
            <span style='color: #666666;'>[{timestamp}]</span>
            <span>{icon} {text}</span>
        </div>
        """
        
        # 计算新内容大小
        new_size = len(log_html.encode('utf-8'))
        
        # 检查是否超��缓存限制
        if self.log_buffer_size + new_size > self.MAX_BUFFER_SIZE:
            self.receive_display.clear()
            self.log_buffer_size = 0
            self.append_log("日志已达到500MB限制，已清除显示区域", "warning")
        
        # 添加新内容到显示区域
        self.receive_display.append(log_html)
        self.log_buffer_size += new_size
        
        # 写入日志文件
        if self.log_file:
            try:
                # 移除HTML标签
                plain_text = re.sub(r'<[^>]+>', '', text)
                # 写入带时间戳的日志
                log_line = f"[{timestamp}] [{level.upper()}] {plain_text}\n"
                self.log_file.write(log_line)
                self.log_file.flush()
            except Exception as e:
                print(f"写入日志文件失败：{e}")
        
        # 添加到loguru日志
        if level == "info":
            self.logger.info(text)
        elif level == "success":
            self.logger.info(f"[SUCCESS] {text}")
        elif level == "warning":
            self.logger.warning(text)
        elif level == "error":
            self.logger.error(text)

    def save_serial_config(self):
        """保存串口配置到JSON文件"""
        config = {
            'port': self.port_combo.currentText(),
            'baudrate': self.baud_combo.currentText(),
            'parity': self.parity_combo.currentText(),
            'bytesize': self.bytesize_combo.currentText(),
            'stopbits': self.stopbits_combo.currentText()
        }
        
        try:
            # 确保配置目录存在
            if not os.path.exists('config'):
                os.makedirs('config')
            
            with open('config/serial_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            print("串口配置已保存")  # 添加调试输出
        except Exception as e:
            print(f"保存串口配置失败: {e}")

    def load_serial_config(self):
        """从JSON文加载串口配置"""
        config_path = 'config/serial_config.json'
        try:
            if not os.path.exists(config_path):
                # 创建默认配置
                default_config = {
                    'port': '',
                    'baudrate': '9600',
                    'parity': '无校验(N)',
                    'bytesize': '8',
                    'stopbits': '1'
                }
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                config = default_config
            else:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 用配置到UI
            # 设置波特率
            index = self.baud_combo.findText(config.get('baudrate', '9600'))
            if index >= 0:
                self.baud_combo.setCurrentIndex(index)
            
            # 设置校验位
            index = self.parity_combo.findText(config.get('parity', '无校验(N)'))
            if index >= 0:
                self.parity_combo.setCurrentIndex(index)
            
            # 设置数据位
            index = self.bytesize_combo.findText(config.get('bytesize', '8'))
            if index >= 0:
                self.bytesize_combo.setCurrentIndex(index)
            
            # 设置停止位
            index = self.stopbits_combo.findText(config.get('stopbits', '1'))
            if index >= 0:
                self.stopbits_combo.setCurrentIndex(index)
            
            # 设置串口如果存在）
            saved_port = config.get('port', '')
            if saved_port:
                index = self.port_combo.findText(saved_port)
                if index >= 0:
                    self.port_combo.setCurrentIndex(index)
            
            return config
        
        except Exception as e:
            print(f"加载串口配置失败: {e}")
            return None

    def save_theme_config(self):
        """保存界面主题置"""
        config = {
            'background_color': '#EEF5FF',
            'groupbox_background': '#FFFFFF',
            'groupbox_border': '#86B6F6',
            'label_color': '#176B87',
            'button_background': '#86B6F6',
            'button_hover': '#19A7CE',
            'table_border': '#86B6F6',
            'table_gridline': '#B4D4FF'
        }
        
        try:
            with open('config/theme_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存主题配置失败: {e}")

    def load_theme_config(self):
        """加载界面主题配置"""
        config_path = 'config/theme_config.json'
        if not os.path.exists(config_path):
            # 创建默认配置
            default_config = {
                'background_color': '#EEF5FF',
                'groupbox_background': '#FFFFFF',
                'groupbox_border': '#86B6F6',
                'label_color': '#176B87',
                'button_background': '#86B6F6',
                'button_hover': '#19A7CE',
                'table_border': '#86B6F6',
                'table_gridline': '#B4D4FF'
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
            return default_config
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载主题配置失败: {e}")
            return None

    def eventFilter(self, obj, event):
        """处理事件过滤"""
        if obj == self.frame_table.viewport():
            if event.type() == QEvent.Wheel and event.modifiers() == Qt.ControlModifier:
                # Ctrl + 滚轮实现缩放
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_table(1.1)  # 放大
                else:
                    self.zoom_table(0.9)  # 缩小
                return True
        return super().eventFilter(obj, event)

    def zoom_table(self, factor):
        """缩放表格"""
        try:
            # 限制缩放范围
            new_factor = self.table_zoom_factor * factor
            if 0.5 <= new_factor <= 2.0:
                self.table_zoom_factor = new_factor
                
                # 调整字体大小
                font = self.frame_table.font()
                font.setPointSizeF(9 * self.table_zoom_factor)  # 基础字号为9
                self.frame_table.setFont(font)
                
                # 调整行高
                for row in range(self.frame_table.rowCount()):
                    self.frame_table.setRowHeight(row, int(30 * self.table_zoom_factor))
                
                # 调整列宽
                self.frame_table.resizeColumnsToContents()
                
                # 调整表头字体
                header_font = self.frame_table.horizontalHeader().font()
                header_font.setPointSizeF(9 * self.table_zoom_factor)
                self.frame_table.horizontalHeader().setFont(header_font)
        except Exception as e:
            self.append_log(f"缩放表格失败: {str(e)}", "error")

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        try:
            # 保存串口配置
            self.save_serial_config()
            # 保存主题配置
            self.save_theme_config()
            # 如果有日志文件打开，关闭它
            if hasattr(self, 'log_file') and self.log_file:
                self.log_file.close()
            event.accept()
        except Exception as e:
            print(f"存配置失败: {e}")
            event.accept()

    def on_connect_clicked(self):
        """处理连接按钮点击事件"""
        if self.connect_btn.text() == "连接":
            # 获取当前串口配置
            parity_map = {
                '无校验(N)': 'N',
                '奇校验(O)': 'O',
                '偶校验(E)': 'E',
                '标记(M)': 'M',
                '空�����(S)': 'S'
            }
            
            config = {
                'port': self.port_combo.currentText(),
                'baudrate': int(self.baud_combo.currentText()),
                'parity': parity_map.get(self.parity_combo.currentText(), 'N'),
                'bytesize': int(self.bytesize_combo.currentText()),
                'stopbits': float(self.stopbits_combo.currentText())
            }
            
            # 检查串口是否选择
            if not config['port']:
                QMessageBox.warning(self, "错误", "请选择串口！")
                return
                
            # 发射连接请求信号
            self.serial_connect_requested.emit(config)
        else:
            # 发射断开请求信号
            self.serial_connect_requested.emit({})

    def set_serial_connected(self, connected):
        """设置串口连接状态"""
        if connected:
            self.connect_btn.setText("断开")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            # 禁用串口设置件
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.parity_combo.setEnabled(False)
            self.bytesize_combo.setEnabled(False)
            self.stopbits_combo.setEnabled(False)
            # 显示连接功消息
            self.append_log("""
            <div style='background-color: #d4edda; padding: 5px; margin: 2px;'>
                <span style='color: #155724;'>✓ 串口连接成功</span>
            </div>
            """)
        else:
            self.connect_btn.setText("连接")
            self.connect_btn.setStyleSheet("")  # 恢复认样式
            # 启用串口置控件
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.parity_combo.setEnabled(True)
            self.bytesize_combo.setEnabled(True)
            self.stopbits_combo.setEnabled(True)
            # 显示断开连接消息
            self.append_log("""
            <div style='background-color: #fff3cd; padding: 5px; margin: 2px;'>
                <span style='color: #856404;'>⚠ 串口已断开连接</span>
            </div>
            """)

    def show_theme_dialog(self):
        """显示主题配置对话框"""
        from ui.theme_dialog import ThemeDialog
        dialog = ThemeDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            theme = dialog.get_current_theme()
            self.apply_theme(theme)
            self.save_current_theme(theme)

    def apply_theme(self, theme):
        """应用Fusion风格主题"""
        style = """
            /* 全局��式 */
            * {
                font-family: "黑体";
                font-size: 9pt;
            }

            /* 分组框 */
            QGroupBox {
                margin-top: 12px;
                padding: 8px;  /* 减小内边距 */
                border: 1px solid #C0C0C0;
                border-radius: 2px;
            }

            /* 下拉框 */
            QComboBox {
                min-height: 20px;
                max-height: 20px;
                padding: 1px 3px;
            }

            /* 输入框 */
            QLineEdit {
                min-height: 20px;
                max-height: 20px;
                padding: 1px 3px;
            }

            /* 标签 */
            QLabel {
                margin: 0px;
                padding: 0px;
                min-height: 20px;
            }

            /* 数字输入框 */
            QSpinBox {
                min-height: 20px;
                max-height: 20px;
                padding: 1px 3px;
            }
        """
        self.setStyleSheet(style)

    def save_current_theme(self, theme):
        """保存当前主题设置"""
        try:
            with open('config/current_theme.json', 'w', encoding='utf-8') as f:
                json.dump(theme, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存当前主题失败: {e}")

    def load_saved_theme(self):
        """加载保存的主题设置"""
        try:
            if os.path.exists('config/current_theme.json'):
                with open('config/current_theme.json', 'r', encoding='utf-8') as f:
                    theme = json.load(f)
                    self.apply_theme(theme)
        except Exception as e:
            print(f"加载主题设置失败: {e}")

    def delete_selected_frames(self):
        """删除选中的帧"""
        # 获取选中的行
        selected_rows = set()
        for item in self.frame_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要删除的帧！")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_rows)} 个帧吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从后向前删除，避免索引变化
            for row in sorted(selected_rows, reverse=True):
                # 获帧名称
                frame_name = self.frame_table.item(row, 1).text()
                
                # 从协议对象中删除数据
                if self.protocol and frame_name in self.protocol.frames:
                    del self.protocol.frames[frame_name]
                
                # 从表格中删除行
                self.frame_table.removeRow(row)
            
            # 更新剩余行的序���
            for row in range(self.frame_table.rowCount()):
                self.frame_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # 显示删除成功消息
            self.append_log(f"""
            <div style='background-color: #d4edda; padding: 5px; margin: 2px;'>
                <span style='color: #155724;'>✓ 已删除 {len(selected_rows)} 个帧</span>
            </div>
            """)

    def send_all_frames(self):
        """发送所有帧"""
        self.logger.info("开始发送所有帧")
        if self.frame_table.rowCount() == 0:
            self.append_log("没有可发送的帧！", "warning")
            QMessageBox.warning(self, "警告", "没有可发送的帧！")
            return
            
        # 确认发送
        reply = QMessageBox.question(
            self,
            "确认发送",
            f"确定要发送所有帧吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 初始化计数器
            self.case_count = self.frame_table.rowCount()
            self.success_count = 0
            self.fail_count = 0
            self.timeout_count = 0
            success_count = 0  # 添加局部计数器
            fail_count = 0     # 添加局部计数器
            self.update_status_bar()
            
            # 从第一行开始发送
            for row in range(self.frame_table.rowCount()):
                try:
                    # 获取帧名称
                    frame_name = self.frame_table.item(row, 1).text()
                    self.append_log(f"正在发送帧 {row + 1} ({frame_name})...", "info")
                    
                    # 发送帧
                    self.frame_send_requested.emit((frame_name, row))
                    
                    # 更新状态
                    status_item = self.frame_table.item(row, 4)
                    if status_item:
                        status_item.setText("已发送")
                        success_count += 1
                        self.append_log(f"帧 {frame_name} 发送成功", "success")
                    
                except Exception as e:
                    fail_count += 1
                    self.append_log(f"发送帧 {frame_name} 失败: {str(e)}", "error")
                
                # 处理事件循环，保持界面响应
                QApplication.processEvents()
            
            # 显示发送统计
            self.append_log(f"发送完成: 成功 {success_count} 个, 失败 {fail_count} 个", 
                           "success" if fail_count == 0 else "warning")
            
            # 更新状态栏
            self.success_count += success_count
            self.fail_count += fail_count
            self.update_status_bar()

    def load_oad_config(self):
        """加载OAD配置"""
        try:
            if os.path.exists('config/oad_config.json'):
                with open('config/oad_config.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载OAD配置失败: {e}")
        return None

    def create_default_oad_config(self):
        """创建默认OAD配置"""
        default_config = {
            'OAD': {
                '电能表地址': '40000200',
                '日期时间': '40000201',
                '通信地址': '40000202',
                '表号': '40000203',
                '资产管理码': '40000204',
                '客户编号': '40000205'
            }
        }
        try:
            if not os.path.exists('config'):
                os.makedirs('config')
            with open('config/oad_config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"创建默认OAD配置失败: {e}")

    def on_oad_selected(self, oad_name):
        """处理OAD选择改变事件"""
        if self.oad_config and 'OAD' in self.oad_config and oad_name in self.oad_config['OAD']:
            self.oad_input.setText(self.oad_config['OAD'][oad_name])

    def create_frame_data(self):
        """根据当前配置创建帧数据"""
        try:
            self.append_log("开始创建帧数据...", "info")
            
            # 获取所有必要的参数
            direction = self.dir_combo.currentText()
            prm = self.prm_combo.currentText()
            function = self.func_combo.currentText()
            split_frame = self.split_combo.currentText()
            sc_flag = self.sc_combo.currentText()
            
            addr_type = self.addr_type_combo.currentText()
            ext_logic_addr = self.ext_logic_addr_combo.currentText()
            logic_addr_flag = self.logic_addr_flag_combo.currentText()
            addr_len = self.addr_len_input.text()  # 使用输入框的值
            
            sa_logic_addr = self.sa_logic_addr.text()
            logic_addr = self.logic_addr.text()
            comm_addr = self.comm_addr.text()
            
            service_type = self.service_type_combo.currentText()
            service_data_type = self.service_data_type_combo.currentText()
            service_priority = self.service_priority_combo.currentText()
            service_number = self.service_number_spin.value()
            
            # 获取并验证OAD值
            oad = '00000000'
            if self.oad_config and 'OAD' in self.oad_config:
                selected_oad = self.oad_combo.currentText()
                if selected_oad in self.oad_config['OAD']:
                    oad_value = self.oad_config['OAD'][selected_oad]
                    # 验证OAD值是否为8位十六进制
                    if isinstance(oad_value, str) and len(oad_value) == 8 and all(c in '0123456789ABCDEF' for c in oad_value.upper()):
                        oad = oad_value
                    else:
                        self.append_log(f"无效的OAD值: {oad_value}，使用默认值00000000", "warning")
            custom_data = self.custom_data.text()
            
            # 使用协议对象创建��
            if self.protocol:
                frame_data = self.protocol.create_frame(
                    direction, prm, function, split_frame, addr_type,
                    int(addr_len),  # 直接使用输入的数字
                    sa_logic_addr, logic_addr, comm_addr,
                    ext_logic_addr, logic_addr_flag,
                    service_type, service_data_type,
                    service_priority, service_number,
                    oad, custom_data
                )
                self.append_log(f"帧数据创建成功: {frame_data.hex()}", "success")
                return frame_data
            return None
        except Exception as e:
            self.append_log(f"创建帧数据失败: {str(e)}", "error")
            import traceback
            self.append_log(f"错误详情:\n{traceback.format_exc()}", "error")
            return None

    def update_status_bar(self):
        """更新状态栏信息"""
        self.case_count_label.setText(f"用例数: {self.case_count}")
        self.success_count_label.setText(f"成功: {self.success_count}")
        self.fail_count_label.setText(f"失败: {self.fail_count}")
        self.timeout_count_label.setText(f"超时: {self.timeout_count}")
        
        # 获取当前线程信息
        threads = threading.enumerate()
        self.thread_count_label.setText(f"线程数: {len(threads)}")
        thread_names = [t.name for t in threads]
        self.thread_list_label.setText(f"线程列表: {thread_names}")

    def init_receive_handler(self):
        """初始化接收数据处理"""
        # 在TestSystem中连接信号时会调用这个方法
        def handle_received_data(data_hex):
            self.append_log(f"收到响应: {data_hex}", "info")
            # 可以在这里添加更多的数据处理逻辑
        
        # 保存处理方法的引用
        self.handle_received_data = handle_received_data

    def display_received_message(self, message):
        """处理接收到的消息"""
        try:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
            self.append_log(f"收到数据: {message}", "info")
            
            # 将接收到的消息转换为字节
            received_bytes = bytes.fromhex(message)
            
            # 如果正在等待响应，检查是否是当前行的匹配
            if hasattr(self, 'waiting_for_response') and self.waiting_for_response:
                row = self.current_send_row
                
                # 获取匹配启用状态
                match_checkbox = self.frame_table.cellWidget(row, 5)
                if match_checkbox and match_checkbox.isChecked():
                    # 获取匹配规则
                    match_rule_widget = self.frame_table.cellWidget(row, 6)
                    if isinstance(match_rule_widget, QLineEdit):
                        match_rule = match_rule_widget.text()
                        if match_rule:
                            # 获取匹配模式
                            match_mode_combo = self.frame_table.cellWidget(row, 7)
                            if isinstance(match_mode_combo, QComboBox):
                                match_mode = match_mode_combo.currentText()
                                # 执行匹配
                                match_result = self.match_data(received_bytes, match_rule, match_mode)
                                
                                # 更新测试结果
                                result_item = self.frame_table.item(row, 8)
                                if not result_item:
                                    result_item = QTableWidgetItem()
                                    self.frame_table.setItem(row, 8, result_item)
                                
                                # 获取帧名称
                                frame_name = self.frame_table.item(row, 1).text()
                                
                                # 显示匹配结果
                                self.display_match_result(match_result, row, frame_name, result_item)
                                
                                # 更新状态栏计数
                                if match_result['match']:
                                    self.success_count += 1
                                else:
                                    self.fail_count += 1
                                self.update_status_bar()
                
                # 标记响应已处理
                self.waiting_for_response = False
                
        except Exception as e:
            self.append_log(f"处理接收数据错误: {str(e)}", "error")

    def match_data(self, data, rule, mode):
        """
        匹配数据并返回详细的匹配结果
        data: 接收到的数据
        rule: 匹配规则
        mode: 匹配模式 (HEX/ASCII)
        """
        try:
            if mode == "HEX":
                # 数据转换为十六进制字符串
                data_hex = data.hex().upper()
                # 规则中的空格去掉转换为大写
                rule = rule.replace(" ", "").upper()
                
                if len(data_hex) != len(rule):
                    return {
                        'match': False,
                        'error': f"长度不匹配: 规则长度={len(rule)}, 数据长度={len(data_hex)}"
                    }
                
                # 记录不匹配的位置
                mismatches = []
                for i in range(0, len(rule), 2):
                    rule_byte = rule[i:i+2]
                    data_byte = data_hex[i:i+2]
                    
                    if rule_byte == "XX":
                        continue
                    if rule_byte != data_byte:
                        mismatches.append((i//2, rule_byte, data_byte))
                
                if mismatches:
                    return {
                        'match': False,
                        'mismatches': mismatches,
                        'data': data_hex
                    }
                return {'match': True}
                
            else:  # ASCII模式
                data_ascii = data.decode('ascii', errors='ignore')
                rule_pattern = rule.replace("XX", ".")
                match = re.match(rule_pattern, data_ascii)
                if not match:
                    return {
                        'match': False,
                        'error': "ASCII模式匹配失败"
                    }
                return {'match': True}
                
        except Exception as e:
            return {
                'match': False,
                'error': f"匹配错误: {str(e)}"
            }

    def display_match_result(self, match_result, row, frame_name, result_item):
        """显示匹配结果"""
        if match_result['match']:
            result_item.setText("PASS")
            result_item.setBackground(QColor("#90EE90"))  # 浅绿色
            self.append_log(f"帧 {frame_name} 匹配成功", "success")
        else:
            if 'mismatches' in match_result:
                # 显示具体的不匹配位置
                result_item.setText("FAIL")
                result_item.setBackground(QColor("#FFB6C1"))  # 浅红色
                
                # 构建带颜色标记的不匹配信息
                data = match_result['data']
                colored_data = []
                last_pos = 0
                
                for pos, expected, actual in match_result['mismatches']:
                    # 添加正常部分
                    colored_data.append(data[last_pos:pos*2])
                    # 添加红色标记的不匹配部分
                    colored_data.append(f'<span style="color: red;">{data[pos*2:pos*2+2]}</span>')
                    last_pos = pos*2 + 2
                
                # 添加剩余部分
                colored_data.append(data[last_pos:])
                
                # 显示详细的不匹配信息
                self.append_log(f"""
                <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                    <span style='color: #721c24;'>帧 {frame_name} 匹配失败</span><br>
                    <span style='font-family: monospace;'>实��数据: {''.join(colored_data)}</span><br>
                    <span style='font-family: monospace;'>期望规则: {match_result.get('rule', '')}</span>
                </div>
                """, "error")

    def check_frame_timeout(self):
        """检查当前帧是否超时"""
        try:
            # 如果已经收到响应，不显示超时信息
            if not self.waiting_for_response:
                return
            
            # 更新测试结果为"超时"
            result_item = self.frame_table.item(self.current_send_row, 8)
            if not result_item:
                result_item = QTableWidgetItem()
                self.frame_table.setItem(self.current_send_row, 8, result_item)
            
            result_item.setText("超时")
            result_item.setBackground(QColor("#FFA500"))  # 橙色背景
            
            # 更新状态栏计数
            self.timeout_count += 1
            self.update_status_bar()
            
            # 重置状态
            self.waiting_for_response = False
            
        except Exception as e:
            self.append_log(f"超时检查错误: {str(e)}", "error")
