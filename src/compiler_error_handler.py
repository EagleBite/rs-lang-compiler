from enum import IntEnum
from typing import List, Tuple, Optional, Dict
from compiler_codegenerator import Quadruple

class ErrorCode(IntEnum):
    """
        错误代码枚举
        格式: 0xTTSS (T=类型, S=子码)

        错误大类：
        - 0x1xxx: 语法错误
        - 0x2xxx: 类型错误  
        - 0x3xxx: 符号错误
        - 0x4xxx: 运行时错误
        - 0x5xxx: 限制类警告（非致命）
        - 0x9xxx: 系统错误
    """
    # 通用错误 (0x0xxx)
    GENERAL_ERROR         = 0x0001  # 通用错误

    # 系统错误 (保留0x9xxx)
    UNKNOWN_ERROR         = 0x9001  # 未知错误
    INTERNAL_COMPILER_ERR = 0x9002  # 编译器内部错误

    # 语法错误(0x10xx)
    SYNTAX_ERROR          = 0x1001  # 通用语法错误
    INVALID_PARAM_FORMAT  = 0x1002  # 参数格式错误
    MISSING_SEMICOLON     = 0x1003  # 缺少分号
    UNEXPECTED_TOKEN      = 0x1004  # 意外符号

    # 类型错误 (0x2xxx)  
    TYPE_MISMATCH         = 0x2001  # 类型不匹配
    INVALID_CAST          = 0x2002  # 无效类型转换
    ARRAY_TYPE_VIOLATION  = 0x2003  # 数组类型违规

    # 符号错误 (0x3xxx)
    UNDEFINED_SYMBOL      = 0x3001  # 未定义符号（通用）
    UNDEFINED_VARIABLE    = 0x3002  # 未定义变量
    UNDEFINED_FUNCTION    = 0x3003  # 未定义函数  
    DUPLICATE_SYMBOL      = 0x3004  # 符号重复定义

    # 运行时错误 (0x4xxx)
    DIVISION_BY_ZERO      = 0x4001  # 除以零
    OUT_OF_MEMORY         = 0x4002  # 内存溢出
    STACK_OVERFLOW        = 0x4003  # 栈溢出
    INVALID_ARGUMENTS     = 0x4004  # 无效参数

    # 限制类警告 (0x5xxx) - 非致命
    PARAM_LIMIT           = 0x5001  # 参数限制警告
    DEPRECATED_FEATURE    = 0x5002  # 弃用功能警告
    RECURSION_DEPTH       = 0x5003  # 递归深度警告

    @property
    def chinese_description(self) -> str:
        """获取错误代码的中文描述"""
        category_prefix = {
            0x0000: "[通用]",
            0x1000: "[语法]",
            0x2000: "[类型]", 
            0x3000: "[符号]",
            0x4000: "[运行时]",
            0x5000: "[限制]",
            0x9000: "[系统]"
        }.get(self.value & 0xF000, "")

        descriptions: Dict[ErrorCode, str] = {
            # 通用错误
            self.GENERAL_ERROR: "通用错误",

            # 系统错误
            self.UNKNOWN_ERROR: "未知错误",
            self.INTERNAL_COMPILER_ERR: "编译器内部错误",
            
            # 语法错误
            self.SYNTAX_ERROR: "语法错误",
            self.INVALID_PARAM_FORMAT: "无效的参数格式",
            self.MISSING_SEMICOLON: "缺少分号",
            self.UNEXPECTED_TOKEN: "意外的符号",
            
            # 类型错误
            self.TYPE_MISMATCH: "类型不匹配",
            self.INVALID_CAST: "无效的类型转换", 
            self.ARRAY_TYPE_VIOLATION: "数组类型违规",
            
            # 符号错误
            self.UNDEFINED_SYMBOL: "未定义的符号",
            self.UNDEFINED_VARIABLE: "未定义的变量",
            self.UNDEFINED_FUNCTION: "未定义的函数",
            self.DUPLICATE_SYMBOL: "重复定义的符号",
            
            # 运行时错误
            self.DIVISION_BY_ZERO: "除以零错误",
            self.OUT_OF_MEMORY: "内存不足",
            self.STACK_OVERFLOW: "栈溢出",
            self.INVALID_ARGUMENTS: "无效的函数参数",
            
            # 限制警告
            self.PARAM_LIMIT: "参数数量超过限制",
            self.DEPRECATED_FEATURE: "使用了已弃用的功能",
            self.RECURSION_DEPTH: "递归深度超过安全限制"
        }

        return f"{category_prefix}{descriptions.get(self, '未定义的错误代码')}"
    
    @classmethod
    def get_category(cls, code: int) -> str:
        """获取错误大类名称"""
        return {
            0x1000: "Syntax",
            0x2000: "Type",
            0x3000: "Symbol",
            0x4000: "Runtime",
            0x5000: "Limitation",
            0x9000: "System"
        }.get(code & 0xF000, "Unknown")
    
    @property
    def is_fatal(self) -> bool:
        """是否为致命错误(限制类警告返回False)"""
        return (self.value & 0xF000) != 0x5000

class ErrorException(Exception):
    """自定义错误异常类"""
    def __init__(
            self, 
            message: str, 
            error_code: ErrorCode = ErrorCode.GENERAL_ERROR,
            code_location: Optional[Tuple[str, int]] = None,
            fix_suggestion: Optional[str] = None
        ):
        """
        Args:
            message: 错误描述
            error_code: 错误分类枚举值
            code_location: (文件名, 行号) 元组
            fix_suggestion: 可选的修复建议
        """
        self.message = message
        self.error_code = error_code
        self.code_location = code_location
        self.fix_suggestion = fix_suggestion
        super().__init__(self._format_chinese_message())

    def _format_chinese_message(self):
        """
            格式化错误信息（包含上下文和修复建议）
        
        输出格式：
            [错误类型] 错误描述
            位置: 文件名:行号
            上下文: 四元式详情
            建议修复: 具体建议
        """
        lines = [
            f"{self.error_code.chinese_description}: {self.message}"
        ]

        if self.code_location:
            file, line = self.code_location
            lines.append(f"  位置: {file}:{line}")

        if self.fix_suggestion:
            lines.append(f"  建议修复: {self.fix_suggestion}")

        # 添加分割线
        if len(lines) > 1:
            lines.insert(1, "  " + "-"*30)

        return "\n".join(lines)