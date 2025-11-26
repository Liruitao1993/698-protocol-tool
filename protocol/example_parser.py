#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
698.45协议帧解析器示例代码
展示如何使用FrameParser类解析698.45协议帧
"""

from protocol.frame_parser import FrameParser

def main():
    """
    示例代码主函数
    """
    print("=" * 60)
    print("698.45协议帧解析器示例")
    print("=" * 60)
    
    # 1. 初始化解析器
    parser = FrameParser()
    print("解析器初始化完成")
    print()
    
    # 2. 示例1：解析十六进制字符串格式的帧
    print("示例1：解析十六进制字符串格式的帧")
    print("-" * 60)
    
    # 示例帧（十六进制字符串）
    hex_frame = "68 0E 00 43 01 00 01 00 00 05 01 00 00 00 00 00 00 16"
    print(f"原始帧（十六进制字符串）：{hex_frame}")
    
    # 解析帧
    result = parser.parse_response(hex_frame)
    
    # 格式化输出解析结果
    formatted_result = parser.format_parse_result(result)
    print(formatted_result)
    print()
    
    # 3. 示例2：解析字节串格式的帧
    print("示例2：解析字节串格式的帧")
    print("-" * 60)
    
    # 示例帧（字节串）
    byte_frame = bytes.fromhex("680E00430100010000050100000000000016")
    print(f"原始帧（字节串）：{byte_frame}")
    
    # 解析帧
    result2 = parser.parse_response(byte_frame)
    
    # 格式化输出解析结果
    formatted_result2 = parser.format_parse_result(result2)
    print(formatted_result2)
    print()
    
    # 4. 示例3：解析不同服务类型的帧
    print("示例3：解析不同服务类型的帧")
    print("-" * 60)
    
    # GET-Request响应帧
    get_frame = "68 16 00 83 01 00 01 00 00 05 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 16"
    print(f"GET-Request响应帧：{get_frame}")
    
    # 解析帧
    get_result = parser.parse_response(get_frame)
    
    # 格式化输出解析结果
    formatted_get_result = parser.format_parse_result(get_result)
    print(formatted_get_result)
    print()
    
    # 5. 示例4：错误处理
    print("示例4：错误处理")
    print("-" * 60)
    
    # 无效的帧（起始符错误）
    invalid_frame = "69 0E 00 43 01 00 01 00 00 05 01 00 00 00 00 00 00 16"
    print(f"无效帧（起始符错误）：{invalid_frame}")
    
    # 解析帧
    invalid_result = parser.parse_response(invalid_frame)
    
    # 格式化输出解析结果
    formatted_invalid_result = parser.format_parse_result(invalid_result)
    print(formatted_invalid_result)
    print()
    
    print("=" * 60)
    print("示例结束")
    print("=" * 60)

if __name__ == "__main__":
    main()
