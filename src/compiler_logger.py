"""日志记录模块"""
import logging, colorlog
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

class CompilerLogger:
    def __init__(self):
        self._logger = None

    def setup_logger(
        self,
        name='compiler_logger',
        log_file='compiler.log',
        level=logging.DEBUG,         # 日志文件等级
        console_level=logging.INFO,  # 控制台日志等级
        max_bytes=5*1024*1024,  # 10MB
        backup_count=5,
        enable_console=True,
        enable_file=True,
        
    ):
        """日志记录器
        
        参数:
            name: 日志记录器名称
            log_file: 日志文件路径
            level: 日志级别
            console_level: 控制台日志级别
            max_bytes: 单个日志文件最大字节数
            backup_count: 保留的备份文件数量
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
        """
        # 创建日志记录器
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        
        # 避免重复添加handler
        if self._logger.handlers:
            return self._logger

        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 自定义日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 文件处理器（带日志轮转）保持无颜色
        if enable_file:
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)-8s] [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(level)
            self._logger.addHandler(file_handler)

        # 控制台处理器 - 使用彩色输出
        if enable_console:
            console_formatter = colorlog.ColoredFormatter(
                '%(log_color)s[%(asctime)s] [%(levelname)-8s] [%(filename)s:%(lineno)d]%(reset)s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                reset=True,
                log_colors={
                    'VERBOSE': 'cyan',
                    'DEBUG': 'blue',
                    'INFO': 'green',
                    'SUCCESS': 'bold_green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                },
                secondary_log_colors={},
                style='%'
            )
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(console_level)
            self._logger.addHandler(console_handler)

        self._add_custom_levels()

        return self._logger
    
    def _add_custom_levels(self):
        """添加自定义日志级别方法"""
        def verbose(msg, *args, **kwargs):
            if self._logger.isEnabledFor(logging.VERBOSE):
                self._logger._log(logging.VERBOSE, msg, args, **kwargs)

        def success(msg, *args, **kwargs):
            if self._logger.isEnabledFor(logging.SUCCESS):
                self._logger._log(logging.SUCCESS, msg, args, **kwargs)

        # 添加自定义级别
        logging.addLevelName(15, "VERBOSE")
        logging.addLevelName(25, "SUCCESS")
        logging.VERBOSE = 15
        logging.SUCCESS = 25

        # 绑定到logger实例
        self._logger.verbose = verbose
        self._logger.success = success

    def get_logger(self):
        """获取配置好的日志记录器"""
        if not self._logger:
            raise RuntimeError("Logger not initialized. Call setup_logger() first.")
        return self._logger

# 全局日志记录器实例
logger = CompilerLogger().setup_logger(
    log_file='logs/compiler.log',
    level=logging.DEBUG,
    console_level=logging.INFO
)