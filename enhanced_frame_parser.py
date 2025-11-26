#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版698.45协议帧解析器
确保完整解析SA地址、客户机地址、帧头校验和应用层链路用户数据
"""

class EnhancedFrameParser:
    def __init__(self):
        self.frame_start_mark = 0x68  # 帧起始符
        self.frame_end_mark = 0x16    # 帧结束符
    
    def parse_frame_complete(self, frame_bytes):
        """
        完整解析698.45协议帧
        
        Args:
            frame_bytes: 帧数据字节序列
            
        Returns:
            dict: 完整的解析结果
        """
        if not frame_bytes or len(frame_bytes) < 12:
            return {'error': '帧数据长度不足'}
        
        result = {}
        idx = 0
        
        try:
            # 1. 帧起始符 (0x68)
            if frame_bytes[idx] != self.frame_start_mark:
                return {'error': f'帧起始符应为68H，实际为{frame_bytes[idx]:02X}H'}
            result['帧起始符'] = '68H'
            idx += 1
            
            # 2. 长度域 (L)
            if idx >= len(frame_bytes):
                return {'error': '无法获取长度域'}
            length = frame_bytes[idx]
            result['长度域'] = f'{length:02X}H ({length}字节)'
            idx += 1
            
            # 3. 控制域 (C)
            if idx >= len(frame_bytes):
                return {'error': '无法获取控制域'}
            control = frame_bytes[idx]
            result['控制域'] = {
                '原始值': f'{control:02X}H',
                'DIR': '主站->从站' if (control & 0x80) == 0 else '从站->主站',
                'PRM': '启动帧' if (control & 0x40) != 0 else '确认帧',
                'FCB': '帧计数位有效' if (control & 0x20) != 0 else '帧计数位无效',
                'FCV': '帧计数有效' if (control & 0x10) != 0 else '帧计数无效',
                '功能码': control & 0x0F
            }
            idx += 1
            
            # 4. 地址域 (A)
            # 4.1 SA地址 (系统地址) - 2字节
            if idx + 1 >= len(frame_bytes):
                return {'error': '无法获取SA地址'}
            sa_address = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['SA地址'] = {
                '原始值': f'{sa_address:04X}H',
                '十进制': sa_address,
                '二进制': bin(sa_address)[2:].zfill(16)
            }
            idx += 2
            
            # 4.2 客户机地址 - 2字节
            if idx + 1 >= len(frame_bytes):
                return {'error': '无法获取客户机地址'}
            client_address = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['客户机地址'] = {
                '原始值': f'{client_address:04X}H',
                '十进制': client_address,
                '二进制': bin(client_address)[2:].zfill(16)
            }
            idx += 2
            
            # 5. 帧头校验 (HCS) - 2字节
            if idx + 1 >= len(frame_bytes):
                return {'error': '无法获取帧头校验'}
            hcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['帧头校验'] = {
                '原始值': f'{hcs:04X}H',
                '十进制': hcs
            }
            
            # 计算并验证帧头校验
            calculated_hcs = self.calculate_hcs(frame_bytes[1:idx+2])  # 从长度域到HCS之前
            result['帧头校验']['计算值'] = f'{calculated_hcs:04X}H'
            result['帧头校验']['校验结果'] = '通过' if hcs == calculated_hcs else '失败'
            idx += 2
            
            # 6. 应用层链路用户数据
            if idx >= len(frame_bytes):
                return {'error': '无法获取应用层链路用户数据'}
            
            # 计算用户数据长度
            user_data_length = length - 8  # 总长度减去控制域、地址域和HCS
            if idx + user_data_length > len(frame_bytes):
                return {'error': '用户数据长度超出帧范围'}
            
            user_data = frame_bytes[idx:idx+user_data_length]
            result['应用层链路用户数据'] = self.parse_user_data(user_data)
            idx += user_data_length
            
            # 7. 帧校验序列 (FCS) - 2字节
            if idx + 1 >= len(frame_bytes):
                return {'error': '无法获取帧校验序列'}
            fcs = frame_bytes[idx] | (frame_bytes[idx+1] << 8)
            result['帧校验序列'] = {
                '原始值': f'{fcs:04X}H',
                '十进制': fcs
            }
            
            # 计算并验证帧校验
            calculated_fcs = self.calculate_fcs(frame_bytes[1:idx+2])  # 从长度域到FCS之前
            result['帧校验序列']['计算值'] = f'{calculated_fcs:04X}H'
            result['帧校验序列']['校验结果'] = '通过' if fcs == calculated_fcs else '失败'
            idx += 2
            
            # 8. 帧结束符 (0x16)
            if idx >= len(frame_bytes):
                return {'error': '无法获取帧结束符'}
            end_mark = frame_bytes[idx]
            result['帧结束符'] = {
                '原始值': f'{end_mark:02X}H',
                '校验结果': '通过' if end_mark == self.frame_end_mark else '失败'
            }
            
            return result
            
        except Exception as e:
            return {'error': f'解析错误: {str(e)}'}
    
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
    
    def calculate_hcs(self, data):
        """
        计算帧头校验序列(HCS)
        使用CRC-16-CCITT算法
        
        Args:
            data: 要计算校验的数据
            
        Returns:
            int: 校验值
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
    
    def calculate_fcs(self, data):
        """
        计算帧校验序列(FCS)
        使用CRC-16-CCITT算法
        
        Args:
            data: 要计算校验的数据
            
        Returns:
            int: 校验值
        """
        # FCS计算与HCS相同，都是CRC-16-CCITT
        return self.calculate_hcs(data)


# 示例使用
if __name__ == "__main__":
    # 示例帧数据 (68 12 01 1234 5678 ABCD 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12 13 14 15 16)
    # 这是一个示例，实际使用时替换为真实的帧数据
    example_frame = bytes([
        0x68,  # 帧起始符
        0x12,  # 长度域
        0x01,  # 控制域
        0x12, 0x34,  # SA地址
        0x56, 0x78,  # 客户机地址
        0xAB, 0xCD,  # 帧头校验
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,  # 应用层链路用户数据
        0x11, 0x12,  # 帧校验序列
        0x16   # 帧结束符
    ])
    
    parser = EnhancedFrameParser()
    result = parser.parse_frame_complete(example_frame)
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))