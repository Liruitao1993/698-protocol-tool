#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成正确的测试帧数据
"""

import sys
sys.path.append('protocol')

from protocol_698 import Protocol698

def generate_test_frame():
    """生成一个正确的测试帧"""
    parser = Protocol698()
    
    # 创建协议帧
    frame = parser.create_frame(
        direction='客户端发出(0)',
        prm='启动站(1)',
        function='应用连接管理(3)',
        split_frame='完整报文(0)',
        addr_type='单地址(0)',
        addr_len='2',
        sa_logic_value=0,
        bit5=0,
        logic_addr='86',
        comm_addr='1234',
        service_type='读取请求',
        service_data_type='无数据',
        service_priority='0',
        service_number=1,
        oad='60100000'
    )
    
    print("生成的测试帧:")
    print(" ".join(f"{b:02X}" for b in frame))
    print()
    
    # 解析验证
    result = parser.parse_frame(frame)
    print("解析结果:")
    for key, value in result.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    generate_test_frame()