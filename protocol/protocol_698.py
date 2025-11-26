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
        2: 3,  # 2表示3字节
        3: 4,  # 3表示4字节
        4: 5,  # 4表示5字节
        5: 6,  # 5表示6字节
        6: 7,  # 6表示7字节
        7: 8,  # 7表示8字节
        8: 9,  # 8表示9字节
        9: 10, # 9表示10字节
        10: 11, # A表示11字节
        11: 12, # B表示12字节
        12: 13, # C表示13字节
        13: 14, # D表示14字节
        14: 15, # E表示15字节
        15: 16  # F表示16字节
    }
    
    # 反向映射（字节数到D3-D0实际值的映射）
    ADDR_LEN_REVERSE_MAP = {
        1: 0,   # 1字节用0表示
        2: 1,   # 2字节用1表示
        3: 2,   # 3字节用2表示
        4: 3,   # 4字节用3表示
        5: 4,   # 5字节用4表示
        6: 5,   # 6字节用5表示
        7: 6,   # 7字节用6表示
        8: 7,   # 8字节用7表示
        9: 8,   # 9字节用8表示
        10: 9,  # 10字节用9表示
        11: 10, # 11字节用A表示
        12: 11, # 12字节用B表示
        13: 12, # 13字节用C表示
        14: 13, # 14字节用D表示
        15: 14, # 15字节用E表示
        16: 15  # 16字节用F表示
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
    
    # 应用层服务类型（1字节）- 根据DL/T 698.45协议定义
    APDU_SERVICES = {
        # 旧版接口兼容（仅中文名称）
        '建立应用连接请求': {
            'code': 0x01,  # LINK-Request
            'data_types': {}
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
                '请求一个记录型对象属性': 0x03,  # GetRequestRecord
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
        },
        # 新版接口（带英文名称和编码）
        'LINK-Request 建立应用连接请求 (1)': {
            'code': 0x01,
            'data_types': {
                'CONNECT-Request 建立应用连接请求 [0]': 0x00
            }
        },
        'RELEASE-Request 断开应用连接请求 (3)': {
            'code': 0x03,
            'data_types': {
                'RELEASE-Request 断开应用连接请求 [0]': 0x00
            }
        },
        'GET-Request 读取请求 (5)': {
            'code': 0x05,
            'data_types': {
                'GetRequestNormal 读取一个对象属性 [1]': 0x01,
                'GetRequestNormalList 读取若干个对象属性 [2]': 0x02,
                'GetRequestRecord 读取一个记录型对象属性 [3]': 0x03,
                'GetRequestRecordList 读取若干个记录型对象属性 [4]': 0x04,
                'GetRequestNext 读取分帧传输的下一帧数据 [5]': 0x05,
                'GetRequestMD5 读取一个对象属性的MD5值 [6]': 0x06
            }
        },
        'SET-Request 设置请求 (6)': {
            'code': 0x06,
            'data_types': {
                'SetRequestNormal 设置一个对象属性 [1]': 0x01,
                'SetRequestNormalList 设置若干个对象属性 [2]': 0x02,
                'SetThenGetRequestNormalList 设置后读取若干个对象属性 [3]': 0x03
            }
        },
        'ACTION-Request 操作请求 (7)': {
            'code': 0x07,
            'data_types': {
                'ActionRequestNormal 操作一个对象方法 [1]': 0x01,
                'ActionRequestNormalList 操作若干个对象方法 [2]': 0x02,
                'ActionThenGetRequestNormalList 操作后读取若干个对象属性 [3]': 0x03
            }
        },
        'REPORT-Response 上报应答 (8)': {
            'code': 0x08,
            'data_types': {
                'ReportResponseRecord 上报一个记录型对象 [1]': 0x01,
                'ReportResponseRecordList 上报若干个记录型对象 [2]': 0x02,
                'ReportResponseTransData 上报透传的数据 [3]': 0x03
            }
        },
        'PROXY-Request 代理请求 (9)': {
            'code': 0x09,
            'data_types': {
                'ProxyRequestGetList 代理读取若干个服务器的若干个对象属性 [1]': 0x01,
                'ProxyRequestSetList 代理设置若干个服务器的若干个对象属性 [2]': 0x02,
                'ProxyRequestActionList 代理操作若干个服务器的若干个对象方法 [3]': 0x03,
                'ProxyRequestTransCommandList 代理透传若干个服务器的命令 [4]': 0x04,
                'ProxyRequestGetTransData 代理读取若干个服务器的若干个透传对象 [5]': 0x05
            }
        },
        'COMPACT-GET-Request 简化读取请求 (133)': {
            'code': 0x85,
            'data_types': {
                'CompactGetRequestNormal 简化读取一个对象属性 [1]': 0x01
            }
        },
        'COMPACT-SET-Request 简化设置请求 (134)': {
            'code': 0x86,
            'data_types': {
                'CompactSetRequestNormal 简化设置一个对象属性 [1]': 0x01
            }
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
                    sa_logic_value, bit5, logic_addr, comm_addr,
                    service_type, service_data_type, service_priority, service_number, oad,
                    custom_data=''):
        """
        创建698.45协议帧
        sa_logic_value: SA逻辑地址值（0, 1, 或 2-255）
        bit5: 扩展逻辑地址标志（0或1）
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
        # 根据协议：bit5=扩展逻辑地址标志，bit4根据sa_logic_value确定
        sa_flag = SAFlagField()
        sa_flag.addr_type = int(addr_type.split('(')[1].split(')')[0])
        sa_flag.ext_logic = bit5
        
        # bit4的值根据SA逻辑地址确定
        if bit5 == 0:
            # bit5=0时，bit4表示逻辑地址0或1
            sa_flag.logic_addr = sa_logic_value  # 0或1
        else:
            # bit5=1时，bit4备用
            sa_flag.logic_addr = 0
        
        sa_flag.addr_len = self.ADDR_LEN_REVERSE_MAP[int(addr_len)]
        frame.append(bytes(sa_flag)[0])
        
        # 5. 扩展逻辑地址（如果bit5=1）
        # 根据698.45协议：扩展逻辑地址是固定1字节长度，值为sa_logic_value（2-255）
        ext_logic_content_len = 0
        if bit5 == 1:
            ext_logic_content_len = 1
            frame.append(sa_logic_value & 0xFF)  # 写入扩展逻辑地址值
        
        # 6. SA地址（低字节在前）
        # 注意：SA地址长度 = addr_len(总长度) - ext_logic_content_len(扩展逻辑地址长度)
        sa_comm_addr_len = int(addr_len) - ext_logic_content_len
        comm_addr_hex = comm_addr.replace(' ', '').replace('\t', '')
        sa_bytes = bytes.fromhex(comm_addr_hex.zfill(sa_comm_addr_len*2))
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
            
            # 5.5 扩展逻辑地址 (如果有)
            # 根据698.45协议：扩展逻辑地址是固定1字节长度，无需长度字段
            ext_logic_content_len = 0
            if sa_flag & 0x20:  # 有扩展逻辑地址
                if idx < len(frame_bytes):
                    ext_logic_byte = frame_bytes[idx]
                    ext_logic_content_len = 1  # 固定1字节
                    result['扩展逻辑地址'] = f'{ext_logic_byte:02X}H'
                    idx += 1
                else:
                    result['扩展逻辑地址'] = '错误：缺少扩展逻辑地址字节'
            
            # 6. SA地址 (实际长度 = addr_len - ext_logic_content_len, 小端)
            sa_actual_len = addr_len - ext_logic_content_len
            sa_addr_bytes = frame_bytes[idx:idx+sa_actual_len]
            sa_addr = ''.join(f'{b:02X}' for b in reversed(sa_addr_bytes))
            result['SA地址'] = {
                '原始值': sa_addr,
                '长度': sa_actual_len,
                '地址类型': addr_type_map.get(addr_type_code, '未知')
            }
            idx += sa_actual_len
            
            # 7. CA客户机地址 (1字节)
            ca = frame_bytes[idx]
            result['CA客户机地址'] = {
                '原始值': f'{ca:02X}H',
                '十进制': ca
            }
            idx += 1
            
            # 8. HCS帧头校验 (2字节)
            hcs_pos = idx
            hcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            
            # 计算HCS校验值：从长度域到CA（包含长度域，不包含HCS自身）
            hcs_data = bytes(frame_bytes[1:hcs_pos])
            calculated_hcs = self.crc16(hcs_data)
            
            result['HCS帧头校验'] = {
                '原始值': f'{hcs:04X}H',
                '计算值': f'{calculated_hcs:04X}H',
                '校验结果': '通过' if hcs == calculated_hcs else '失败'
            }
            idx += 2
            
            # 9. 应用层链路用户数据 (如果有数据域)
            if control & 0x10:
                # 计算应用层链路用户数据长度
                user_data_len = length - 12  # 长度域 - 12 (固定头部长度)
                if user_data_len > 0 and idx + user_data_len <= len(frame_bytes):
                    user_data = frame_bytes[idx:idx+user_data_len]
                    result['应用层链路用户数据'] = {
                        '原始值': user_data.hex(),
                        '长度': user_data_len
                    }
                    idx += user_data_len
                    
                    # 尝试解析用户数据
                    user_data_info = self.parse_user_data(user_data)
                    if user_data_info:
                        result['用户数据解析'] = user_data_info
            
            # 10. 时间标签 (1字节)
            if idx < len(frame_bytes) - 3:
                time_tag = frame_bytes[idx]
                result['时间标签'] = f'{time_tag:02X}H'
                idx += 1
            
            # 11. FCS校验 (2字节)
            if idx + 2 < len(frame_bytes):
                fcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
                
                # 计算FCS校验值：从长度域到时间标签（包含长度域和HCS，不包含FCS自身）
                fcs_data = bytes(frame_bytes[1:idx])
                calculated_fcs = self.crc16(fcs_data)
                
                result['FCS校验'] = {
                    '原始值': f'{fcs:04X}H',
                    '计算值': f'{calculated_fcs:04X}H',
                    '校验结果': '通过' if fcs == calculated_fcs else '失败'
                }
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
    
    def crc16(self, data):
        """
        计算CRC16校验值 (CRC-CCITT)
        
        Args:
            data: 要计算的数据字节
            
        Returns:
            int: CRC16校验值
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc >>= 1
        return crc
    
    def parse_user_data(self, user_data):
        """
        解析应用层链路用户数据
        
        Args:
            user_data: 应用层链路用户数据
            
        Returns:
            dict: 解析结果
        """
        if len(user_data) < 1:
            return {'error': '应用层链路用户数据长度不足'}
        
        result = {}
        idx = 0
        
        # 控制域 (1字节)
        if idx < len(user_data):
            control = user_data[idx]
            idx += 1
            
            result['控制域'] = {
                '原始值': f'{control:02X}',
                'DIR': '主站->从站' if (control & 0x80) == 0 else '从站->主站',
                'PRM': '启动帧' if (control & 0x40) != 0 else '确认帧',
                'FCB': '帧计数位有效' if (control & 0x20) != 0 else '帧计数位无效',
                'FCV': '帧计数有效' if (control & 0x10) != 0 else '帧计数无效',
                '功能码': control & 0x0F
            }
        
        # 链路用户数据
        if idx < len(user_data):
            # 判断是否有数据域
            has_data = (control & 0x10) != 0 if 'control' in locals() else False
            
            if has_data:
                # 数据长度 (1字节)
                if idx < len(user_data):
                    data_length = user_data[idx]
                    idx += 1
                    
                    # 数据内容
                    if idx + data_length <= len(user_data):
                        data_content = user_data[idx:idx+data_length]
                        idx += data_length
                        
                        result['链路用户数据'] = {
                            '数据长度': data_length,
                            '数据内容': data_content.hex()
                        }
                        
                        # 尝试解析数据内容
                        if data_length >= 4:
                            # 可能是APDU结构
                            apdu_info = self.parse_apdu(data_content)
                            if apdu_info:
                                result['APDU解析'] = apdu_info
            else:
                # 无数据域，剩余部分为链路用户数据
                remaining_data = user_data[idx:]
                result['链路用户数据'] = {
                    '数据长度': len(remaining_data),
                    '数据内容': remaining_data.hex()
                }
        
        return result
    
    def parse_apdu(self, apdu_data):
        """
        解析APDU数据
        
        Args:
            apdu_data: APDU数据
            
        Returns:
            dict: 解析结果
        """
        if len(apdu_data) < 4:
            return None
            
        result = {}
        idx = 0
        
        # 服务类型 (1字节)
        service_type = apdu_data[idx]
        idx += 1
        result['服务类型'] = f'{service_type:02X}'
        
        # 服务属性 (1字节)
        if idx < len(apdu_data):
            service_attr = apdu_data[idx]
            idx += 1
            result['服务属性'] = f'{service_attr:02X}'
        
        # 数据长度 (2字节，小端序)
        if idx + 1 < len(apdu_data):
            data_length = apdu_data[idx] | (apdu_data[idx+1] << 8)
            idx += 2
            result['数据长度'] = data_length
            
            # 数据内容
            if idx + data_length <= len(apdu_data):
                data_content = apdu_data[idx:idx+data_length]
                result['数据内容'] = data_content.hex()
        
        return result