from PySide6.QtCore import QObject, Signal
import threading
import time
import serial
import serial.tools.list_ports
import traceback

class SerialHandler(QObject):
    data_received = Signal(str)  # Define signal for received data

    def __init__(self):
        super().__init__()  # Initialize the QObject parent class
        self.serial = None
        self.stop_receive_thread = False  # New flag bit
        self._is_connected = False  # Add connection status flag
        
        # Frame reassembly buffer
        self.frame_buffer = bytearray()
        self.last_receive_time = 0
        self.frame_timeout = 0.05  # 50ms timeout for frame completion
        
        # Response frame event and data
        self.response_event = threading.Event()
        self.response_frame = None
        
    def get_available_ports(self):
        """Get a list of available serial ports"""
        return [port.device for port in serial.tools.list_ports.comports()]
    
    def connect(self, port, baudrate, parity='N', bytesize=8, stopbits=1):
        """Connect to serial port"""
        try:
            print("\n=== Start connecting to serial port ===")
            print(f"Call source:\n{traceback.format_stack()[-2]}")
            print(f"Parameters: port={port}, baudrate={baudrate}, parity={parity}, bytesize={bytesize}, stopbits={stopbits}")
            
            # If already connected to the same port, return True directly
            if (self.is_connected() and 
                self.serial.port == port and 
                self.serial.baudrate == baudrate and 
                self.serial.parity == parity and 
                self.serial.bytesize == bytesize and 
                self.serial.stopbits == stopbits):
                print("Already connected to the specified port, maintaining connection")
                return True
            
            # If already connected to a different port, disconnect first
            if self.is_connected():
                print("Detected serial port connection with different configuration, need to reconnect")
                self.disconnect()
            
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=parity,
                bytesize=bytesize,
                stopbits=stopbits,
                timeout=0.1  # Short timeout for non-blocking read
            )
            
            # Verify if the serial port is actually open
            if not self.serial.is_open:
                self.serial.open()
            
            print(f"Serial port successfully opened: {self.serial.port}")
            self.stop_receive_thread = False
            self.frame_buffer.clear()  # Clear frame buffer
            self.start_receive_thread()
            self._is_connected = True
            print("=== Serial port connection completed ===\n")
            return True
            
        except Exception as e:
            print("\n=== Serial port connection error ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Call stack:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            self.serial = None
            return False
    
    def disconnect(self):
        """Disconnect serial port"""
        try:
            print("\n=== Start disconnecting serial port ===")
            print(f"Call source:\n{traceback.format_stack()[-2]}")
            if self.serial:
                if self.serial.is_open:
                    self.stop_receive_thread = True
                    time.sleep(0.2)  # Give the thread more time to exit
                    self.serial.close()
                    print("Serial port closed")
                self.serial = None
            self._is_connected = False
            self.frame_buffer.clear()  # Clear frame buffer
            print("=== Serial port disconnection completed ===\n")
        except Exception as e:
            print("\n=== Serial port disconnection error ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Call stack:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            self.serial = None
    
    def is_connected(self):
        """Check if serial port is connected"""
        try:
            is_connected = (self.serial is not None and 
                           self.serial.is_open and 
                           self._is_connected)
            print(f"Check serial port connection status: {is_connected}")
            if not is_connected:
                print(f"Serial object: {self.serial}")
                print(f"Serial port open status: {self.serial.is_open if self.serial else 'N/A'}")
                print(f"Connection flag: {self._is_connected}")
            return is_connected
        except Exception as e:
            print("\n=== Check serial port status error ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Call stack:\n{''.join(traceback.format_stack())}")
            self._is_connected = False
            return False
    
    def send_frame(self, frame_data, timeout=1000):
        """Send data frame and wait for response"""
        if not self.is_connected():
            print("Serial port not connected, cannot send data")
            return False, None
        
        try:
            # 清除之前的响应数据和事件状态
            self.response_event.clear()
            self.response_frame = None
            
            print(f"Sending data: {frame_data.hex()}")
            self.serial.write(frame_data)
            self.data_received.emit(f"Send: {frame_data.hex()}")  # Send log
            print("Data sent successfully, waiting for response...")
            
            # 等待后台线程组装完整帧
            if self.response_event.wait(timeout / 1000.0):  # 转换为秒
                response = self.response_frame
                if response:
                    print(f"Response received: {response.hex()}")
                    # 不再重复发送信号，receive_loop已经发送了
                    return True, response
            
            print("Receive timeout")
            self.data_received.emit("Receive timeout")  # Send log
            return False, None
                
        except Exception as e:
            print(f"Send data error: {e}")
            self.data_received.emit(f"Send error: {str(e)}")  # Send log
            self._is_connected = False
            return False, None


    def process_frame_data(self, data):
        """Process received data for frame reassembly"""
        current_time = time.time()
        
        # Add new data to buffer
        self.frame_buffer.extend(data)
        self.last_receive_time = current_time
        
        # Check if we have a complete frame (ending with 0x16)
        if len(self.frame_buffer) > 0 and self.frame_buffer[-1] == 0x16:
            # Found complete frame
            complete_frame = bytes(self.frame_buffer)
            self.frame_buffer.clear()
            return complete_frame
        
        return None

    def receive_frame(self):
        """Receive data frame"""
        if self.serial and self.serial.is_open:
            try:
                datalen = self.serial.in_waiting
                if datalen > 0:
                    data = self.serial.read(datalen)
                    return data
            except Exception as e:
                print(f"Receive data error: {e}")
                return b""
        return b""
    
    def start_receive_thread(self):
        """Start receive thread"""
        if self.serial and self.serial.is_open:
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
        else:
            print("Serial port not connected or not open")

    def receive_loop(self):
        """Receive loop with frame reassembly"""
        while not self.stop_receive_thread:  # Check flag bit
            try:
                # Check if there's data to read
                if self.serial and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting)
                    if data:
                        print(f"Received data fragment: {data.hex()}")
                        
                        # Process data for frame reassembly
                        complete_frame = self.process_frame_data(data)
                        
                        # If complete frame found, emit signal and set event
                        if complete_frame:
                            print(f"Complete frame assembled: {complete_frame.hex()}")
                            self.data_received.emit(f"Receive: {complete_frame.hex()}")  # 统一格式
                            
                            # 设置响应帧并触发事件
                            self.response_frame = complete_frame
                            self.response_event.set()
                
                # Check for frame timeout (in case of incomplete frame)
                if len(self.frame_buffer) > 0:
                    current_time = time.time()
                    if current_time - self.last_receive_time > self.frame_timeout:
                        print(f"Frame timeout, discarding incomplete buffer: {self.frame_buffer.hex()}")
                        self.frame_buffer.clear()
                
                time.sleep(0.01)  # Short sleep to avoid high CPU usage
                
            except Exception as e:
                print(f"Receive loop error: {e}")
                time.sleep(0.1)  # Sleep longer on error

    def checkthread(self):
        # Get list of all threads
        all_threads = threading.enumerate()
        # Print name and status of each thread
        for thread in all_threads:
            print(f"Thread name: {thread.name}, status: {thread.is_alive()}")
