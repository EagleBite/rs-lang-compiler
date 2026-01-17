"""中间代码生成器"""
from dataclasses import dataclass
from typing import Optional, Dict, List, Union, Tuple
from compiler_logger import logger

@dataclass
class Quadruple:
    """四元式(纯数据结构)"""
    op: str                              # 操作类型
    arg1: Union[str, int, float, None]   # 左操作数
    arg2: Union[str, int, float, None]   # 右操作数
    result: str                          # 结果存储位置

    def __iter__(self):
        return iter((self.op, self.arg1, self.arg2, self.result))

    def __str__(self):
        args = [str(self.arg1) if self.arg1 is not None else 'None',
                str(self.arg2) if self.arg2 is not None else 'None']
        return f"[{self.op},{args[0]},{args[1]},{self.result}]"

class IntermediateCodeGenerator:
    """中间代码生成器(生成四元式)"""
    def __init__(self):
        self.quads = []             # 生成的四元式
        self.next_quad = 0          # 指向下一条将要产生但尚未形成的四元式的地址(标号)
        self.temp_counter = 0       # 临时变量的数量
        self.label_counter = 0      # 标签的数量

    def reset(self):
        self.quads = []             # 生成的四元式
        self.next_quad = 0          # 指向下一条将要产生但尚未形成的四元式的地址(标号)
        self.temp_counter = 0       # 临时变量的数量
        self.label_counter = 0      # 标签的数量

    def new_temp(self):
        """Generate a new temporary variable name"""
        temp = f"t{self.temp_counter}"
        self.temp_counter += 1
        return temp
    
    def new_label(self):
        """Generate a new label name"""
        label = f"L{self.label_counter}"
        self.label_counter += 1
        return label
    
    def emit(self, op, arg1, arg2, result):
        """Emit a new quadruple and add it to the list"""
        logger.debug(f"Emitting quadruple: OP='{op}', ARG1='{arg1}', ARG2='{arg2}', RESULT='{result}'")
        quad = Quadruple(op, arg1, arg2, result)
        self.quads.append(quad)
        self.next_quad = len(self.quads)
        return self.next_quad - 1
    
    def backpatch(self, list_to_patch, label):
        """回填"""
        for idx in list_to_patch:
            self.quads[idx].result = label

    def merge_lists(self, *lists: list[int]) -> list[int]:
        """合并任意数量的四元式索引列表"""
        merged = []
        for lst in lists:
            if not isinstance(lst, list):
                raise TypeError(f"Expected list, got {type(lst).__name__}")
            merged.extend(lst)  # 使用extend而非+，避免临时列表创建
        return merged