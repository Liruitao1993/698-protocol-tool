#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户数据解析调试脚本
"""

import sys
import os

# 添加项目路径到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol.protocol_698 import Protocol698

def debug_user_data():
    """调试用户数据解析"""
    print("=== 用户数据解析调试 ===")
    
    # 创建协议实例
    protocol = Protocol698()
    
    # 测试帧数据：包含用户数据域
    test_frame = bytes([
        0x68,  # 起始符
        0x3A,  # 长度域 (58字节)
        0x00,  # 长度域
        0xD3,  # 控制域 - 有数据域、客户机发出、启动站、功能码3
        0x05,  # SA标志 - 单地址、无扩展逻辑地址、无逻辑地址标志、6字节地址长度
        0x00, 0x00, 0x00, 0x00, 0x00, 0x01,  # SA地址
        0x01,  # CA客户机地址
        0x00, 0x00,  # HCS帧头校验（占位）
        # 应用层链路用户数据 (8字节)
        0x53,  # 链路控制域
        0x04,  # 链路用户数据长度
        0x01, 0x02, 0x03, 0x04,  # 链路用户数据内容
        # APDU数据 (模拟)
        0x85,  # APDU类型 (读取请求)
        0x01,  # 服务属性
        0x00, 0x02,  # 数据长度
        0xAA, 0xBB,  # 数据内容
        0x00, 0x00,  # FCS校验（占位）
        0x16   # 结束符
    ])
    
    print(f"测试帧数据长度: {len(test_frame)}")
    print(f"测试帧数据: {test_frame.hex()}")
    
    # 手动分析帧结构
    print("\n=== 手动分析帧结构 ===")
    
    # 1. 起始符
    start = test_frame[0]
    print(f"起始符: {start:02X}")
    
    # 2. 长度域
    length = test_frame[1] | (test_frame[2] << 8)
    print(f"长度域: {length} ({length:04X}H)")
    
    # 3. 控制域
    control = test_frame[3]
    print(f"控制域: {control:02X}H")
    print(f"  有数据域: {'是' if (control & 0x10) else '否'}")
    
    # 4. SA标志
    sa_flag = test_frame[4]
    addr_len_code = sa_flag & 0x0F
    addr_len = protocol.ADDR_LEN_MAP.get(addr_len_code, 1)
    print(f"SA标志: {sa_flag:02X}H")
    print(f"  地址长度: {addr_len}")
    
    # 5. 计算各字段位置
    idx = 5  # SA地址开始位置
    sa_addr_end = idx + addr_len  # SA地址结束位置
    print(f"SA地址范围: {idx}-{sa_addr_end-1}")
    
    idx = sa_addr_end  # CA地址位置
    ca = test_frame[idx]
    print(f"CA地址: {idx} ({ca:02X}H)")
    
    idx += 1  # HCS开始位置
    hcs_end = idx + 2
    print(f"HCS范围: {idx}-{hcs_end-1}")
    
    idx = hcs_end  # 用户数据开始位置
    
    # 计算用户数据长度
    user_data_start = idx
    user_data_end = len(test_frame) - 3  # 减去时间标签(1) + FCS(2) + 结束符(1) = 4，但结束符不算在内
    user_data_len = user_data_end - user_data_start
    
    print(f"用户数据范围: {user_data_start}-{user_data_end-1} (长度: {user_data_len})")
    print(f"用户数据: {test_frame[user_data_start:user_data_end].hex()}")
    
    # 尝试解析
    print("\n=== 协议解析结果 ===")
    result = protocol.parse_frame(test_frame)
    
    if '应用层链路用户数据' in result:
        print(f"应用层链路用户数据: {result['应用层链路用户数据']}")
    else:
        print("无应用层链路用户数据")
        
    if '用户数据解析' in result:
        print(f"用户数据解析: {result['用户数据解析']}")
    else:
        print("无用户数据解析")

if __name__ == "__main__":
    debug_user_data()