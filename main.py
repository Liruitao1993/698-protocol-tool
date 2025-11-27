import sys
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidgetItem, QComboBox, QCheckBox, QSpinBox, QMessageBox, QLineEdit
from PySide6.QtCore import QDateTime, QTimer
from PySide6.QtGui import QColor, QFont
from ui.main_window import MainWindow
from utils.serial_handler import SerialHandler
from utils.database_handler import DatabaseHandler
from protocol.protocol_698 import Protocol698
import re
import time
import json

class TestSystem:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()
        self.serial_handler = SerialHandler()
        self.protocol = Protocol698()
        
        # 初始化数据库连接
        self.database = DatabaseHandler("frames.db")
        
        # 设置window的protocol和database属性
        self.window.set_protocol(self.protocol)
        self.window.set_database(self.database)  # 这里会自动触发加载数据库数据
        
        self.update_port_list()
        self.setup_receive_display()
        self.init_connections()

    def setup_receive_display(self):
        """Setup the UI component for displaying received messages."""
        self.window.receive_display.clear()  # Assuming a QTextEdit or similar widget

    def init_connections(self):
        """初始化信号连接"""
        self.window.add_frame_btn.clicked.connect(self.add_new_frame)
        self.window.delete_frame_btn.clicked.connect(self.delete_selected_frames)
        # 批量发送按钮由 main_window.py 中的 send_all_frames 处理
        # self.window.send_frame_btn.clicked.connect(self.send_all_frames)  # 已移除，由UI层处理
        self.window.frame_send_requested.connect(self.send_single_frame)
        
        # 连接串口数据接收信号，直接使用 MainWindow 的处理方法
        self.serial_handler.data_received.connect(self.window.handle_received_data)
        
        # 添加串口连接信号处理
        self.window.serial_connect_requested.connect(self.handle_serial_connection)
        
    def update_port_list(self):
        """更新串口列表"""
        ports = self.serial_handler.get_available_ports()
        self.window.port_combo.clear()
        self.window.port_combo.addItems(ports)
        
    def handle_serial_connection(self, config):
        """处理串口连接请求"""
        try:
            if not config:  # 如果是空字典，表示断开连接请求
                self.serial_handler.disconnect()
                self.window.set_serial_connected(False)
            else:
                # 尝试连接
                success = self.serial_handler.connect(**config)
                if success:
                    self.window.set_serial_connected(True)
                    # 保���当前配置
                    self.window.save_serial_config()
                else:
                    QMessageBox.critical(self.window, "错误", "串口连接失败！")
                    self.window.set_serial_connected(False)
        except Exception as e:
            QMessageBox.critical(self.window, "错误", f"串口操作失败：{str(e)}")
            self.window.set_serial_connected(False)

    def add_new_frame(self):
        """添加新的数据帧"""
        try:
            # 获取控制域参数
            direction = self.window.dir_combo.currentText()
            prm = self.window.prm_combo.currentText()
            function = self.window.func_combo.currentText()
            split_frame = self.window.split_combo.currentText()
            
            # 获取SA地址标志配置
            addr_type = self.window.addr_type_combo.currentText()
            
            # 根据协议：bit4和bit5组成SA逻辑地址
            sa_logic_choice = self.window.sa_logic_addr_combo.currentText()
            
            # 确定SA逻辑地址值和bit4/bit5
            if sa_logic_choice == '0':
                # bit5=0, bit4=0 → 逻辑地址0
                sa_logic_value = 0
                bit5 = 0
                bit4 = 0
                ext_logic_len = 0
            elif sa_logic_choice == '1':
                # bit5=0, bit4=1 → 逻辑地址1
                sa_logic_value = 1
                bit5 = 0
                bit4 = 1
                ext_logic_len = 0
            else:  # '2-255(扩展)'
                # bit5=1 → 有扩展逻辑地址，地址值在2-255
                sa_ext_logic_text = self.window.sa_ext_logic_input.text().strip()
                sa_logic_value = int(sa_ext_logic_text) if sa_ext_logic_text else 2
                bit5 = 1
                bit4 = 0  # bit4备用
                ext_logic_len = 1  # 扩展逻辑地址固定1字节
            
            # 获取SA通信地址
            comm_addr = self.window.comm_addr.text()
            
            # 根据SA地址实际内容计算长度
            comm_addr_hex = comm_addr.replace(' ', '').replace('\t', '')
            sa_addr_len = len(comm_addr_hex) // 2  # SA通信地址实际字节数
            
            # D3-D0地址长度 = 扩展逻辑地址长度 + SA通信地址长度
            total_addr_len = ext_logic_len + sa_addr_len
            addr_len = str(total_addr_len)  # 转换为字符串
            
            # 更新UI显示（自动计算后的值）
            self.window.addr_len_input.setText(str(total_addr_len))
            
            # 构造SA标志字节
            addr_type_num = int(addr_type.split('(')[1].split(')')[0])  # 提取括号中的数字
            addr_len_num = int(addr_len)  # 实际字节数
            
            # 计算SA标志字节值（将实际字节转换为协议值）
            protocol_addr_len = self.protocol.ADDR_LEN_REVERSE_MAP[addr_len_num]  # 如6转换为5
            sa_flag_value = ((addr_type_num & 0x03) << 6) | \
                            ((bit5 & 0x01) << 5) | \
                            ((bit4 & 0x01) << 4) | \
                            (protocol_addr_len & 0x0F)
            
            # 构造SA标志字符串（不使用数组索引）
            addr_type_map = {0: '单地址', 1: '通配地址', 2: '组地址', 3: '广播地址'}
            addr_type_str = addr_type_map.get(addr_type_num, '未知地类型')
            sa_flag = f"{addr_type_str}-{addr_len_num}字节({sa_flag_value:02X})"
            
            # 在控制台输出SA地址配置信息
            print(f"SA地址配置:")
            print(f"  SA标志字节: {sa_flag_value:02X}H")
            print(f"  SA逻辑地址: {sa_logic_value} (bit5={bit5}, bit4={bit4})")
            print(f"  SA通信地址实际长度: {sa_addr_len}字节 (根据输入内容计算)")
            if bit5:
                print(f"  扩展逻辑地址: 启用 (固定1字节, 值={sa_logic_value})")
                print(f"  D3-D0地址长度字段: {total_addr_len}字节 = 扩展逻辑1 + SA通信{sa_addr_len}")
                print(f"  帧中地址总长度: {1 + sa_addr_len}字节 (扩展逻辑1 + SA通信{sa_addr_len})")
            else:
                print(f"  扩展逻辑地址: 未启用")
                print(f"  D3-D0地址长度字段: {total_addr_len}字节 = SA通信{sa_addr_len}")
                print(f"  帧中地址总长度: {sa_addr_len}字节")
            
            # 获取其他参数
            logic_addr = self.window.logic_addr.text()
            comm_addr = self.window.comm_addr.text()
            oad = self.window.oad_input.text()
            
            # 验证必填字段
            required_fields = [logic_addr, comm_addr, oad]
            
            if not all(required_fields):
                print("错误：所有必填字段都必须填写")
                return
            
            # 获取APDU配置
            service_type = self.window.service_type_combo.currentText()
            service_data_type = self.window.service_data_type_combo.currentText()
            service_priority = self.window.service_priority_combo.currentText()
            service_number = self.window.service_number_spin.value()
            
            # 获取OAD值（直接从输入框获取）
            oad = self.window.oad_input.text().strip()
            if not oad:
                oad = "40000201"  # 默认OAD值
            
            # 获取自定义报文内容
            custom_data = self.window.custom_data.text()
            
            # 生成帧名称：根据APDU服务类型和OI对象名称
            frame_name = self.generate_frame_name(service_type, oad)
            
            # 创建帧
            frame = self.protocol.create_frame(
                direction=direction,
                prm=prm,
                function=function,
                split_frame=split_frame,
                addr_type=addr_type,
                addr_len=addr_len,
                sa_logic_value=sa_logic_value,
                bit5=bit5,
                logic_addr=logic_addr,
                comm_addr=comm_addr,
                service_type=service_type,
                service_data_type=service_data_type,
                service_priority=service_priority,
                service_number=service_number,
                oad=oad,
                custom_data=custom_data
            )
            
            # 将帧保存到协议对象中
            self.protocol.save_frame(frame_name, frame)
            
            # 保存到数据库
            frame_id = self.database.add_frame(
                name=frame_name,
                frame_content=frame.hex(),
                status="就绪",
                match_enabled=False,
                match_rule="",
                match_mode="HEX",
                test_result="",
                timeout_ms=self.window.default_timeout.value()
            )
            
            # 添加新行
            row = self.window.frame_table.rowCount()
            self.window.frame_table.insertRow(row)
            
            # 设置序号
            self.window.frame_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # 设置名称和帧内容
            self.window.frame_table.setItem(row, 1, QTableWidgetItem(frame_name))
            self.window.frame_table.setItem(row, 2, QTableWidgetItem(frame.hex()))
            
            # 添加发送按钮
            send_btn = QPushButton("单帧发送")
            send_btn.setFont(QFont("黑体", 9))  # 减小字体
            send_btn.setFixedWidth(90)  # 减小宽度从130到90
            send_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 4px;
                    padding: 4px 8px;  /* 减小内边距 */
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            send_btn.clicked.connect(lambda checked, name=frame_name, r=row: self.send_single_frame(name, r))
            self.window.frame_table.setCellWidget(row, 3, send_btn)
            
            # 设置状态
            self.window.frame_table.setItem(row, 4, QTableWidgetItem("就绪"))
            
            # 添加匹配启用复选框
            match_checkbox = QCheckBox()
            match_checkbox.setChecked(False)  # 默认不启用
            self.window.frame_table.setCellWidget(row, 5, match_checkbox)
            
            # 添加匹配规则入框
            rule_item = QTableWidgetItem("")
            rule_item.setToolTip("使用XX表示任意字节，如: 68XXXX16")
            self.window.frame_table.setItem(row, 6, rule_item)
            
            # 添加匹配模式选择
            mode_combo = QComboBox()
            mode_combo.addItems(["HEX", "ASCII"])
            self.window.frame_table.setCellWidget(row, 7, mode_combo)
            
            # 添加测试结果列
            result_item = QTableWidgetItem("")
            self.window.frame_table.setItem(row, 8, result_item)
            
            # 添加超时设置
            timeout_spinbox = QSpinBox()
            timeout_spinbox.setRange(0, 60000)
            timeout_spinbox.setValue(self.window.default_timeout.value())
            self.window.frame_table.setCellWidget(row, 9, timeout_spinbox)
            
            # 自动调整列宽
            self.window.frame_table.resizeColumnsToContents()
            # 设置操作列固定宽度
            self.window.frame_table.setColumnWidth(3, 110)
            
            # 在接收显示区域显示帧内容
            self.window.receive_display.append(f"新建帧 {frame_name}:")
            self.window.receive_display.append(f"帧内容: {frame.hex()}")
            self.window.receive_display.append("------------------------")
            
            # 显示数据库保存成功信息
            self.window.append_log(f"✓ 新帧已保存到数据库 (ID: {frame_id})", "success")
            
        except Exception as e:
            print(f"添加帧错误: {e}")
            # 在接收显示区域显示错误信息
            self.window.receive_display.append(f"添加帧错误: {str(e)}")

    def generate_frame_name(self, service_type, oad):
        """
        生成帧名称：APDU服务类型_OI对象名称
        如果名称重复，添加递增序号
        """
        # 提取APDU服务类型的中文名称
        service_name = self.extract_service_name(service_type)
        
        # 根据OAD获取OI对象名称
        oi_name = self.get_oi_name_from_oad(oad)
        
        # 组合基本名称
        base_name = f"{service_name}_{oi_name}"
        
        # 检查是否重复，如果重复则添加序号
        frame_name = base_name
        counter = 2
        existing_names = []
        
        # 获取所有现有帧名称
        for row in range(self.window.frame_table.rowCount()):
            item = self.window.frame_table.item(row, 1)
            if item:
                existing_names.append(item.text())
        
        # 如果名称已存在，添加递增序号
        while frame_name in existing_names:
            frame_name = f"{base_name}_{counter}"
            counter += 1
        
        return frame_name
    
    def extract_service_name(self, service_type):
        """提取APDU服务类型的中文名称"""
        # 如果包含英文和编码，提取中文部分
        # 例: "GET-Request 读取请求 (5)" -> "读取请求"
        if ' ' in service_type:
            parts = service_type.split(' ')
            # 找到中文部分（不包含括号的部分）
            for part in parts:
                if part and not part.startswith('(') and not part.endswith(')'):
                    # 判断是否包含中文字符
                    if any('\u4e00' <= c <= '\u9fff' for c in part):
                        return part
        # 如果没有空格或找不到中文，直接返回
        return service_type
    
    def get_oi_name_from_oad(self, oad):
        """根据OAD获取OI对象名称"""
        # 加载OAD配置
        try:
            with open('config/oad_config.json', 'r', encoding='utf-8') as f:
                oad_config = json.load(f)
            
            # 先在预定义OAD中查找
            if 'OAD' in oad_config:
                for name, value in oad_config['OAD'].items():
                    if value.upper() == oad.upper():
                        # 提取名称部分（去除OAD编码）
                        # 例: "40000200-日期时间" -> "日期时间"
                        if '-' in name:
                            return name.split('-', 1)[1]
                        return name
            
            # 如果没有找到，尝试解析OAD结构：OI(2字节) + 属性(1字节) + 索引(1字节)
            if len(oad) == 8:
                oi = oad[0:4].upper()
                
                # 在OI_SUBCLASS中查找
                if 'OI_SUBCLASS' in oad_config:
                    for class_name, subclasses in oad_config['OI_SUBCLASS'].items():
                        for sub_name, sub_value in subclasses.items():
                            if sub_value.upper() == oi:
                                # 提取名称部分
                                if '-' in sub_name:
                                    return sub_name.split('-', 1)[1]
                                return sub_name
            
            # 如果都没有找到，返回OAD值
            return f"OAD_{oad}"

        except Exception as e:
            print(f"读取OAD配置失败: {e}")
            return f"OAD_{oad}"

    def handle_window_close(self, event):
        """处理窗关闭事件"""
        self.serial_handler.disconnect()  # 断开串口连接
        event.accept()
        
    def run(self):
        self.window.show()
        self.window.closeEvent = self.handle_window_close
        return self.app.exec_()

    def display_received_message(self, message):
        """Display received message in hex format"""
        try:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
            
            # 使用window的append_log方法
            self.window.append_log(f"""
            <div style='background-color: #e8f5e9; padding: 5px; margin: 2px;'>
                <span style='color: #666;'>[{timestamp}]</span>
                <span style='color: #2e7d32;'>RX:</span> 
                <span style='font-family: Consolas, monospace;'>{message}</span>
            </div>
            """, "info")
            
            # 将接收��的消息换为字节
            received_bytes = bytes.fromhex(message)
            
            # 如果正在等待响应，检查是否是当前行的匹配
            if hasattr(self, 'waiting_for_response') and self.waiting_for_response:
                # 取消超时定时器
                if hasattr(self, 'timeout_timer'):
                    self.timeout_timer.stop()
                    self.timeout_timer.deleteLater()
                    delattr(self, 'timeout_timer')
                
                row = self.current_send_row
                
                # 获取匹配启用状态
                match_checkbox = self.window.frame_table.cellWidget(row, 5)
                if match_checkbox and match_checkbox.isChecked():
                    # 获取匹配规则 - 第6列可能是QLineEdit(Widget)或QTableWidgetItem(Item)
                    match_rule_widget = self.window.frame_table.cellWidget(row, 6)
                    rule = ""
                    if isinstance(match_rule_widget, QLineEdit):
                        # 如果是QLineEdit，直接获取文本
                        rule = match_rule_widget.text().strip()
                    else:
                        # 如果是QTableWidgetItem，使用item方法
                        rule_item = self.window.frame_table.item(row, 6)
                        if rule_item:
                            rule = rule_item.text().strip()
                    
                    if rule:
                        # 获取匹配模式
                        mode_combo = self.window.frame_table.cellWidget(row, 7)
                        if mode_combo:
                            # 执行匹配
                            match_mode = mode_combo.currentText()
                            match_result = self.match_data(received_bytes, rule, match_mode)
                            
                            # 更新测试结果
                            result_item = self.window.frame_table.item(row, 8)
                            if not result_item:
                                result_item = QTableWidgetItem()
                                self.window.frame_table.setItem(row, 8, result_item)
                            
                            # 取帧名称
                            frame_name = self.window.frame_table.item(row, 1).text()
                            
                            # 显示匹配结果
                            self.display_match_result(match_result, row, frame_name, result_item)
                
                # 标记响应已处理
                self.waiting_for_response = False
                
                # 只有在执行"发送"按钮（发送所有帧）时才继续发送下一帧
                if hasattr(self, 'sending_all_frames') and self.sending_all_frames:
                    self.current_send_row += 1
                    self.send_next_frame()
                
        except Exception as e:
            self.window.append_log(f"处理接收数据错误: {str(e)}", "error")

    def match_data(self, data, rule, mode):
        """
        匹配数据并返回详细的匹配结果
        data: 接收到的数据
        rule: 匹配规则
        mode: 匹配模式 (HEX/ASCII)
        """
        try:
            if mode == "HEX":
                # 数据转换为六进制字符串
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

    def delete_selected_frames(self):
        """删除选中的帧"""
        selected_rows = set(item.row() for item in self.window.frame_table.selectedItems())
        if not selected_rows:
            return
        
        # 获取要删除的帧名称和数据库ID
        frames_to_delete = []
        for row in sorted(selected_rows, reverse=True):
            frame_name = self.window.frame_table.item(row, 1).text()
            frames_to_delete.append((row, frame_name))
        
        # 从数据库删除
        frame_ids_to_delete = []
        for row, frame_name in frames_to_delete:
            # 查找对应的数据库ID（这里简化处理，实际应用中可能需要维护ID映射）
            # 为了简化，我们直接使用帧名称来查找
            frames = self.database.get_all_frames()
            for frame in frames:
                if frame['name'] == frame_name:
                    frame_ids_to_delete.append(frame['id'])
                    break
        
        # 从数据库删除
        if frame_ids_to_delete:
            deleted_count = self.database.delete_frames(frame_ids_to_delete)
            self.window.append_log(f"✓ 已从数据库删除 {deleted_count} 个帧", "success")
        
        # 从UI和协议对象中删除
        for row, frame_name in reversed(frames_to_delete):
            self.window.frame_table.removeRow(row)
            # 从协议对象中删除帧
            if hasattr(self.protocol, 'frames'):
                self.protocol.frames.pop(frame_name, None)
        
        # 重新编号
        self.renumber_frames()

    def renumber_frames(self):
        """重新为所有帧编号"""
        for row in range(self.window.frame_table.rowCount()):
            self.window.frame_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def send_all_frames(self):
        """按序号顺序发送所有帧"""
        self.current_send_row = 0
        self.current_frame_start_time = None
        self.waiting_for_response = False
        self.sending_all_frames = True  # 添加标志位
        self.send_next_frame()

    def send_next_frame(self):
        """发送下一个帧"""
        if self.current_send_row >= self.window.frame_table.rowCount():
            return
        
        try:
            # 获取当前行的帧名称和超时设置
            frame_name_item = self.window.frame_table.item(self.current_send_row, 1)
            if not frame_name_item:
                self.window.append_log(f"""
                <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                    <span style='color: #721c24;'>错误: 行 {self.current_send_row + 1} 的帧名称为空</span>
                </div>
                """)
                # 移动到下一行
                self.current_send_row += 1
                self.send_next_frame()
                return
            
            frame_name = frame_name_item.text()
            frame = self.protocol.get_frame(frame_name)
            if not frame:
                self.window.append_log(f"""
                <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                    <span style='color: #721c24;'>错误: 找不到帧 "{frame_name}" 的数据</span>
                </div>
                """)
                # 移动到下一行
                self.current_send_row += 1
                self.send_next_frame()
                return
            
            # 获取超时设置
            timeout_spinbox = self.window.frame_table.cellWidget(self.current_send_row, 9)
            self.current_timeout = timeout_spinbox.value() if timeout_spinbox else self.window.default_timeout.value()
            
            # 记录开始时间
            self.current_frame_start_time = time.time()
            self.waiting_for_response = True
            
            # 发送帧
            self.serial_handler.send_frame(frame)
            
            # 记录发送信息
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz")
            self.window.append_log(f"""
            <div style='background-color: #e8f5e9; padding: 5px; margin: 2px;'>
                <span style='color: #666;'>[{timestamp}]</span>
                <span style='color: #2e7d32;'>TX:</span> 
                <span style='font-family: Consolas, monospace;'>{frame.hex()}</span>
                <br>
                <span style='color: #666;'>帧名称: {frame_name}</span>
                <span style='color: #666;'>行号: {self.current_send_row + 1}</span>
            </div>
            """)
            
            # 清理旧定时器（如果存在）
            if hasattr(self, 'timeout_timer') and self.timeout_timer:
                try:
                    self.timeout_timer.stop()
                    self.timeout_timer.timeout.disconnect()  # 断开信号
                    self.timeout_timer.deleteLater()
                except:
                    pass
                self.timeout_timer = None
            
            # 创建新的超时检查定时器
            self.timeout_timer = QTimer(self.window)
            self.timeout_timer.setSingleShot(True)
            self.timeout_timer.timeout.connect(self.check_frame_timeout)
            self.timeout_timer.start(self.current_timeout)
            
        except Exception as e:
            self.window.receive_display.append(f"""
            <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                <span style='color: #721c24;'>发送帧错误: {str(e)}</span>
            </div>
            """)
            # 移动到下一行
            self.current_send_row += 1
            self.send_next_frame()

    def check_frame_timeout(self):
        """检查当前帧是否超时"""
        try:
            # 如果已经收到响应，不处理超时
            if not self.waiting_for_response:
                return
            
            # 获取帧名称
            frame_name = self.window.frame_table.item(self.current_send_row, 1).text()
            
            # 更新测试结果为"超时"
            result_item = self.window.frame_table.item(self.current_send_row, 8)
            if not result_item:
                result_item = QTableWidgetItem()
                self.window.frame_table.setItem(self.current_send_row, 8, result_item)
            result_item.setText("超时")
            result_item.setBackground(QColor("#FFA500"))  # 橙色背景
            
            # 显示超时信息
            self.window.append_log(f"""
            <div style='background-color: #fff3cd; padding: 5px; margin: 2px;'>
                <span style='color: #856404;'>⚠ 帧 {self.current_send_row + 1} ({frame_name}) 执行超时</span>
                <br>
                <span style='color: #856404;'>超时时间: {self.current_timeout}ms</span>
            </div>
            """, "warning")
            
            # 重置状态
            self.waiting_for_response = False
            
            # 清理定时器
            if hasattr(self, 'timeout_timer') and self.timeout_timer:
                self.timeout_timer = None
            
            # 如果是发送所有帧模式，继续发送下一帧
            if hasattr(self, 'sending_all_frames') and self.sending_all_frames:
                self.current_send_row += 1
                self.send_next_frame()
            
        except Exception as e:
            self.window.append_log(f"超时检查错误: {str(e)}", "error")

    def send_single_frame(self, frame_name, row):
        """发送单个帧并检查匹配规则"""
        if self.serial_handler.is_connected():
            try:
                # 获取帧数据
                frame = self.protocol.get_frame(frame_name)
                if not frame:
                    self.window.append_log(f"错误: 找不到帧 {frame_name} 的数据", "error")
                    return
                
                # 获取超时设置
                timeout_spinbox = self.window.frame_table.cellWidget(row, 9)
                timeout = timeout_spinbox.value() if timeout_spinbox else 1000
                
                # 发送帧并等待响应
                success, response = self.serial_handler.send_frame(frame, timeout)
                
                if success and response:
                    # 解析响应帧
                    parsed_response = self.protocol.parse_frame(response)
                    if parsed_response:
                        # 显示解析后的响应
                        self.window.append_log(f"<span style='color: #155724;'>Receive: {response.hex(' ')}</span>", "info")
                        self.window.append_log(f"<span style='color: #155724;'>解析响应: {parsed_response}</span>", "info")
                    else:
                        self.window.append_log(f"错误: 无法解析响应帧 {response.hex()}", "error")
                        
                    # 更新状态列
                    status_item = QTableWidgetItem("已发送")
                    self.window.frame_table.setItem(row, 4, status_item)
                    
                    # 检查匹配规则
                    match_checkbox = self.window.frame_table.cellWidget(row, 5)
                    if match_checkbox and match_checkbox.isChecked():
                        # 启用了匹配，需要根据匹配结果决定是否合格
                        # 第6列可能是QLineEdit(Widget)或QTableWidgetItem(Item)
                        match_rule_widget = self.window.frame_table.cellWidget(row, 6)
                        if isinstance(match_rule_widget, QLineEdit):
                            # 如果是QLineEdit，直接获取文本
                            match_rule = match_rule_widget.text()
                        else:
                            # 如果是QTableWidgetItem，使用item方法
                            match_rule_item = self.window.frame_table.item(row, 6)
                            if match_rule_item:
                                match_rule = match_rule_item.text()
                            else:
                                match_rule = ""
                        
                        match_mode_combo = self.window.frame_table.cellWidget(row, 7)
                        match_mode = match_mode_combo.currentText() if match_mode_combo else "HEX"
                        
                        # 使用 MainWindow 的 match_data 方法进行匹配
                        print(f"response  ={response.hex()}")
                        print(f"match_rule={match_rule}")
                        self.window.append_log(f"response  ={response.hex()}", "info")
                        self.window.append_log(f"match_rule={match_rule}", "info")
                        
                        match_result = self.window.match_data(response, match_rule, match_mode)
                        print(f"{match_result}")
                        self.window.append_log(f"{match_result}", "info")
                        
                        # 更新测试结果
                        result_item = QTableWidgetItem()
                        self.window.frame_table.setItem(row, 8, result_item)
                        
                        try:
                            # 显示匹配结果
                            self.window.display_match_result(match_result, row, frame_name, result_item, match_rule)
                            if not match_result['match']:
                                self.display_mismatch_details(match_result, row, frame_name, result_item)
                        except Exception as e:
                            self.window.append_log(f"显示匹配结果时出错: {e}", "error")
                    else:
                        # 未启用匹配，只要收到响应就是PASS
                        result_item = QTableWidgetItem("PASS")
                        result_item.setBackground(QColor("#90EE90"))  # 浅绿色背景
                        self.window.frame_table.setItem(row, 8, result_item)
                        
                        # 显示成功信息
                        self.window.append_log(f"✓ 帧 {frame_name} 测试通过（收到响应）", "success")
                    
                else:
                    # 发送失败或超时
                    status_item = QTableWidgetItem("发送失败")
                    self.window.frame_table.setItem(row, 4, status_item)
                    result_item = QTableWidgetItem("超时无响应")
                    result_item.setBackground(QColor("#fff3cd"))
                    self.window.frame_table.setItem(row, 8, result_item)
                    
            except Exception as e:
                self.window.append_log(f"发送帧失败: {e}", "error")
        else:
            QMessageBox.warning(self.window, "错误", "请先连接串口！")

    def display_match_result(self, match_result, row, frame_name, result_item):
        """显示匹配结果"""
        if match_result['match']:
            result_item.setText("PASS")
            result_item.setBackground(QColor("#90EE90"))
            self.window.receive_display.append(f"""
            <div style='background-color: #d4edda; padding: 5px; margin: 2px;'>
                <span style='color: #155724;'>帧 {row + 1} ({frame_name}) 匹配成功</span>
            </div>
            """)
        else:
            if 'mismatches' in match_result:
                self.display_mismatch_details(match_result, row, frame_name, result_item)
            else:
                error_msg = match_result.get('error', '未知错误')
                result_item.setText("FAIL")
                result_item.setBackground(QColor("#FFB6C1"))
                self.window.receive_display.append(f"""
                <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
                    <span style='color: #721c24;'>✗ 错误: {error_msg}</span>
                </div>
                """)

    def display_mismatch_details(self, match_result, row, frame_name, result_item):
        """显示不匹配的详细信息"""
        error_msg = "FAIL\n"
        data = match_result['data']
        mismatches = match_result['mismatches']
        
        # 在接收显示区域显示详细的不匹配信息
        mismatch_info = f"帧 {row + 1} ({frame_name}) 匹配失败:\n"
        for pos, rule_byte, data_byte in mismatches:
            mismatch_info += f"位置 {pos}: 期望={rule_byte}, 实际={data_byte}\n"
        
        # 在接收显示区域中显示带颜色标记的数据
        colored_data = ""
        last_pos = 0
        for pos, rule_byte, data_byte in mismatches:
            pos_start = pos * 2
            colored_data += data[last_pos:pos_start]
            colored_data += f'<span style="color: red;">{data[pos_start:pos_start+2]}</span>'
            last_pos = pos_start + 2
        colored_data += data[last_pos:]
        
        # 设置测试结果
        result_item.setText("FAIL")
        result_item.setBackground(QColor("#FFB6C1"))
        
        # 显示错误信息
        self.window.receive_display.append(f"""
        <div style='background-color: #f8d7da; padding: 5px; margin: 2px;'>
            <span style='color: #721c24;'>✗ 帧 {row + 1} ({frame_name}) 匹配失败:</span>
            <pre style='margin: 5px 0;'color: #721c24;'>{mismatch_info}</pre>
            <div style='font-family: monospace;'>数据对比: {colored_data}</div>
        </div>
        """)
        
        # 添加分隔线
        self.window.receive_display.append("""
        <div style='border-bottom: 1px solid #dee2e6; margin: 10px 0;'>
            <span style='color: #6c757d;'>------------------------</span>
        </div>
        """)

    def handle_timeout(self, row, frame_name):
        """处理超时事件"""
        if not self.waiting_for_response:
            return
        
        # 更新测试结果为"超时"
        result_item = self.window.frame_table.item(row, 8)
        if not result_item:
            result_item = QTableWidgetItem()
            self.window.frame_table.setItem(row, 8, result_item)
        result_item.setText("超时")
        result_item.setBackground(QColor("#FFA500"))  # 橙色背景
        
        # 显示超时信息
        self.window.receive_display.append(f"""
        <div style='background-color: #fff3cd; padding: 5px; margin: 2px;'>
            <span style='color: #856404;'>⚠ 帧 {row + 1} ({frame_name}) 执行超时</span>
            <br>
            <span style='color: #856404;'>超时时间: {self.current_timeout}ms</span>
        </div>
        <div style='border-bottom: 1px solid #dee2e6; margin: 10px 0;'>
            <span style='color: #6c757d;'>------------------------</span>
        </div>
        """)
        
        # 重置状态
        self.waiting_for_response = False
        
        # 如果是发送所有帧模式，继续发送下一帧
        if hasattr(self, 'sending_all_frames') and self.sending_all_frames:
            self.current_send_row += 1
            self.send_next_frame()

if __name__ == "__main__":
    system = TestSystem()
    sys.exit(system.run())