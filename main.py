import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QTableWidgetItem, QComboBox, QCheckBox, QSpinBox, QMessageBox
from PyQt5.QtCore import QDateTime, QTimer
from PyQt5.QtGui import QColor, QFont
from ui.main_window import MainWindow
from utils.serial_handler import SerialHandler
from protocol.protocol_698 import Protocol698
import re
import time

class TestSystem:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()
        self.serial_handler = SerialHandler()
        self.protocol = Protocol698()
        
        # 设置window的protocol属性
        self.window.set_protocol(self.protocol)
        
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
        self.window.send_frame_btn.clicked.connect(self.send_all_frames)
        self.window.frame_send_requested.connect(lambda x: self.send_single_frame(x[0], x[1]))
        
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
            # 获取控制域配置
            direction = self.window.dir_combo.currentText()
            prm = self.window.prm_combo.currentText()
            function = self.window.func_combo.currentText()
            split_frame = self.window.split_combo.currentText()
            
            # 获取SA地址标志配置
            addr_type = self.window.addr_type_combo.currentText()
            addr_len = self.window.addr_len_input.text()  # 接获取输入的数字
            ext_logic_addr = self.window.ext_logic_addr_combo.currentText()
            logic_addr_flag = self.window.logic_addr_flag_combo.currentText()
            
            # 确保通信地址长度正确
            comm_addr = self.window.comm_addr.text()
            if len(comm_addr) < int(addr_len) * 2:
                comm_addr = comm_addr.zfill(int(addr_len) * 2)
                self.window.comm_addr.setText(comm_addr)
            
            # 构造SA标志字节
            addr_type_num = int(addr_type.split('(')[1].split(')')[0])  # 提取括号中的数字
            addr_len_num = int(addr_len)  # 实际字节数
            ext_logic_flag = int(ext_logic_addr.split('(')[1].split(')')[0])  # 0或1
            logic_flag = int(logic_addr_flag.split('(')[1].split(')')[0])     # 0或1
            
            # 计算SA标志字节值（将实际字节转换为协议值）
            protocol_addr_len = self.protocol.ADDR_LEN_REVERSE_MAP[addr_len_num]  # 如6转换为5
            sa_flag_value = ((addr_type_num & 0x03) << 6) | \
                            ((ext_logic_flag & 0x01) << 5) | \
                            ((logic_flag & 0x01) << 4) | \
                            (protocol_addr_len & 0x0F)
            
            # 构造SA标志字符串（不使用数组索引）
            addr_type_map = {0: '单地址', 1: '通配地址', 2: '组地址', 3: '广播地址'}
            addr_type_str = addr_type_map.get(addr_type_num, '未知地型')
            sa_flag = f"{addr_type_str}-{addr_len_num}字节({sa_flag_value:02X})"
            
            # 获取其他参数
            logic_addr = self.window.logic_addr.text()
            comm_addr = self.window.comm_addr.text()
            sa_logic_addr = self.window.sa_logic_addr.text()
            oad = self.window.oad_input.text()
            
            # 验证必填字段
            required_fields = [logic_addr, comm_addr, oad]
            # 有在有逻辑地址标志时才验证sa_logic_addr
            if logic_addr_flag == '有逻辑地址(1)':
                required_fields.append(sa_logic_addr)
            
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
            
            # 获取定义报文内容
            custom_data = self.window.custom_data.text()
            
            # 获取当前行数并创建帧名称
            row = self.window.frame_table.rowCount()
            frame_name = f"Frame_{row + 1}"
            
            # 创建帧
            frame = self.protocol.create_frame(
                direction=direction,
                prm=prm,
                function=function,
                split_frame=split_frame,
                addr_type=addr_type,
                addr_len=addr_len,
                sa_logic_addr=sa_logic_addr,
                logic_addr=logic_addr,
                comm_addr=comm_addr,
                ext_logic_addr=ext_logic_addr,
                logic_addr_flag=logic_addr_flag,
                service_type=service_type,
                service_data_type=service_data_type,
                service_priority=service_priority,
                service_number=service_number,
                oad=oad,
                custom_data=custom_data
            )
            
            # 将帧保存到协议对象中
            self.protocol.save_frame(frame_name, frame)
            
            # 添加新行
            self.window.frame_table.insertRow(row)
            
            # 设置序号
            self.window.frame_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # 设置名称和帧内容
            self.window.frame_table.setItem(row, 1, QTableWidgetItem(frame_name))
            self.window.frame_table.setItem(row, 2, QTableWidgetItem(frame.hex()))
            
            # 添加发送按钮
            send_btn = QPushButton("单帧发送")
            send_btn.setFont(QFont("黑体", weight=QFont.Bold))
            send_btn.setFixedWidth(130)  # 设置固定宽度
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
            send_btn.clicked.connect(lambda checked, name=frame_name: self.send_single_frame(name, row))
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
            operation_column_width = self.window.frame_table.columnWidth(3)
            self.window.frame_table.setColumnWidth(3, int(operation_column_width * 1.5))
            
            # 在接收显示区域显示帧内容
            self.window.receive_display.append(f"新建帧 {frame_name}:")
            self.window.receive_display.append(f"帧内容: {frame.hex()}")
            self.window.receive_display.append("------------------------")
            
        except Exception as e:
            print(f"添加帧错误: {e}")
            # 在接收显示区域显示错误信息
            self.window.receive_display.append(f"添加帧错误: {str(e)}")

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
                    # 获取匹配规则
                    rule_item = self.window.frame_table.item(row, 6)
                    if rule_item and rule_item.text().strip():
                        # 获取匹配模式
                        mode_combo = self.window.frame_table.cellWidget(row, 7)
                        if mode_combo:
                            # 执行匹配
                            match_mode = mode_combo.currentText()
                            rule = rule_item.text().strip()
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
        
        for row in sorted(selected_rows, reverse=True):
            frame_name = self.window.frame_table.item(row, 1).text()
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
                    # 更新状态列
                    status_item = QTableWidgetItem("已发送")
                    self.window.frame_table.setItem(row, 4, status_item)
                    
                    # 检查匹配规则
                    match_checkbox = self.window.frame_table.cellWidget(row, 5)
                    if match_checkbox and match_checkbox.isChecked():
                        match_rule = self.window.frame_table.cellWidget(row, 6).text()
                        match_mode = self.window.frame_table.cellWidget(row, 7).currentText()
                        
                        # 使用 MainWindow 的 match_data 方法进行匹配
                        match_result = self.window.match_data(response, match_rule, match_mode)
                        
                        # 更新测试结果
                        result_item = QTableWidgetItem()
                        self.window.frame_table.setItem(row, 8, result_item)
                        
                        # 显示匹配结果
                        self.window.display_match_result(match_result, row, frame_name, result_item)
                    
                else:
                    # 发送失败或超时
                    status_item = QTableWidgetItem("发送失败")
                    self.window.frame_table.setItem(row, 4, status_item)
                    result_item = QTableWidgetItem("超时无响应")
                    result_item.setBackground(QColor("#fff3cd"))
                    self.window.frame_table.setItem(row, 8, result_item)
                    
            except Exception as e:
                self.window.append_log(f"发送帧失败: {str(e)}", "error")
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
            <pre style='margin: 5px 0;'>{mismatch_info}</pre>
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