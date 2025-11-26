#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试协议解析问题的脚本
"""

from protocol.protocol_698 import Protocol698

def test_protocol_parsing():
    """测试698.45协议解析"""
    
    # 用户提供的测试数据
    test_data = "fefefe682400c305010003072420100956850100200002000101031208ed1200001200000000e45b16"
    
    # 去掉起始符fefefe，协议解析需要从0x68开始
    hex_data = test_data.replace("fefefe", "")
    print(f"原始数据: {test_data}")
    print(f"去掉起始符后: {hex_data}")
    
    # 转换为字节
    try:
        frame_bytes = bytes.fromhex(hex_data)
        print(f"帧长度: {len(frame_bytes)} 字节")
        print(f"帧数据: {frame_bytes.hex().upper()}")
    except ValueError as e:
        print(f"数据转换错误: {e}")
        return
    
    # 创建协议解析器
    protocol = Protocol698()
    
    # 执行解析
    try:
        result = protocol.parse_frame(frame_bytes)
        print(f"\n=== 解析结果 ===")
        for key, value in result.items():
            print(f"{key}: {value}")
            
        # 检查控制域和SA标志是否存在
        print(f"\n=== 关键字段检查 ===")
        print(f"控制域存在: {'控制域' in result}")
        print(f"SA标志存在: {'SA标志' in result}")
        
        if '控制域' in result:
            control = result['控制域']
            print(f"控制域类型: {type(control)}")
            print(f"控制域内容: {control}")
            
        if 'SA标志' in result:
            sa_flag = result['SA标志']
            print(f"SA标志类型: {type(sa_flag)}")
            print(f"SA标志内容: {sa_flag}")
            
    except Exception as e:
        print(f"解析错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_protocol_parsing()