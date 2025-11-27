import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from protocol.protocol_698 import Protocol698

print('开始测试协议解析...')

# 创建协议实例
protocol = Protocol698()
print('协议实例创建成功')

# 测试数据 - 控制域C3H，SA标志05H
test_frame = '68 13 00 C3 05 01 00 03 07 24 20 10 09 56 85 01 00 20 00 02 00 01 01 03 12 08 EB 12 00 00 12 00 00 00 00 FB FF 16'
test_frame = test_frame.replace(' ', '')

print('测试帧:', test_frame)
frame_bytes = bytes.fromhex(test_frame)
print('帧长度:', len(frame_bytes))

# 解析帧
print('开始解析帧...')
result = protocol.parse_frame(frame_bytes)

print('解析结果类型:', type(result))
if isinstance(result, dict):
    print('解析结果键:', list(result.keys()))
    
    if 'error' in result:
        print('解析错误:', result['error'])
    else:
        print()
        print('=== 698.45协议解析结果 ===')
        if '控制域' in result:
            print('控制域原始值:', result['控制域']['原始值'])
            print('  传输方向:', result['控制域']['D7-传输方向'])
            print('  启动标志:', result['控制域']['D6-启动标志'])
            print('  分帧标志:', result['控制域']['D5-分帧标志'])
            print('  数据域标志:', result['控制域']['D4-数据域标志'])
            print('  功能码:', result['控制域']['D2-D0-功能码'])
        
        if 'SA标志' in result:
            print('SA标志原始值:', result['SA标志']['原始值'])
            print('  地址类型:', result['SA标志']['D7-D6-地址类型'])
            print('  扩展逻辑地址:', result['SA标志']['D5-扩展逻辑地址'])
            print('  逻辑地址标志:', result['SA标志']['D4-逻辑地址标志'])
            print('  地址长度:', result['SA标志']['D3-D0-地址长度'])
        print('=== 解析完成 ===')
else:
    print('解析结果:', result)