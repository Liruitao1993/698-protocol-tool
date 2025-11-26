import sys
import os
# 添加上级目录到Python路径，以便正确导入protocol模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import Protocol698  # 此处应有表达式
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FrameParser:
    """
    698.45协议帧解析器
    封装Protocol698类，提供更易用的解析接口
    """
    
    def __init__(self):
        """
        初始化解析器
        """
        self.protocol = Protocol698()
        logger.info("698.45协议帧解析器初始化完成")
    
    def hex_str_to_bytes(self, hex_str):
        """
        将十六进制字符串转换为字节串
        
        Args:
            hex_str (str): 十六进制字符串，支持空格分隔
            
        Returns:
            bytes: 转换后的字节串
            
        Raises:
            ValueError: 无效的十六进制字符串
        """
        try:
            # 移除空格和换行符
            hex_str = hex_str.replace(' ', '').replace('\n', '').replace('\t', '')
            # 检查字符串长度是否为偶数
            if len(hex_str) % 2 != 0:
                raise ValueError("十六进制字符串长度必须为偶数")
            # 转换为字节串
            return bytes.fromhex(hex_str)
        except ValueError as e:
            logger.error(f"十六进制字符串转换失败: {e}")
            raise
    
    def validate_checksum(self, frame_bytes):
        """
        验证帧的校验和
        
        Args:
            frame_bytes (bytes): 完整的协议帧字节串
            
        Returns:
            bool: 校验和是否有效
        """
        try:
            if len(frame_bytes) < 10:
                logger.error("帧长度不足，无法验证校验和")
                return False
            
            # 计算HCS校验和
            hcs_pos = 7  # HCS位置：起始符(1) + 长度域(2) + 控制域(1) + SA标志(1) + SA地址(1) + CA地址(1)
            hcs_data = frame_bytes[1:hcs_pos]  # 从长度域到CA地址
            calculated_hcs = self.protocol.crc16(hcs_data)
            
            # 获取帧中的HCS
            frame_hcs = frame_bytes[hcs_pos] | (frame_bytes[hcs_pos+1] << 8)
            
            if calculated_hcs != frame_hcs:
                logger.error(f"HCS校验失败: 计算值={calculated_hcs:04X}, 帧中值={frame_hcs:04X}")
                return False
            
            # 计算FCS校验和
            fcs_pos = len(frame_bytes) - 3  # FCS位置：结束符前2字节
            fcs_data = frame_bytes[1:fcs_pos]  # 从长度域到时间标签
            calculated_fcs = self.protocol.crc16(fcs_data)
            
            # 获取帧中的FCS
            frame_fcs = frame_bytes[fcs_pos] | (frame_bytes[fcs_pos+1] << 8)
            
            if calculated_fcs != frame_fcs:
                logger.error(f"FCS校验失败: 计算值={calculated_fcs:04X}, 帧中值={frame_fcs:04X}")
                return False
            
            logger.info("校验和验证通过")
            return True
        except Exception as e:
            logger.error(f"校验和验证失败: {e}")
            return False
    
    def parse_response(self, frame_data):
        """
        解析698.45协议响应帧
        
        Args:
            frame_data (bytes or str): 协议帧数据，可以是字节串或十六进制字符串
            
        Returns:
            dict: 解析结果字典，包含帧的各个组成部分
            
        Raises:
            ValueError: 无效的帧数据格式
        """
        try:
            # 预处理：将十六进制字符串转换为字节串
            if isinstance(frame_data, str):
                frame_bytes = self.hex_str_to_bytes(frame_data)
            elif isinstance(frame_data, bytes):
                frame_bytes = frame_data
            else:
                raise ValueError("帧数据必须是字节串或十六进制字符串")
            
            logger.info(f"开始解析帧: {frame_bytes.hex(' ')}")
            
            # 验证校验和
            if not self.validate_checksum(frame_bytes):
                logger.warning("校验和验证失败，继续解析")
            
            # 调用Protocol698的parse_frame方法进行解析
            result = self.protocol.parse_frame(frame_bytes)
            
            # 后处理：添加原始帧信息
            result['原始帧'] = frame_bytes.hex(' ')
            
            # 检查解析结果是否有错误
            if 'error' in result:
                logger.error(f"帧解析失败: {result['error']}")
            else:
                logger.info("帧解析成功")
            
            return result
        except Exception as e:
            logger.error(f"解析响应帧时发生错误: {e}")
            return {'error': str(e)}
    
    def format_parse_result(self, parse_result):
        """
        格式化解析结果，便于输出和查看
        
        Args:
            parse_result (dict): 解析结果字典
            
        Returns:
            str: 格式化后的解析结果字符串
        """
        if 'error' in parse_result:
            return f"解析错误: {parse_result['error']}"
        
        formatted = []
        formatted.append("=" * 60)
        formatted.append("698.45协议帧解析结果")
        formatted.append("=" * 60)
        
        # 基本帧信息
        for key, value in parse_result.items():
            if isinstance(value, dict):
                formatted.append(f"\n{key}:")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        formatted.append(f"  {sub_key}:")
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            formatted.append(f"    {sub_sub_key}: {sub_sub_value}")
                    else:
                        formatted.append(f"  {sub_key}: {sub_value}")
            else:
                formatted.append(f"{key}: {value}")
        
        formatted.append("=" * 60)
        return "\n".join(formatted)

# 示例用法
if __name__ == "__main__":
    # 创建解析器实例
    parser = FrameParser()
    
    # 示例帧（十六进制字符串）
    example_frame = "682400c305010003072420100956850100200002000101031208eb1200001200000000fbff16"
    
    try:
        # 解析帧
        result = parser.parse_response(example_frame)
        
        # 格式化输出
        formatted_result = parser.format_parse_result(result)
        print(formatted_result)
    except Exception as e:
        print(f"解析失败: {e}")