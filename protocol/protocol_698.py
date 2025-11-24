from ctypes import Structure, c_uint8
from crcmod import predefined

class ControlField(Structure):
    """698.45协议控制域结构"""
    _pack_ = 1
    _fields_ = [
        # 使用位域来定义每个标志位
        ("func_code", c_uint8, 3),  # D2-D0: 功能码
        ("reserved", c_uint8, 1),   # D3: 保留位
        ("sc_flag", c_uint8, 1),    # D4: 数据域标志
        ("split_frame", c_uint8, 1), # D5: 分帧标志
        ("prm", c_uint8, 1),        # D6: 启动标志位
        ("dir", c_uint8, 1),        # D7: 传输方向位
    ]

class SAFlagField(Structure):
    """698.45协议SA标志字节结构"""
    _pack_ = 1
    _fields_ = [
        ("addr_len", c_uint8, 4),      # D3-D0: 地址长度
        ("logic_addr", c_uint8, 1),    # D4: 逻辑地址标志
        ("ext_logic", c_uint8, 1),     # D5: 扩展逻辑地址标志
        ("addr_type", c_uint8, 2),     # D7-D6: 地址类型
    ]

    # 添加地址长度映射
    ADDR_LEN_MAP = {
        '1字节(0)': 0x00,
        '2字节(1)': 0x01,
        '4字节(2)': 0x03,
        '6字节(3)': 0x05  # 修正6字节的码
    }

class Protocol698:
    # 功能码映射 (D2-D0)
    FUNCTION_CODES = {
        '保留(0)': 0,      # 保留
        '链路管理(1)': 1,   # 链路连接管理
        '保留(2)': 2,      # 保留
        '用户数据(3)': 3,   # 应用连接管理及数据交换服务
        '保留(4)': 4,      # 保留
        '保留(5)': 5,      # 保留
        '保留(6)': 6,      # 保留
        '保留(7)': 7       # 保留
    }
    
    # 地址类型映射
    ADDRESS_TYPES = {
        '单地址': 0x00,
        '通配地址': 0x01,
        '组地址': 0x02,
        '广播地址': 0x03
    }
    
    # 地址长度映射（D3-D0实际值到字节数的映射）
    ADDR_LEN_MAP = {
        0: 1,  # 0表示1字节
        1: 2,  # 1表示2字节
        2: 4,  # 2表示4字节
        5: 6,   # 5表示6字节
        6: 7,  # 6表示7字节
        7: 8,   # 7表示8字节
        8: 9,   # 8表示9字节

    }
    
    # 反向映射（字节数到D3-D0实际值的映射）
    ADDR_LEN_REVERSE_MAP = {
        1: 0,  # 1字节用0表示
        2: 1,  # 2字节用1表示
        3: 2,
        4: 3,  # 4字节用2表示
        6: 5,  # 6字节用5表示
        7: 6,  # 7字节用6表示
        8: 7,  # 8字节用7表示
        9: 8   # 9字节用8表��
    }
    
    # 添加SA地址标映射
    SA_FLAGS = {
        '单地址-1字节(01)': 0x01,
        '单地址-2字节(02)': 0x02,
        '单地址-4字节(03)': 0x03,
        '单地址-6字节(04)': 0x04,
        '通配地址-1字节(11)': 0x11,
        '通配地址-2字节(12)': 0x12,
        '通配地址-4字节(13)': 0x13,
        '通配地址-6字节(14)': 0x14,
        '组地址-1字节(21)': 0x21,
        '组地址-2字节(22)': 0x22,
        '组地址-4字节(23)': 0x23,
        '组地址-6字节(24)': 0x24,
        '广播地址-1字节(31)': 0x31,
        '广播地址-2字节(32)': 0x32,
        '广播地址-4字节(33)': 0x33,
        '广播地址-6字节(34)': 0x34
    }
    
    # 应用层服务类型（1字节）
    APDU_SERVICES = {
        '建立应用连接请求': {
            'code': 0x02,  # CONNECT-Request
            'data_types': {}  # 暂无子类型
        },
        '断开应用连接请求': {
            'code': 0x03,  # RELEASE-Request
            'data_types': {}
        },
        '读取请求': {
            'code': 0x05,  # GET-Request
            'data_types': {
                '请求一个对象属性': 0x01,     # GetRequestNormal
                '请求若干个对象属性': 0x02,   # GetRequestNormalList
                '请求一个��录型对象属性': 0x03,  # GetRequestRecord
                '请求若干个记录型对象属性': 0x04,  # GetRequestRecordList
                '请求分帧传输的下一帧': 0x05,  # GetRequestNext
                '请求一个对象属性的MD5值': 0x06  # GetRequestMD5
            }
        },
        '设置请求': {
            'code': 0x06,  # SET-Request
            'data_types': {
                '请求设置一个对象属性': 0x01,     # SetRequestNormal
                '请求设置若干个对象属性': 0x02,   # SetRequestNormalList
                '请求设置后若干个对象属性': 0x03  # SetTheGetRequestNormalList
            }
        },
        '操作请求': {
            'code': 0x07,  # ACTION-Request
            'data_types': {}
        },
        '上报应答': {
            'code': 0x08,  # REPORT-Response
            'data_types': {}
        },
        '代理请求': {
            'code': 0x09,  # PROXY-Request
            'data_types': {}
        }
    }
    
    def __init__(self):
        self.frames = {}
        # 使用预定义的X-25 CRC算法
        self.crc16 = predefined.mkPredefinedCrcFun('x-25')
        self.piid = 0  # 初始化PIID为0
    
    def get_next_piid(self):
        """获取下一个PIID值（0-63循环）"""
        self.piid = (self.piid + 1) & 0x3F  # PIID为6位，范围0-63
        return self.piid
    
    def create_control_field(self, direction, prm, function, split_frame, sc_flag):
        """
        创建控制域
        direction: 方向位 ('客户机发出(0)'/'服务器发出(1)')
        prm: 启动标志位 ('从动站(0)'/'启动站(1)')
        function: 功能码 ('预链接(0)'等)
        split_frame: 分帧标志 ('不分帧(0)'/'分帧(1)')
        sc_flag: 数据域标志 ('无数据域(0)'/'有数据域(1)')
        """
        control = ControlField()
        
        # 设置方向位 D7
        control.dir = 1 if direction == '服务器发出(1)' else 0
        
        # 设置启动标志位 D6
        control.prm = 1 if prm == '启动站(1)' else 0
        
        # 设置分帧标志 D5
        control.split_frame = 1 if split_frame == '分帧(1)' else 0
        
        # 设置数据域标志 D4
        control.sc_flag = 1 if sc_flag == '有数据域(1)' else 0
        
        # 设置功能码 D2-D0
        func_name = function.split('(')[0]
        control.func_code = self.FUNCTION_CODES.get(function, 0) & 0x07  # 确保只使用低3位
        
        # 将Structure转换为字节
        return bytes(control)[0]  # 只需要第一个字节
    
    def create_sa_flag(self, addr_type, ext_logic_addr, logic_addr_flag, addr_len):
        """
        创建SA标字节
        addr_type: 地址类型 ('单地址(0)'等)
        ext_logic_addr: 扩展逻辑地址标志 ('无扩展逻辑地址(0)'/'有扩展逻辑地址(1)')
        logic_addr_flag: 逻辑地址标志 ('无逻辑地址(0)'/'有逻辑地址(1)')
        addr_len: 地址长度 ('1字节(0)'等)
        """
        sa_flag = SAFlagField()
        
        # 设置地址类型 D7-D6
        sa_flag.addr_type = int(addr_type.split('(')[1].split(')')[0])
        
        # 设置扩展逻辑地址标志 D5
        sa_flag.ext_logic = 1 if ext_logic_addr == '有扩展逻辑地址(1)' else 0
        
        # 设置逻辑地址标志 D4
        sa_flag.logic_addr = 1 if logic_addr_flag == '有逻辑地址(1)' else 0
        
        # 设置地址长度 D3-D0
        sa_flag.addr_len = SAFlagField.ADDR_LEN_MAP[addr_len]
        
        # 将Structure转换为字节
        return bytes(sa_flag)[0]
    
    def create_frame(self, direction, prm, function, split_frame, addr_type, addr_len,
                    sa_logic_addr, logic_addr, comm_addr, ext_logic_addr, logic_addr_flag,
                    service_type, service_data_type, service_priority, service_number, oad,
                    custom_data=''):
        """
        创建698.45协议帧（优化版 - 修复CRC计算）
        """
        frame = []
        
        # 1. 帧起始符
        frame.append(0x68)
        
        # 2. 长度域（临时占位，后面计算）
        frame.extend([0x00, 0x00])
        
        # 3. 控制域
        control = ControlField()
        if direction == '服务器发出(1)':
            control.dir = 1
        if prm == '启动站(1)':
            control.prm = 1
        if split_frame == '分帧(1)':
            control.split_frame = 1
        # 如果有服务类型，说明有数据域
        if service_type:
            control.sc_flag = 1
        control.func_code = self.FUNCTION_CODES.get(function, 0) & 0x07
        frame.append(bytes(control)[0])
        
        # 4. SA标志字节
        sa_flag = SAFlagField()
        sa_flag.addr_type = int(addr_type.split('(')[1].split(')')[0])
        sa_flag.ext_logic = 1 if ext_logic_addr == '有扩展逻辑地址(1)' else 0
        sa_flag.logic_addr = 1 if logic_addr_flag == '有逻辑地址(1)' else 0
        sa_flag.addr_len = self.ADDR_LEN_REVERSE_MAP[int(addr_len)]
        frame.append(bytes(sa_flag)[0])
        
        # 5. SA逻辑地址（如果有）
        addr_length = int(addr_len)
        if logic_addr_flag == '有逻辑地址(1)' and sa_logic_addr:
            sa_logic_addr_int = int(sa_logic_addr, 16)
            frame.append(sa_logic_addr_int & 0xFF)
        
        # 6. SA地址（低字节在前）
        sa_bytes = bytes.fromhex(comm_addr.zfill(addr_length*2))
        frame.extend(list(reversed(sa_bytes)))
        
        # 7. CA客户机地址
        ca_int = int(logic_addr)
        frame.append(ca_int & 0xFF)
        
        # 8. HCS帧头校验（占位，后面计算）
        hcs_pos = len(frame)
        frame.extend([0x00, 0x00])
        
        # 9. APDU（如果有服务类型）
        if service_type:
            service_info = self.APDU_SERVICES.get(service_type, {})
            service_code = service_info.get('code', 0)
            data_type_code = service_info.get('data_types', {}).get(service_data_type, 0)
            
            frame.append(service_code)  # 服务类型码
            frame.append(data_type_code)  # 数据类型码
            
            # PIID
            piid = (int(service_priority) << 6) | (service_number & 0x3F)
            frame.append(piid)
            
            # OAD
            oad_bytes = bytes.fromhex(oad)
            frame.extend(oad_bytes)
            
            # 自定义数据
            if custom_data:
                try:
                    custom_bytes = bytes.fromhex(custom_data)
                    frame.extend(custom_bytes)
                except ValueError as e:
                    print(f"自定义报文格式错误: {e}")
        
        # 10. 时间标签
        frame.append(0x00)
        
        # 11. FCS帧校验（占位，后面计算）
        fcs_pos = len(frame)
        frame.extend([0x00, 0x00])
        
        # 12. 帧结束符
        frame.append(0x16)
        
        # 13. 计算并更新长度域
        # 根据DL/T 698.45协议：长度域 = 长度域自身(2) + 控制域到FCS(包含)的字节数
        length = fcs_pos + 1  # fcs_pos是FCS开始位置，+1是加上长度域本身（已减去起始符）
        frame[1] = length & 0xFF
        frame[2] = (length >> 8) & 0xFF
        
        # 14. 计算并更新HCS
        # HCS范围：从长度域到CA（包含长度域，不包含HCS自身）
        # 长度域在frame[1]，CA在hcs_pos-1
        hcs_data = bytes(frame[1:hcs_pos])
        hcs = self.crc16(hcs_data)
        frame[hcs_pos] = hcs & 0xFF
        frame[hcs_pos + 1] = (hcs >> 8) & 0xFF
        
        # 15. 计算并更新FCS（必须在HCS填充之后）
        # FCS范围：从长度域到时间标签（包含长度域和HCS，不包含FCS自身）
        # 长度域在frame[1]，时间标签在fcs_pos-1
        fcs_data = bytes(frame[1:fcs_pos])
        fcs = self.crc16(fcs_data)
        frame[fcs_pos] = fcs & 0xFF
        frame[fcs_pos + 1] = (fcs >> 8) & 0xFF
        
        return bytes(frame)
    
    def save_frame(self, name, frame):
        """保存命名帧"""
        self.frames[name] = frame
        
    def get_frame(self, name):
        """获取已保存的帧"""
        return self.frames.get(name)
    
    def parse_frame(self, frame_bytes):
        """
        解析698.45协议帧
        返回解析结果字典
        """
        try:
            if not frame_bytes or len(frame_bytes) < 10:
                return {'error': '帧长度不足'}
            
            result = {}
            idx = 0
            
            # 1. 起始符 (0x68)
            if frame_bytes[idx] != 0x68:
                return {'error': f'起始符错误: {frame_bytes[idx]:02X}'}
            result['起始符'] = '68'
            idx += 1
            
            # 2. 长度域 (2字节，小端)
            length = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['长度域'] = f'{length} ({length:04X}H)'
            idx += 2
            
            # 3. 控制域 (1字节)
            control = frame_bytes[idx]
            result['控制域'] = {
                '原始值': f'{control:02X}H',
                'D7-传输方向': '服务器发出' if (control & 0x80) else '客户机发出',
                'D6-启动标志': '启动站' if (control & 0x40) else '从动站',
                'D5-分帧标志': '分帧' if (control & 0x20) else '不分帧',
                'D4-数据域标志': '有数据域' if (control & 0x10) else '无数据域',
                'D2-D0-功能码': control & 0x07
            }
            idx += 1
            
            # 4. SA标志 (1字节)
            sa_flag = frame_bytes[idx]
            addr_type_code = (sa_flag >> 6) & 0x03
            addr_type_map = {0: '单地址', 1: '通配地址', 2: '组地址', 3: '广播地址'}
            addr_len_code = sa_flag & 0x0F
            addr_len = self.ADDR_LEN_MAP.get(addr_len_code, 1)
            
            result['SA标志'] = {
                '原始值': f'{sa_flag:02X}H',
                'D7-D6-地址类型': addr_type_map.get(addr_type_code, '未知'),
                'D5-扩展逻辑地址': '有' if (sa_flag & 0x20) else '无',
                'D4-逻辑地址标志': '有' if (sa_flag & 0x10) else '无',
                'D3-D0-地址长度': f'{addr_len}字节 ({addr_len_code})'
            }
            idx += 1
            
            # 5. SA逻辑地址 (如果有)
            if sa_flag & 0x10:  # 有逻辑地址
                sa_logic = frame_bytes[idx]
                result['SA逻辑地址'] = f'{sa_logic:02X}H'
                idx += 1
            
            # 6. SA地址 (addr_len字节，小端)
            sa_addr_bytes = frame_bytes[idx:idx+addr_len]
            sa_addr = ''.join(f'{b:02X}' for b in reversed(sa_addr_bytes))
            result['SA地址'] = sa_addr
            idx += addr_len
            
            # 7. CA地址 (1字节)
            ca = frame_bytes[idx]
            result['CA地址'] = f'{ca} ({ca:02X}H)'
            idx += 1
            
            # 8. HCS校验 (2字节)
            hcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['HCS校验'] = f'{hcs:04X}H'
            idx += 2
            
            # 9. APDU (如果有数据域)
            if control & 0x10:
                # 服务类型 (1字节)
                if idx < len(frame_bytes) - 3:  # 至少要有时间标签+FCS+结束符
                    service_type = frame_bytes[idx]
                    result['APDU'] = {
                        '服务类型码': f'{service_type:02X}H'
                    }
                    idx += 1
                    
                    # 数据类型 (1字节)
                    if idx < len(frame_bytes) - 3:
                        data_type = frame_bytes[idx]
                        result['APDU']['数据类型码'] = f'{data_type:02X}H'
                        idx += 1
                        
                        # PIID (1字节)
                        if idx < len(frame_bytes) - 3:
                            piid = frame_bytes[idx]
                            result['APDU']['PIID'] = {
                                '原始值': f'{piid:02X}H',
                                '优先级': (piid >> 6) & 0x03,
                                '序号': piid & 0x3F
                            }
                            idx += 1
                            
                            # OAD (4字节)
                            if idx + 4 <= len(frame_bytes) - 3:
                                oad_bytes = frame_bytes[idx:idx+4]
                                oad_hex = ''.join(f'{b:02X}' for b in oad_bytes)
                                result['APDU']['OAD'] = oad_hex
                                idx += 4
                                
                                # 剩余数据（自定义数据）
                                remaining_len = len(frame_bytes) - idx - 3  # 减去时间标签+FCS+结束符
                                if remaining_len > 0:
                                    custom_data = frame_bytes[idx:idx+remaining_len]
                                    result['APDU']['自定义数据'] = ''.join(f'{b:02X}' for b in custom_data)
                                    idx += remaining_len
            
            # 10. 时间标签 (1字节)
            if idx < len(frame_bytes) - 3:
                time_tag = frame_bytes[idx]
                result['时间标签'] = f'{time_tag:02X}H'
                idx += 1
            
            # 11. FCS校验 (2字节)
            if idx + 2 < len(frame_bytes):
                fcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
                result['FCS校验'] = f'{fcs:04X}H'
                idx += 2
            
            # 12. 结束符 (0x16)
            if idx < len(frame_bytes):
                end_mark = frame_bytes[idx]
                result['结束符'] = f'{end_mark:02X}H'
                if end_mark != 0x16:
                    result['warning'] = f'结束符应为16H，实际为{end_mark:02X}H'
            
            return result
            
        except Exception as e:
            return {'error': f'解析错误: {str(e)}'} 