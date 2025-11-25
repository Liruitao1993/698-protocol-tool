from loguru import logger
import sys
import os
from datetime import datetime

class Logger:
    def __init__(self):
        # 创建日志目录
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 生成日志文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"protocol_test_{current_time}.log")
        
        # 配置日志格式
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        # 移除默认的处理器
        logger.remove()
        
        # 添加控制台处理器（仅当sys.stdout存在时）
        if sys.stdout is not None:
            logger.add(
                sys.stdout,
                format=log_format,
                level="INFO",
                colorize=True
            )
        
        # 添加文件处理器
        logger.add(
            log_file,
            format=log_format,
            level="DEBUG",
            rotation="500 MB",
            retention="30 days",
            encoding="utf-8"
        )
        
        self.logger = logger

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs) 