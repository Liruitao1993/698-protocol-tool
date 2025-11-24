from PyQt5.QtCore import QObject, pyqtSignal
import threading
import time
import serial
import serial.tools.list_ports
import traceback  # 添加这个导入
from func_timeout import func_set_timeout, FunctionTimedOut

class SerialHandler(QObject):
    data_received = pyqtSignal(str)  # Define the signal for received data

    def __init__(self):
        super().__init__()  # Initialize the QObject parent class
        self.serial = None
        self.stop_receive_thread = False  # 新增标志位
        self._is_connected = False  # 添加连接状态标志
        
    def get_available_ports(self):
        """获取可用串口列表"""
        return [port.device for port in serial.tools.list_ports.comports()]
    
    def connect(self, port, baudrate, parity='N', bytesize=8, stopbits=1):
        """连接串口"""
        try:
            print("\n=== 开始连接串口 ===")
            print(f"调用来源:\n{traceback.format_stack()[-2]}")
            print(f"参数: port={port}, baudrate={baudrate}, parity={parity}, bytesize={bytesize}, stopbits={stopbits}")
            
            # 如果已经连接到相同的串口，直接返回True
            if (self.is_connected() and 
                self.serial.port == port and 
                self.serial.baudrate == baudrate and 
                self.serial.parity == parity and 
                self.serial.bytesize == bytesize and 
                self.serial.stopbits == stopbits):
                print("已经连接到指定串口，保持连接")
                return True
            
            # 如果已经连接到不同的串口，先断开
            if self.is_connected():
                print("检测到不同配置的串口连接，需要重新连接")
                self.disconnect()
            
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=parity,
                bytesize=bytesize,
                stopbits=stopbits,
                timeout=1
            )
            
            # 验证串口是否真正打开
            if not self.serial.is_open:
                self.serial.open()
            
            print(f"串口已成功打开: {self.serial.port}")
            self.stop_receive_thread = False
            self.start_receive_thread()
            self._is_connected = True
            print("=== 串口连接完成 ===\n")
            return True
            
        except Exception as e:
            print("\n=== 串口连接错误 ===")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {str(e)}")
            print(f"调用堆栈:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            self.serial = None
            return False
    
    def disconnect(self):
        """断开串口连接"""
        try:
            print("\n=== 开始断开串口 ===")
            print(f"调用来源:\n{traceback.format_stack()[-2]}")
            if self.serial:
                if self.serial.is_open:
                    self.stop_receive_thread = True
                    time.sleep(0.1)
                    self.serial.close()
                    print("串口已关闭")
                self.serial = None
            self._is_connected = False
            print("=== 串口断开完成 ===\n")
        except Exception as e:
            print("\n=== 断开串口错误 ===")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {str(e)}")
            print(f"调用堆栈:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            self.serial = None
    
    def is_connected(self):
        """检查串口是否已连接"""
        try:
            is_connected = (self.serial is not None and 
                           self.serial.is_open and 
                           self._is_connected)
            print(f"检查串口连接状态: {is_connected}")
            if not is_connected:
                print(f"串口对象: {self.serial}")
                print(f"串口打开状态: {self.serial.is_open if self.serial else 'N/A'}")
                print(f"连接标志: {self._is_connected}")
            return is_connected
        except Exception as e:
            print("\n=== 检查串口状态错误 ===")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {str(e)}")
            print(f"调用堆栈:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            return False
    
    def send_frame(self, frame_data, timeout=1000):
        """发送数据帧并等待响应"""
        if not self.is_connected():
            print("串口未连接，无法发送数据")
            return False, None
        
        try:
            print(f"正在发送数据: {frame_data.hex()}")
            self.serial.write(frame_data)
            self.data_received.emit(f"发送: {frame_data.hex()}")  # 发送日志
            print("数据发送成功，等待响应...")
            
            try:
                # 使用超时装饰器接收响应
                response = self.receive_with_timeout(timeout)
                if response:
                    print(f"收到响应: {response.hex()}")
                    self.data_received.emit(f"接收: {response.hex()}")  # 发送日志
                    return True, response
                else:
                    print("接收超时")
                    self.data_received.emit("接收超时")  # 发送日志
                    return False, None
                    
            except FunctionTimedOut:
                print("接收超时")
                self.data_received.emit("接收超时")  # 发送日志
                return False, None
                
        except Exception as e:
            print(f"发送数据错误: {e}")
            self.data_received.emit(f"发送错误: {str(e)}")  # 发送日志
            self._is_connected = False
            return False, None

    @func_set_timeout(10)  # 默认10秒超时
    def receive_with_timeout(self, timeout):
        """带超时的接收数据"""
        start_time = time.time()
        received_data = bytearray()
        
        try:
            while (time.time() - start_time) < timeout/1000:  # 转换为秒
                if self.serial and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting)
                    received_data.extend(data)
                    # 发送接收到的数据信号
                    self.data_received.emit(data.hex())  # 发送十六进制字符串
                    # 如果收到完整的帧，就返回
                    if received_data and received_data[-1] == 0x16:  # 结束符
                        return bytes(received_data)
                time.sleep(0.001)  # 短暂休眠，避免CPU占用过高
            return None  # 超时返回None
            
        except Exception as e:
            print(f"接收数据错误: {e}")
            return None

    def receive_frame(self):
        """接收数据帧"""
        if self.serial and self.serial.is_open:
            try:
                datalen = self.serial.in_waiting
                if datalen > 0:
                    data = self.serial.read(datalen)
                    return data
            except Exception as e:
                print(f"接收数据错误: {e}")
                return ""
        return ""
    def start_receive_thread(self):
        """启动接收线程"""
        if self.serial and self.serial.is_open:
            self.receive_thread = threading.Thread(target=self.receive_loop)
            self.receive_thread.start()
        else:
            print("串口未连接或未打开")

    def receive_loop(self):
        """接收循环"""
        while not self.stop_receive_thread:  # 检查标志位
            frame = self.receive_frame()
            time.sleep(0.1)
            if frame:
                print(f"接收到数据帧: {frame.hex()}")
                self.data_received.emit(frame.hex())  # Emit the signal with hex string

    def checkthread(self):
         # 获取所有线程的列表
        all_threads = threading.enumerate()
        # 打印每个线程的名称和状态
        for thread in all_threads:
            print(f"线程名称: {thread.name}, 状态: {thread.is_alive()}")