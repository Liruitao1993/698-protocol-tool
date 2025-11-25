from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QComboBox, QLineEdit, QPushButton, QLabel, 
                           QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout, QSpinBox, QHeaderView,
                           QFileDialog, QMessageBox, QTextEdit, QCheckBox, QDockWidget, QScrollArea, 
                           QMenu, QDialog, QDialogButtonBox, QSizePolicy, QTabWidget, QSplitter)
from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtGui import QRegularExpressionValidator, QFont, QColor, QActionGroup, QAction, QIntValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import QApplication, QStyleFactory
import configparser
import os
import csv
from functools import partial
import re
from PySide6.QtCore import QDateTime
import json
import serial.tools.list_ports
import threading
from utils.logger import Logger

class MainWindow(QMainWindow):
    frame_send_requested = Signal(str, int)  # (frame_name, row)
    serial_connect_requested = Signal(object)  # 添加串口连接请求信号
    
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
        
        # 不再需要创建停靠日志窗口，因为已经在init_ui中创建
        # self.create_dockable_log_window()
        
        # 添加表格缩放功能
        self.table_zoom_factor = 1.0
        self.frame_table.viewport().installEventFilter(self)
        
        # 创建定时器定期更新串口列表
        self.port_update_timer = QTimer(self)
        self.port_update_timer.timeout.connect(self.update_port_list)
        self.port_update_timer.start(1000)
        
        # 使用PySide6原生默认风格
        
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
        # 使用PySide6原生默认风格，不创建主题菜单
        pass
        
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
        
        # 服务器逻辑地址选择（根据协议：bit4和bit5组成逻辑地址）
        # bit5=0, bit4=0 → 逻辑地址0
        # bit5=0, bit4=1 → 逻辑地址1
        # bit5=1 → 有扩展逻辑地址，地址值2-255
        self.sa_logic_addr_combo = QComboBox()
        self.sa_logic_addr_combo.addItems(['0', '1', '2-255(扩展)'])
        self.sa_logic_addr_combo.currentTextChanged.connect(self.on_sa_logic_addr_changed)
        
        # 扩展逻辑地址输入框（当选择2-255时启用）
        self.sa_ext_logic_input = QLineEdit()
        self.sa_ext_logic_input.setPlaceholderText("输入2-255的十进制数")
        self.sa_ext_logic_input.setText("2")  # 默认值
        ext_logic_validator = QIntValidator(2, 255)
        self.sa_ext_logic_input.setValidator(ext_logic_validator)
        self.sa_ext_logic_input.setEnabled(False)  # 默认禁用
        
        # 修改地址长度为输入框
        self.addr_len_input = QLineEdit()
        self.addr_len_input.setText("6")  # 默认值为6
        self.addr_len_input.setPlaceholderText("范围0-15")
        # 限制输入范围为0-15的数字
        addr_len_validator = QIntValidator(0, 15)
        self.addr_len_input.setValidator(addr_len_validator)
        self.addr_len_input.setFixedWidth(60)  # 设置固定宽度
        self.addr_len_input.setAlignment(Qt.AlignCenter)  # 文本居中对齐

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
        comm_addr_validator = QRegularExpressionValidator(QRegularExpression("^[0-9A-Fa-f]{1,12}$"))
        self.comm_addr.setValidator(comm_addr_validator)
        
        # 创建自定义数据输入框
        self.custom_data = QLineEdit()
        self.custom_data.setPlaceholderText("输入十六进制数据（可选）")
        hex_validator = QRegularExpressionValidator(QRegularExpression("^[0-9A-Fa-f]*$"))
        self.custom_data.setValidator(hex_validator)
        
        # 创建服务类型和数据类型选择框（按照DL/T 698.45协议定义）
        self.service_type_combo = QComboBox()
        # 格式: 显示名称 (编码值)
        self.service_type_combo.addItems([
            'LINK-Request 建立应用连接请求 (1)',
            'RELEASE-Request 断开应用连接请求 (3)',
            'GET-Request 读取请求 (5)',
            'SET-Request 设置请求 (6)',
            'ACTION-Request 操作请求 (7)',
            'REPORT-Response 上报应答 (8)',
            'PROXY-Request 代理请求 (9)',
            'COMPACT-GET-Request 简化读取请求 (133)',
            'COMPACT-SET-Request 简化设置请求 (134)'
        ])
        self.service_type_combo.currentTextChanged.connect(self.on_service_type_changed)
        
        # 服务类型编码映射表
        self.service_type_codes = {
            'LINK-Request 建立应用连接请求 (1)': '01',
            'RELEASE-Request 断开应用连接请求 (3)': '03',
            'GET-Request 读取请求 (5)': '05',
            'SET-Request 设置请求 (6)': '06',
            'ACTION-Request 操作请求 (7)': '07',
            'REPORT-Response 上报应答 (8)': '08',
            'PROXY-Request 代理请求 (9)': '09',
            'COMPACT-GET-Request 简化读取请求 (133)': '85',
            'COMPACT-SET-Request 简化设置请求 (134)': '86'
        }
        
        # 服务数据类型编码映射表
        self.service_data_type_codes = {
            # LINK-Request 建立应用连接请求
            'CONNECT-Request 建立应用连接请求 [0]': '00',
            # RELEASE-Request 断开应用连接请求
            'RELEASE-Request 断开应用连接请求 [0]': '00',
            # GET-Request 读取请求
            'GetRequestNormal 读取一个对象属性 [1]': '01',
            'GetRequestNormalList 读取若干个对象属性 [2]': '02',
            'GetRequestRecord 读取一个记录型对象属性 [3]': '03',
            'GetRequestRecordList 读取若干个记录型对象属性 [4]': '04',
            'GetRequestNext 读取分帧传输的下一帧数据 [5]': '05',
            'GetRequestMD5 读取一个对象属性的MD5值 [6]': '06',
            # SET-Request 设置请求
            'SetRequestNormal 设置一个对象属性 [1]': '01',
            'SetRequestNormalList 设置若干个对象属性 [2]': '02',
            'SetThenGetRequestNormalList 设置后读取若干个对象属性 [3]': '03',
            # ACTION-Request 操作请求
            'ActionRequestNormal 操作一个对象方法 [1]': '01',
            'ActionRequestNormalList 操作若干个对象方法 [2]': '02',
            'ActionThenGetRequestNormalList 操作后读取若干个对象属性 [3]': '03',
            # REPORT-Response 上报应答
            'ReportResponseRecord 上报一个记录型对象 [1]': '01',
            'ReportResponseRecordList 上报若干个记录型对象 [2]': '02',
            'ReportResponseTransData 上报透传的数据 [3]': '03',
            # PROXY-Request 代理请求
            'ProxyRequestGetList 代理读取若干个服务器的若干个对象属性 [1]': '01',
            'ProxyRequestSetList 代理设置若干个服务器的若干个对象属性 [2]': '02',
            'ProxyRequestActionList 代理操作若干个服务器的若干个对象方法 [3]': '03',
            'ProxyRequestTransCommandList 代理透传若干个服务器的命令 [4]': '04',
            'ProxyRequestGetTransData 代理读取若干个服务器的若干个透传对象 [5]': '05',
            # COMPACT-GET-Request 简化读取请求
            'CompactGetRequestNormal 简化读取一个对象属性 [1]': '01',
            # COMPACT-SET-Request 简化设置请求
            'CompactSetRequestNormal 简化设置一个对象属性 [1]': '01'
        }
        
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
        oad_validator = QRegularExpressionValidator(QRegularExpression("^[0-9A-Fa-f]{8}$"))
        self.oad_input.setValidator(oad_validator)
        
        
        # 创建主布局（水平分割：左侧配置面板 + 右侧主区域）
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用QSplitter实现可拖拽的分割线
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)  # 设置分割线宽度
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cccccc;
            }
            QSplitter::handle:hover {
                background-color: #999999;
            }
        """)
        
        # ========== 左侧：配置面板 ==========
        self.create_protocol_config_panel()
        splitter.addWidget(self.protocol_config_panel)
        
        # ========== 右侧：主工作区域 ==========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(10, 10, 10, 10)

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
        right_layout.addWidget(serial_group)  # 添加到右侧布局

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
            0: (40, QHeaderView.ResizeMode.Fixed),              # 序号列
            1: (100, QHeaderView.ResizeMode.Interactive),       # 名称列
            2: (300, QHeaderView.ResizeMode.Interactive),       # 帧内容列
            3: (150, QHeaderView.ResizeMode.Fixed),             # 操作列
            4: (80, QHeaderView.ResizeMode.Fixed),              # 状态列
            5: (80, QHeaderView.ResizeMode.Fixed),              # 启用匹配列
            6: (300, QHeaderView.ResizeMode.Interactive),       # 匹配规则列
            7: (80, QHeaderView.ResizeMode.Fixed),              # 匹配模式列
            8: (100, QHeaderView.ResizeMode.Interactive),       # 测试结果列
            9: (80, QHeaderView.ResizeMode.Fixed)               # 超时列
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
        
        # 设置表格内容的对齐方式 - 使用原生样式
        self.frame_table.setStyleSheet("""
            QTableWidget::item {
                padding: 5px;
                text-align: center;
            }
            QTableWidget QLineEdit {
                padding: 2px;
                text-align: center;
            }
            QTableWidget QComboBox {
                text-align: center;
            }
        """)
        
        frame_layout.addWidget(self.frame_table)
        
        frame_group.setLayout(frame_layout)
        right_layout.addWidget(frame_group, 1)  # 让帧列表占主要空间，添加到右侧布局

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
        
        # 移除操作组的自定义样式，使用原生样式
        
        right_layout.addWidget(button_group)  # 添加到右侧布局
        
        # ========== 日志输出区域 ==========
        log_group = QGroupBox("📝 日志输出")
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)
        log_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建日志文本框
        self.receive_display = QTextEdit()
        self.receive_display.setReadOnly(True)
        self.receive_display.setMinimumHeight(200)  # 设置最小高度
        self.receive_display.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        log_layout.addWidget(self.receive_display)
        
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)  # 添加到右侧布局
        
        # 将右侧区域添加到splitter
        splitter.addWidget(right_widget)
        
        # 设置初始分割比例：左侧420px，右侧占据剩余空间
        splitter.setStretchFactor(0, 0)  # 左侧不伸缩
        splitter.setStretchFactor(1, 1)  # 右侧可以伸缩
        splitter.setSizes([420, 800])  # 设置初始宽度
        
        # 将splitter添加到主布局
        main_layout.addWidget(splitter)

        # 连接单格变化信号
        self.frame_table.cellChanged.connect(self.on_cell_changed)
        # 添加编辑开始信号接
        self.frame_table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 添加属性来存储原始名称
        self.editing_frame_name = None


        # 设置所有下拉框的大小策略
        for combo in [self.dir_combo, self.prm_combo, self.split_combo, 
                     self.sc_combo, self.func_combo, self.addr_type_combo,
                     self.sa_logic_addr_combo]:
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

    def on_sa_logic_addr_changed(self, text):
        """处理SA逻辑地址改变事件（根据协议：bit4和bit5组成逻辑地址）"""
        # 选择2-255时启用扩展逻辑地址输入框
        self.sa_ext_logic_input.setEnabled(text == '2-255(扩展)')
        if text != '2-255(扩展)':
            self.sa_ext_logic_input.clear()
            self.sa_ext_logic_input.setText("2")  # 恢复默认值

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

    def update_composite_elements(self, count):
        """更新复合类型（Array/Structure）的元素输入控件"""
        # 清空现有元素
        while self.elements_layout.count():
            child = self.elements_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.element_inputs = []
        
        # 常用数据类型列表（用于元素类型选择）
        common_types = [
            'Bool(3)',
            'DoubleLong(5)',
            'DoubleLongUnsigned(6)',
            'OctetString(9)',
            'Integer(15)',
            'Long(16)',
            'Unsigned(17)',
            'LongUnsigned(18)',
            'Enum(22)',
            'OAD(45)',
            'OI(80)'
        ]
        
        # 为每个元素创建输入控件
        for i in range(count):
            # 元素容器
            element_group = QGroupBox(f"元素 {i+1}")
            element_group.setStyleSheet("""
                QGroupBox {
                    font-size: 9pt;
                    padding: 3px;
                    margin-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 7px;
                    padding: 0 3px;
                }
            """)
            element_layout = QVBoxLayout()
            element_layout.setSpacing(3)  # 减小间距从5到3
            element_layout.setContentsMargins(5, 8, 5, 5)  # 调整边距
            
            # 类型选择
            type_layout = QHBoxLayout()
            type_layout.setSpacing(5)  # 设置合理间距
            type_label = QLabel("类型:")
            type_label.setFixedWidth(40)  # 固定标签宽度避免重叠
            type_label.setStyleSheet("font-size: 9pt;")
            type_layout.addWidget(type_label)
            type_combo = QComboBox()
            type_combo.addItems(common_types)
            type_combo.setCurrentIndex(0)  # 默认Bool类型
            type_combo.setFixedHeight(22)  # 减小下拉框高度
            type_combo.setStyleSheet("font-size: 9pt;")
            type_layout.addWidget(type_combo, 1)
            element_layout.addLayout(type_layout)
            
            # 值输入（动态变化）
            value_widget = QWidget()
            value_layout = QVBoxLayout(value_widget)
            value_layout.setSpacing(2)  # 减小间距从3到2
            value_layout.setContentsMargins(0, 0, 0, 0)
            element_layout.addWidget(value_widget)
            
            # 连接类型变化信号
            type_combo.currentTextChanged.connect(
                lambda text, widget=value_widget, layout=value_layout: 
                self.update_element_value_input(text, widget, layout)
            )
            
            element_group.setLayout(element_layout)
            self.elements_layout.addWidget(element_group)
            
            # 存储元素信息
            self.element_inputs.append({
                'type_combo': type_combo,
                'value_widget': value_widget,
                'value_layout': value_layout
            })
            
            # 初始化默认值输入
            self.update_element_value_input(type_combo.currentText(), value_widget, value_layout)

    def update_element_value_input(self, data_type, value_widget, value_layout):
        """更新元素的值输入控件"""
        # 清空现有控件
        while value_layout.count():
            child = value_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not data_type:
            return
        
        type_code = data_type.split('(')[1].rstrip(')')
        
        # 根据类型创建相应的输入控件
        value_layout_h = QHBoxLayout()
        value_layout_h.setSpacing(5)  # 设置合理间距
        value_label = QLabel("值:")
        value_label.setFixedWidth(40)  # 固定标签宽度避免重叠
        value_label.setStyleSheet("font-size: 9pt;")
        value_layout_h.addWidget(value_label)
        
        if type_code == '3':  # Bool
            value_input = QComboBox()
            value_input.addItems(['False(00)', 'True(01)'])
            value_input.setFixedHeight(22)  # 减小高度
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('bool_combo')
        elif type_code in ['5', '6']:  # DoubleLong, DoubleLongUnsigned
            value_input = QLineEdit()
            value_input.setPlaceholderText("10进制数")
            value_input.setText("0")
            value_input.setFixedHeight(22)  # 减小高度
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('int_input')
        elif type_code == '9':  # OctetString
            value_input = QLineEdit()
            value_input.setPlaceholderText("HEX: 01 02 03")
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('hex_input')
        elif type_code in ['15', '17']:  # Integer, Unsigned (1字节)
            value_input = QSpinBox()
            if type_code == '15':
                value_input.setRange(-128, 127)
            else:
                value_input.setRange(0, 255)
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('byte_spin')
        elif type_code in ['16', '18']:  # Long, LongUnsigned (2字节)
            value_input = QLineEdit()
            if type_code == '16':
                value_input.setPlaceholderText("-32768~32767")
            else:
                value_input.setPlaceholderText("0~65535")
            value_input.setText("0")
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('int_input')
        elif type_code == '22':  # Enum
            value_input = QSpinBox()
            value_input.setRange(0, 255)
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('byte_spin')
        elif type_code == '45':  # OAD
            value_input = QLineEdit()
            value_input.setPlaceholderText("HEX: 40000200")
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('oad_input')
        elif type_code == '80':  # OI
            value_input = QLineEdit()
            value_input.setPlaceholderText("HEX: 4000")
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('oi_input')
        else:
            value_input = QLineEdit()
            value_input.setPlaceholderText("输入值")
            value_input.setFixedHeight(22)
            value_input.setStyleSheet("font-size: 9pt;")
            value_input.setObjectName('generic_input')
        
        value_layout_h.addWidget(value_input, 1)
        value_layout.addLayout(value_layout_h)
        
        # 将输入控件存储到value_widget的属性中，供后续读取
        value_widget.setProperty('value_input', value_input)

    def on_data_type_changed(self, data_type):
        """数据类型变化时更新参数输入区域"""
        # 清空现有的参数输入控件
        while self.param_input_layout.count():
            child = self.param_input_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not data_type:
            return
        
        type_code = data_type.split('(')[1].rstrip(')')
        
        # 根据不同类型添加相应的输入控件
        if type_code == '0':  # NullData
            label = QLabel("提示: NULL类型无需参数")
            label.setStyleSheet("color: #666; font-style: italic; font-size: 9pt;")
            self.param_input_layout.addWidget(label)
            
        elif type_code in ['1', '2']:  # Array, Structure
            # 复合类型，需要长度参数
            len_layout = QHBoxLayout()
            len_layout.setSpacing(5)
            len_label = QLabel("元素个数:")
            len_label.setFixedWidth(60)
            len_label.setStyleSheet("font-size: 9pt;")
            len_layout.addWidget(len_label)
            self.data_len_input = QSpinBox()
            self.data_len_input.setRange(0, 10)  # 限制最大9个元素，避免界面过长
            self.data_len_input.setValue(2)
            self.data_len_input.setFixedHeight(22)
            self.data_len_input.setStyleSheet("font-size: 9pt;")
            self.data_len_input.valueChanged.connect(self.update_composite_elements)
            len_layout.addWidget(self.data_len_input, 1)
            self.param_input_layout.addLayout(len_layout)
            
            # 创建元素定义区域容器
            self.elements_container = QWidget()
            self.elements_layout = QVBoxLayout(self.elements_container)
            self.elements_layout.setSpacing(4)  # 减小间距从5到4
            self.elements_layout.setContentsMargins(0, 3, 0, 0)  # 减小边距
            self.param_input_layout.addWidget(self.elements_container)
            
            # 初始化元素输入
            self.element_inputs = []  # 存储每个元素的输入控件
            self.update_composite_elements(2)  # 默认2个元素
            
        elif type_code == '3':  # Bool
            bool_layout = QHBoxLayout()
            bool_layout.setSpacing(5)
            bool_label = QLabel("值:")
            bool_label.setFixedWidth(60)
            bool_label.setStyleSheet("font-size: 9pt;")
            bool_layout.addWidget(bool_label)
            self.bool_value_combo = QComboBox()
            self.bool_value_combo.addItems(['False(00)', 'True(01)'])
            self.bool_value_combo.setFixedHeight(22)
            self.bool_value_combo.setStyleSheet("font-size: 9pt;")
            bool_layout.addWidget(self.bool_value_combo, 1)
            self.param_input_layout.addLayout(bool_layout)
            
        elif type_code == '4':  # BitString
            # 位串长度
            len_layout = QHBoxLayout()
            len_layout.setSpacing(5)
            len_label = QLabel("位数:")
            len_label.setFixedWidth(60)
            len_label.setStyleSheet("font-size: 9pt;")
            len_layout.addWidget(len_label)
            self.bitstring_len_input = QSpinBox()
            self.bitstring_len_input.setRange(1, 255)
            self.bitstring_len_input.setValue(8)
            self.bitstring_len_input.setFixedHeight(22)
            self.bitstring_len_input.setStyleSheet("font-size: 9pt;")
            len_layout.addWidget(self.bitstring_len_input, 1)
            self.param_input_layout.addLayout(len_layout)
            
            # 值输入
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("值(HEX):")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.bitstring_value_input = QLineEdit()
            self.bitstring_value_input.setPlaceholderText("例: FF")
            self.bitstring_value_input.setFixedHeight(22)
            self.bitstring_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.bitstring_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code in ['5', '6']:  # DoubleLong, DoubleLongUnsigned
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("值:")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.double_long_input = QLineEdit()
            self.double_long_input.setPlaceholderText("输入10进制数, 例: 1000")
            self.double_long_input.setFixedHeight(22)
            self.double_long_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.double_long_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code in ['9', '10', '12']:  # OctetString, VisibleString, Utf8String
            # 字符串/字节串输入
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            if type_code == '9':
                value_label = QLabel("字节串(HEX):")
                value_label.setFixedWidth(80)
                value_label.setStyleSheet("font-size: 9pt;")
                value_layout.addWidget(value_label)
                self.string_value_input = QLineEdit()
                self.string_value_input.setPlaceholderText("例: 01 02 03 04")
            else:
                value_label = QLabel("字符串:")
                value_label.setFixedWidth(60)
                value_label.setStyleSheet("font-size: 9pt;")
                value_layout.addWidget(value_label)
                self.string_value_input = QLineEdit()
                self.string_value_input.setPlaceholderText("例: HELLO")
            self.string_value_input.setFixedHeight(22)
            self.string_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.string_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code in ['15', '17']:  # Integer, Unsigned (1字节)
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("值:")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.byte_value_input = QSpinBox()
            if type_code == '15':  # Integer
                self.byte_value_input.setRange(-128, 127)
            else:  # Unsigned
                self.byte_value_input.setRange(0, 255)
            self.byte_value_input.setFixedHeight(22)
            self.byte_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.byte_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code in ['16', '18']:  # Long, LongUnsigned (2字节)
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("值:")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.word_value_input = QLineEdit()
            if type_code == '16':
                self.word_value_input.setPlaceholderText("范围: -32768~32767")
            else:
                self.word_value_input.setPlaceholderText("范围: 0~65535")
            self.word_value_input.setFixedHeight(22)
            self.word_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.word_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code == '22':  # Enum
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("枚举值:")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.enum_value_input = QSpinBox()
            self.enum_value_input.setRange(0, 255)
            self.enum_value_input.setFixedHeight(22)
            self.enum_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.enum_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code in ['23', '24']:  # Float32, Float64
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("浮点数:")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.float_value_input = QLineEdit()
            self.float_value_input.setPlaceholderText("例: 3.14159")
            self.float_value_input.setFixedHeight(22)
            self.float_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.float_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code == '45':  # OAD
            # OAD输入 (4字节)
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("OAD(HEX):")
            value_label.setFixedWidth(70)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.oad_value_input = QLineEdit()
            self.oad_value_input.setPlaceholderText("例: 40000200")
            self.oad_value_input.setFixedHeight(22)
            self.oad_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.oad_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        elif type_code == '80':  # OI
            # OI输入 (2字节)
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("OI(HEX):")
            value_label.setFixedWidth(60)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.oi_value_input = QLineEdit()
            self.oi_value_input.setPlaceholderText("例: 4000")
            self.oi_value_input.setFixedHeight(22)
            self.oi_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.oi_value_input, 1)
            self.param_input_layout.addLayout(value_layout)
            
        else:
            # 其他类型，提供通用HEX输入
            value_layout = QHBoxLayout()
            value_layout.setSpacing(5)
            value_label = QLabel("数据(HEX):")
            value_label.setFixedWidth(70)
            value_label.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(value_label)
            self.generic_value_input = QLineEdit()
            self.generic_value_input.setPlaceholderText("输入16进制数据")
            self.generic_value_input.setFixedHeight(22)
            self.generic_value_input.setStyleSheet("font-size: 9pt;")
            value_layout.addWidget(self.generic_value_input, 1)
            self.param_input_layout.addLayout(value_layout)

    def generate_element_data(self, type_code, value_input):
        """生成单个元素的数据"""
        try:
            if type_code == '3':  # Bool
                value = 1 if 'True' in value_input.currentText() else 0
                return f"03 {value:02X}"
                
            elif type_code == '5':  # DoubleLong
                value = int(value_input.text() or "0")
                if value < 0:
                    value = (1 << 32) + value
                # 生成完整的十六进制字符串，然后按每2位切分
                hex_value = f"{value:08X}"  # 8位十六进制
                hex_bytes = ' '.join([hex_value[i:i+2] for i in range(0, len(hex_value), 2)])
                return f"05 {hex_bytes}"
                
            elif type_code == '6':  # DoubleLongUnsigned
                value = int(value_input.text() or "0")
                hex_value = f"{value:08X}"
                hex_bytes = ' '.join([hex_value[i:i+2] for i in range(0, len(hex_value), 2)])
                return f"06 {hex_bytes}"
                
            elif type_code == '9':  # OctetString
                value_hex = value_input.text().strip().replace(' ', '')
                if value_hex:
                    length = len(value_hex) // 2
                    # 确保字节串按每2位切分
                    hex_bytes = ' '.join([value_hex[i:i+2] for i in range(0, len(value_hex), 2)])
                    return f"09 {length:02X} {hex_bytes}"
                else:
                    return "09 00"
                    
            elif type_code == '15':  # Integer
                value = value_input.value()
                if value < 0:
                    value = 256 + value
                return f"0F {value:02X}"
                
            elif type_code == '16':  # Long
                value = int(value_input.text() or "0")
                if value < 0:
                    value = 65536 + value
                hex_value = f"{value:04X}"
                hex_bytes = ' '.join([hex_value[i:i+2] for i in range(0, len(hex_value), 2)])
                return f"10 {hex_bytes}"
                
            elif type_code == '17':  # Unsigned
                value = value_input.value()
                return f"11 {value:02X}"
                
            elif type_code == '18':  # LongUnsigned
                value = int(value_input.text() or "0")
                hex_value = f"{value:04X}"
                hex_bytes = ' '.join([hex_value[i:i+2] for i in range(0, len(hex_value), 2)])
                return f"12 {hex_bytes}"
                
            elif type_code == '22':  # Enum
                value = value_input.value()
                return f"16 {value:02X}"
                
            elif type_code == '45':  # OAD
                value_hex = value_input.text().strip().replace(' ', '')
                if len(value_hex) == 8:
                    hex_bytes = ' '.join([value_hex[i:i+2] for i in range(0, len(value_hex), 2)])
                    return f"2D {hex_bytes}"
                else:
                    return "2D 40 00 02 00"
                    
            elif type_code == '80':  # OI
                value_hex = value_input.text().strip().replace(' ', '')
                if len(value_hex) == 4:
                    hex_bytes = ' '.join([value_hex[i:i+2] for i in range(0, len(value_hex), 2)])
                    return f"50 {hex_bytes}"
                else:
                    return "50 40 00"
            else:
                return f"{type_code} 00"
        except Exception as e:
            self.append_log(f"元素数据生成错误: {str(e)}", "error")
            return f"{type_code} 00"

    def generate_data(self):
        """生成数据"""
        try:
            data_type = self.data_type_combo.currentText()
            
            # 根据数据类型生成示例数据
            type_code = data_type.split('(')[1].rstrip(')')
            generated_data = ""
            
            # 生成数据，根据用户输入的参数
            if type_code == '0':  # NullData
                generated_data = "00"  # NULL类型
                
            elif type_code == '1':  # Array
                # 复合类型，需要包含长度
                try:
                    length = len(self.element_inputs)
                    # 格式: 类型码 + 元素个数 + 元素内容
                    generated_data = f"01 {length:02X}"
                    
                    # 读取每个元素的类型和值
                    for elem in self.element_inputs:
                        elem_type = elem['type_combo'].currentText()
                        elem_type_code = elem_type.split('(')[1].rstrip(')')
                        elem_value_input = elem['value_widget'].property('value_input')
                        
                        # 生成元素数据
                        elem_data = self.generate_element_data(elem_type_code, elem_value_input)
                        generated_data += f" {elem_data}"
                except Exception as e:
                    self.append_log(f"Array生成错误: {str(e)}", "error")
                    generated_data = "01 02 06 00 00 00 00 06 00 00 00 01"  # 默认礧2个元素
                    
            elif type_code == '2':  # Structure
                # 复合类型，需要包含长度
                try:
                    length = len(self.element_inputs)
                    # 格式: 类型码 + 元素个数 + 元素内容
                    generated_data = f"02 {length:02X}"
                    
                    # 读取每个元素的类型和值
                    for elem in self.element_inputs:
                        elem_type = elem['type_combo'].currentText()
                        elem_type_code = elem_type.split('(')[1].rstrip(')')
                        elem_value_input = elem['value_widget'].property('value_input')
                        
                        # 生成元素数据
                        elem_data = self.generate_element_data(elem_type_code, elem_value_input)
                        generated_data += f" {elem_data}"
                except Exception as e:
                    self.append_log(f"Structure生成错误: {str(e)}", "error")
                    generated_data = "02 02 11 00 12 00 01"  # 默认礧2个元素
                    
            elif type_code == '3':  # Bool
                # 基本类型，不需要长度，只需要值
                try:
                    value = 1 if 'True' in self.bool_value_combo.currentText() else 0
                    generated_data = f"03 {value:02X}"
                except:
                    generated_data = "03 00"  # 默认False
                    
            elif type_code == '4':  # BitString
                # 需要长度参数
                try:
                    bit_len = self.bitstring_len_input.value()
                    value_hex = self.bitstring_value_input.text().strip().replace(' ', '')
                    if not value_hex:
                        value_hex = "FF"
                    generated_data = f"04 {bit_len:02X} {value_hex}"
                except:
                    generated_data = "04 08 FF"  # 默认8位
                    
            elif type_code == '5':  # DoubleLong
                # 基本类型，不需要长度，直接是4字节值
                try:
                    value = int(self.double_long_input.text())
                    # 转换为带符号4字节
                    if value < 0:
                        value = (1 << 32) + value
                    generated_data = f"05 {value:08X}"
                    # 插入空格
                    generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                except:
                    generated_data = "05 00 00 00 00"
                    
            elif type_code == '6':  # DoubleLongUnsigned
                # 基本类型，不需要长度
                try:
                    value = int(self.double_long_input.text())
                    generated_data = f"06 {value:08X}"
                    generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                except:
                    generated_data = "06 00 00 00 00"
                    
            elif type_code == '9':  # OctetString
                # 需要长度参数
                try:
                    value_hex = self.string_value_input.text().strip().replace(' ', '')
                    if value_hex:
                        length = len(value_hex) // 2
                        generated_data = f"09 {length:02X} {value_hex}"
                        generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                    else:
                        generated_data = "09 00"  # 空字节串
                except:
                    generated_data = "09 04 01 02 03 04"
                    
            elif type_code in ['10', '12']:  # VisibleString, Utf8String
                # 需要长度参数
                try:
                    text = self.string_value_input.text().strip()
                    if text:
                        # 转换为HEX
                        hex_str = ' '.join([f"{ord(c):02X}" for c in text])
                        length = len(text)
                        type_prefix = '0A' if type_code == '10' else '0C'
                        generated_data = f"{type_prefix} {length:02X} {hex_str}"
                    else:
                        type_prefix = '0A' if type_code == '10' else '0C'
                        generated_data = f"{type_prefix} 00"  # 空字符串
                except:
                    type_prefix = '0A' if type_code == '10' else '0C'
                    generated_data = f"{type_prefix} 05 48 45 4C 4C 4F"  # "HELLO"
                    
            elif type_code == '15':  # Integer (1字节)
                # 基本类型，不需要长度
                try:
                    value = self.byte_value_input.value()
                    if value < 0:
                        value = 256 + value
                    generated_data = f"0F {value:02X}"
                except:
                    generated_data = "0F 00"
                    
            elif type_code == '16':  # Long (2字节)
                # 基本类型，不需要长度
                try:
                    value = int(self.word_value_input.text())
                    if value < 0:
                        value = 65536 + value
                    generated_data = f"10 {value:04X}"
                    generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                except:
                    generated_data = "10 00 00"
                    
            elif type_code == '17':  # Unsigned (1字节)
                # 基本类型，不需要长度
                try:
                    value = self.byte_value_input.value()
                    generated_data = f"11 {value:02X}"
                except:
                    generated_data = "11 00"
                    
            elif type_code == '18':  # LongUnsigned (2字节)
                # 基本类型，不需要长度
                try:
                    value = int(self.word_value_input.text())
                    generated_data = f"12 {value:04X}"
                    generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                except:
                    generated_data = "12 00 00"
                    
            elif type_code == '22':  # Enum
                # 基本类型，不需要长度
                try:
                    value = self.enum_value_input.value()
                    generated_data = f"16 {value:02X}"
                except:
                    generated_data = "16 00"
                    
            elif type_code in ['23', '24']:  # Float32, Float64
                # 基本类型，不需要长度
                try:
                    import struct
                    value = float(self.float_value_input.text())
                    if type_code == '23':  # Float32
                        hex_bytes = struct.pack('>f', value).hex().upper()
                        generated_data = f"17 {hex_bytes}"
                    else:  # Float64
                        hex_bytes = struct.pack('>d', value).hex().upper()
                        generated_data = f"18 {hex_bytes}"
                    generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                except:
                    if type_code == '23':
                        generated_data = "17 00 00 00 00"
                    else:
                        generated_data = "18 00 00 00 00 00 00 00 00"
                        
            elif type_code == '45':  # OAD
                # 基本类型，不需要长度，4字节固定长度
                try:
                    value_hex = self.oad_value_input.text().strip().replace(' ', '')
                    if len(value_hex) == 8:
                        generated_data = f"2D {value_hex}"
                        generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                    else:
                        generated_data = "2D 40 00 02 00"  # 默认值
                except:
                    generated_data = "2D 40 00 02 00"
                    
            elif type_code == '80':  # OI
                # 基本类型，不需要长度，2字节固定长度
                try:
                    value_hex = self.oi_value_input.text().strip().replace(' ', '')
                    if len(value_hex) == 4:
                        generated_data = f"50 {value_hex}"
                        generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                    else:
                        generated_data = "50 40 00"  # 默认值
                except:
                    generated_data = "50 40 00"
                    
            else:
                # 其他类型使用通用输入
                try:
                    value_hex = self.generic_value_input.text().strip().replace(' ', '')
                    if value_hex:
                        generated_data = f"{type_code} {value_hex}"
                        generated_data = ' '.join([generated_data[i:i+2] for i in range(0, len(generated_data), 2)])
                    else:
                        generated_data = f"{type_code} 00"
                except:
                    generated_data = f"{type_code} 00"
            
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
        """处理服务类型改变事件（根据DL/T 698.45协议）"""
        self.service_data_type_combo.clear()
        
        # 根据服务类型显示对应的数据类型选项（格式: 显示名称 [编码值]）
        if 'LINK-Request' in text:  # 建立应用连接请求 (1)
            self.service_data_type_combo.addItems([
                'CONNECT-Request 建立应用连接请求 [0]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'RELEASE-Request' in text:  # 断开应用连接请求 (3)
            self.service_data_type_combo.addItems([
                'RELEASE-Request 断开应用连接请求 [0]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'GET-Request' in text and 'COMPACT' not in text:  # 读取请求 (5)
            self.service_data_type_combo.addItems([
                'GetRequestNormal 读取一个对象属性 [1]',
                'GetRequestNormalList 读取若干个对象属性 [2]',
                'GetRequestRecord 读取一个记录型对象属性 [3]',
                'GetRequestRecordList 读取若干个记录型对象属性 [4]',
                'GetRequestNext 读取分帧传输的下一帧数据 [5]',
                'GetRequestMD5 读取一个对象属性的MD5值 [6]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'SET-Request' in text and 'COMPACT' not in text:  # 设置请求 (6)
            self.service_data_type_combo.addItems([
                'SetRequestNormal 设置一个对象属性 [1]',
                'SetRequestNormalList 设置若干个对象属性 [2]',
                'SetThenGetRequestNormalList 设置后读取若干个对象属性 [3]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'ACTION-Request' in text:  # 操作请求 (7)
            self.service_data_type_combo.addItems([
                'ActionRequestNormal 操作一个对象方法 [1]',
                'ActionRequestNormalList 操作若干个对象方法 [2]',
                'ActionThenGetRequestNormalList 操作后读取若干个对象属性 [3]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'REPORT-Response' in text:  # 上报应答 (8)
            self.service_data_type_combo.addItems([
                'ReportResponseRecord 上报一个记录型对象 [1]',
                'ReportResponseRecordList 上报若干个记录型对象 [2]',
                'ReportResponseTransData 上报透传的数据 [3]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'PROXY-Request' in text:  # 代理请求 (9)
            self.service_data_type_combo.addItems([
                'ProxyRequestGetList 代理读取若干个服务器的若干个对象属性 [1]',
                'ProxyRequestSetList 代理设置若干个服务器的若干个对象属性 [2]',
                'ProxyRequestActionList 代理操作若干个服务器的若干个对象方法 [3]',
                'ProxyRequestTransCommandList 代理透传若干个服务器的命令 [4]',
                'ProxyRequestGetTransData 代理读取若干个服务器的若干个透传对象 [5]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'COMPACT-GET-Request' in text:  # 简化读取请求 (133)
            self.service_data_type_combo.addItems([
                'CompactGetRequestNormal 简化读取一个对象属性 [1]'
            ])
            self.service_data_type_label.setVisible(True)
            self.service_data_type_combo.setVisible(True)
            
        elif 'COMPACT-SET-Request' in text:  # 简化设置请求 (134)
            self.service_data_type_combo.addItems([
                'CompactSetRequestNormal 简化设置一个对象属性 [1]'
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

    def create_protocol_config_panel(self):
        """创建协议配置面板（固定在左侧）"""
        # 创建配置面板容器
        self.protocol_config_panel = QWidget()
        self.protocol_config_panel.setMinimumWidth(380)  # 设置最小宽度
        # 不设置最大宽度，允许用户拖拽调整
        
        # 主容器布局
        panel_layout = QVBoxLayout(self.protocol_config_panel)
        panel_layout.setSpacing(0)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        
        # ========== 协议配置内容 ==========
        # 创建内容容器（替代原来的protocol_tab）
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)  # 减小间距从10到8
        content_layout.setContentsMargins(8, 8, 8, 8)  # 减小边距从10到8
        
        # 控制域配置组（优化布局）
        control_group = QGroupBox("控制域(CBIN)")
        control_layout = QVBoxLayout()  # 改为垂直布局
        control_layout.setSpacing(5)
        control_layout.setContentsMargins(10, 10, 10, 10)
        
        # D7传输方向
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("D7传输方向:"))
        dir_layout.addWidget(self.dir_combo, 1)
        control_layout.addLayout(dir_layout)
        
        # D6启动标志
        prm_layout = QHBoxLayout()
        prm_layout.addWidget(QLabel("D6启动标志:"))
        prm_layout.addWidget(self.prm_combo, 1)
        control_layout.addLayout(prm_layout)
        
        # D5分帧标志
        split_layout = QHBoxLayout()
        split_layout.addWidget(QLabel("D5分帧标志:"))
        split_layout.addWidget(self.split_combo, 1)
        control_layout.addLayout(split_layout)
        
        # D3数据域标志
        sc_layout = QHBoxLayout()
        sc_layout.addWidget(QLabel("D3数据域标志:"))
        sc_layout.addWidget(self.sc_combo, 1)
        control_layout.addLayout(sc_layout)
        
        # D2-D0功能码
        func_layout = QHBoxLayout()
        func_layout.addWidget(QLabel("D2-D0功能码:"))
        func_layout.addWidget(self.func_combo, 1)
        control_layout.addLayout(func_layout)
        
        control_group.setLayout(control_layout)
        content_layout.addWidget(control_group)
        
        # SA标志配置组（优化布局）
        sa_flag_group = QGroupBox("服务器地址SA标志字节(BCD)")
        sa_flag_layout = QVBoxLayout()
        sa_flag_layout.setSpacing(5)
        sa_flag_layout.setContentsMargins(10, 10, 10, 10)
        
        # D7-D6地址类型
        addr_type_layout = QHBoxLayout()
        addr_type_layout.addWidget(QLabel("D7-D6地址类型:"))
        addr_type_layout.addWidget(self.addr_type_combo, 1)
        sa_flag_layout.addLayout(addr_type_layout)
        
        # SA逻辑地址（bit4和bit5组成）
        sa_logic_layout = QHBoxLayout()
        sa_logic_layout.addWidget(QLabel("SA逻辑地址(bit4+bit5):"))
        sa_logic_layout.addWidget(self.sa_logic_addr_combo, 1)
        sa_flag_layout.addLayout(sa_logic_layout)
        
        # 扩展逻辑地址输入
        ext_logic_input_layout = QHBoxLayout()
        ext_logic_input_layout.addWidget(QLabel("扩展逻辑地址值:"))
        ext_logic_input_layout.addWidget(self.sa_ext_logic_input, 1)
        sa_flag_layout.addLayout(ext_logic_input_layout)
        
        # D3-D0地址长度
        addr_len_layout = QHBoxLayout()
        addr_len_layout.addWidget(QLabel("D3-D0地址长度:"))
        addr_len_layout.addWidget(self.addr_len_input, 1)
        sa_flag_layout.addLayout(addr_len_layout)
        
        sa_flag_group.setLayout(sa_flag_layout)
        content_layout.addWidget(sa_flag_group)
        
        # 服务器地址配置组（优化布局）
        sa_group = QGroupBox("服务器地址(SA)")
        sa_layout = QVBoxLayout()
        sa_layout.setSpacing(5)
        sa_layout.setContentsMargins(10, 10, 10, 10)
        
        # 客户机地址(CA)
        ca_layout = QHBoxLayout()
        ca_layout.addWidget(QLabel("客户机地址(CA):"))
        ca_layout.addWidget(self.logic_addr, 1)
        sa_layout.addLayout(ca_layout)
        
        # 通信地址(SA)
        comm_addr_layout = QHBoxLayout()
        comm_addr_layout.addWidget(QLabel("通信地址(SA):"))
        comm_addr_layout.addWidget(self.comm_addr, 1)
        sa_layout.addLayout(comm_addr_layout)
        
        sa_group.setLayout(sa_layout)
        content_layout.addWidget(sa_group)
        
        # APDU配置组（优化为垂直布局）
        apdu_group = QGroupBox("APDU")
        apdu_layout = QVBoxLayout()  # 改为垂直布局
        apdu_layout.setSpacing(5)
        apdu_layout.setContentsMargins(10, 10, 10, 10)
        
        # 服务类型
        service_type_layout = QHBoxLayout()
        service_type_layout.addWidget(QLabel("服务类型:"))
        service_type_layout.addWidget(self.service_type_combo, 1)
        apdu_layout.addLayout(service_type_layout)
        
        # 数据类型（根据需要显示）
        data_type_layout = QHBoxLayout()
        data_type_layout.addWidget(self.service_data_type_label)
        data_type_layout.addWidget(self.service_data_type_combo, 1)
        apdu_layout.addLayout(data_type_layout)
        
        # 服务优先级
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("服务优先级:"))
        priority_layout.addWidget(self.service_priority_combo, 1)
        apdu_layout.addLayout(priority_layout)
        
        # 服务序号
        number_layout = QHBoxLayout()
        number_layout.addWidget(QLabel("服务序号:"))
        number_layout.addWidget(self.service_number_spin, 1)
        apdu_layout.addLayout(number_layout)
        
        # OAD选择和输入（优化为垂直布局）
        apdu_layout.addWidget(QLabel("OAD:"))
        
        # 创建OAD配置组
        oad_group = QGroupBox()
        oad_layout = QVBoxLayout()  # 改为垂直布局
        oad_layout.setSpacing(5)
        oad_layout.setContentsMargins(5, 5, 5, 5)
        
        # 第一行：对象大类
        oi_class_layout = QHBoxLayout()
        oi_class_layout.addWidget(QLabel("对象大类:"))
        self.oi_class_combo = QComboBox()
        if self.oad_config and 'OI_CLASS' in self.oad_config:
            self.oi_class_combo.addItems(self.oad_config['OI_CLASS'].keys())
        self.oi_class_combo.currentTextChanged.connect(self.on_oi_class_changed)
        oi_class_layout.addWidget(self.oi_class_combo, 1)
        oad_layout.addLayout(oi_class_layout)
        
        # 第二行：OI(对象标识)
        oi_layout = QHBoxLayout()
        oi_layout.addWidget(QLabel("OI(对象标识):"))
        self.oi_subclass_combo = QComboBox()
        self.oi_subclass_combo.currentTextChanged.connect(self.update_oad_input)
        oi_layout.addWidget(self.oi_subclass_combo, 1)
        oad_layout.addLayout(oi_layout)
        
        # 第三行：属性ID
        property_layout = QHBoxLayout()
        property_layout.addWidget(QLabel("属性ID:"))
        self.property_combo = QComboBox()
        if self.oad_config and 'PROPERTY' in self.oad_config:
            self.property_combo.addItems(self.oad_config['PROPERTY'].keys())
        self.property_combo.currentTextChanged.connect(self.update_oad_input)
        property_layout.addWidget(self.property_combo, 1)
        oad_layout.addLayout(property_layout)
        
        # 第四行：索引
        index_layout = QHBoxLayout()
        index_layout.addWidget(QLabel("索引:"))
        self.index_combo = QComboBox()
        if self.oad_config and 'INDEX' in self.oad_config:
            self.index_combo.addItems(self.oad_config['INDEX'].keys())
        self.index_combo.currentTextChanged.connect(self.update_oad_input)
        index_layout.addWidget(self.index_combo, 1)
        oad_layout.addLayout(index_layout)
        
        # 第五行：OAD完整值
        oad_result_layout = QHBoxLayout()
        oad_result_layout.addWidget(QLabel("OAD完整值:"))
        self.oad_input.setStyleSheet("""
            QLineEdit {
                background-color: #e3f2fd;
                border: 2px solid #2196f3;
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        self.oad_input.setReadOnly(True)
        oad_result_layout.addWidget(self.oad_input, 1)
        oad_layout.addLayout(oad_result_layout)
        
        oad_group.setLayout(oad_layout)
        apdu_layout.addWidget(oad_group)
        
        # 初始化OI小类列表
        if self.oi_class_combo.count() > 0:
            self.on_oi_class_changed(self.oi_class_combo.currentText())
        
        # 自定义数据
        custom_data_layout = QHBoxLayout()
        custom_data_layout.addWidget(QLabel("自定义数据:"))
        custom_data_layout.addWidget(self.custom_data, 1)
        apdu_layout.addLayout(custom_data_layout)
        
        apdu_group.setLayout(apdu_layout)
        content_layout.addWidget(apdu_group)
        
        # ========== 数据构造器组件 ==========
        data_builder_group = QGroupBox("🔧 数据构造器")
        data_builder_main_layout = QVBoxLayout()
        data_builder_main_layout.setSpacing(6)  # 减小间距从8到6
        data_builder_main_layout.setContentsMargins(8, 8, 8, 8)  # 减小边距从10到8
        
        # 数据类型选择
        data_type_layout = QHBoxLayout()
        data_type_layout.setSpacing(5)  # 设置合理间距避免重叠
        type_label = QLabel("数据类型:")
        type_label.setFixedWidth(60)  # 固定标签宽度避免重叠
        data_type_layout.addWidget(type_label)
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
        self.data_type_combo.setFixedHeight(24)  # 减小高度从30到24
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_type_layout.addWidget(self.data_type_combo, 1)  # 添加伸缩因子
        data_builder_main_layout.addLayout(data_type_layout)
        
        # 动态参数输入区域（根据数据类型动态显示）
        self.param_input_widget = QWidget()
        self.param_input_layout = QVBoxLayout(self.param_input_widget)
        self.param_input_layout.setSpacing(5)
        self.param_input_layout.setContentsMargins(0, 0, 0, 0)
        data_builder_main_layout.addWidget(self.param_input_widget)
        
        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)  # 减小按钮间距
        
        # 生成数据按钮
        self.generate_data_btn = QPushButton("生成数据")
        self.generate_data_btn.setFixedHeight(28)  # 减小高度从40到28
        self.generate_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 9pt;
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
        self.add_data_btn = QPushButton("添加到自定义数据")
        self.add_data_btn.setFixedHeight(28)  # 减小高度从40到28
        self.add_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 9pt;
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
        
        data_builder_main_layout.addLayout(button_layout)
        
        # 数据显示区域
        data_display_layout = QVBoxLayout()
        data_display_layout.setSpacing(3)  # 设置标签和文本框间距
        display_label = QLabel("生成的数据:")
        display_label.setStyleSheet("font-size: 9pt;")
        data_display_layout.addWidget(display_label)
        
        self.data_display = QTextEdit()
        self.data_display.setPlaceholderText("点击'生成数据'按钮后，生成的数据将显示在此处...")
        self.data_display.setFixedHeight(70)  # 固定高度为70px，更紧凑
        self.data_display.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        data_display_layout.addWidget(self.data_display)
        data_builder_main_layout.addLayout(data_display_layout)
        
        data_builder_group.setLayout(data_builder_main_layout)
        content_layout.addWidget(data_builder_group)
        
        # 初始化时触发数据类型变化，显示默认类型的参数输入
        if self.data_type_combo.count() > 0:
            self.on_data_type_changed(self.data_type_combo.currentText())
        
        # 添加弹性空间
        content_layout.addStretch()
        
        # 使用滚动区域包裹内容容器
        scroll_area = QScrollArea()
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 确保滚动区域背景透明
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)
        
        # 将滚动区域添加到面板布局
        panel_layout.addWidget(scroll_area)

    # 以下方法不再需要，因为配置面板和日志区域已经固定在主界面中
    def minimize_config_window(self):
        """最小化配置窗口（已废弃）"""
        pass

    def toggle_maximize_config_window(self):
        """切换配置窗口最大状态（已废弃）"""
        pass
    
    def minimize_log_window(self):
        """最小化日志窗口（已废弃）"""
        pass

    def toggle_maximize_log_window(self):
        """切换日志窗口最大化状态（已废弃）"""
        pass

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

    # 主题相关方法已移除，使用PySide6原生默认风格

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
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
            ext_logic_addr_content = self.ext_logic_addr_input.text().strip()
            
            service_type = self.service_type_combo.currentText()
            service_data_type = self.service_data_type_combo.currentText()
            service_priority = self.service_priority_combo.currentText()
            service_number = self.service_number_spin.value()
            
            # 获取服务类型和数据类型的编码，用于日志显示
            service_type_code = self.service_type_codes.get(service_type, '00')
            service_data_type_code = self.service_data_type_codes.get(service_data_type, '00') if service_data_type else '00'
            
            # 在日志中显示APDU配置信息
            if service_type:
                self.append_log(f"APDU配置: 服务类型={service_type} [编码:{service_type_code}H]", "info")
                if service_data_type:
                    self.append_log(f"          数据类型={service_data_type} [编码:{service_data_type_code}H]", "info")
                self.append_log(f"          PIID=优先级{service_priority}|序号{service_number}", "info")
            
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
                    oad, custom_data, ext_logic_addr_content
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
