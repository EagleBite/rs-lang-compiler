"""语法分析树节点"""
from dataclasses import dataclass, field
from typing import Optional, List, Any
from compiler_lexer import LexicalElement   
from compiler_semantic_symbol import UnitType

@dataclass
class SynthesizedAttributes:
    """综合属性"""
    place: Optional[str] = None                             # 值存储位置(常量值或变量名称)
    type_obj: Optional[Any] = None                          # 类型对象(用于类型检查)
    is_lvalue: bool = False                                 # 是否可作为左值
    is_mutable: bool = False                                # 是否可变
    const_value: Optional[Any] = None                       # 常量值

    # 控制流相关
    quad_index: Optional[int] = None                        # 记录下一条未生成四元式的位置  
    true_list: List[int] = field(default_factory=list)      # 为真跳转目标
    false_list: List[int] = field(default_factory=list)     # 为假跳转目标
    next_list: List[int] = field(default_factory=list)      # 下一跳转目标
    break_list: List[int] = field(default_factory=list)     # 循环跳转目标
    continue_list: List[int] = field(default_factory=list)  # 循环继续跳转目标

    # 数据结构访问
    elements: Optional[dict] = None       # {'types':[Type], 'places':[str], 'const_values':[int]}]
    array_access: Optional[dict] = None   # {'name':str, 'index':str, 'elem_type':Type}                     
    tuple_access: Optional[dict] = None   # {'name':str, 'field_idx':int, 'field_type':Type}

    # 函数相关
    func_info: Optional[dict] = None      # {'func_name':str, 'params':[Type], 'ret_type':Type}
    call_info: Optional[dict] = None      # {'args':[str], 'arg_types':[Type], 'ret_temp':str}

class ParseNode:
    def __init__(
            self, 
            symbol: str, 
            children: Optional[List["ParseNode"]] = None, 
            token: Optional[LexicalElement] = None
            ):
        """
        语法分析树节点
        
        :param symbol: 节点符号(String)
        :param children: 子节点列表
        :param token: 关联的词法单元(对终结符节点)
        """
        self.symbol = symbol
        self.children = children if children is not None else []
        self.token = token

        # 终结符相关属性
        self.value = getattr(token, "value", None)
        self.line = getattr(token, "line", -1)
        self.column = getattr(token, "column", -1)

        self.last_return = False    # 判断最后一个语句是不是返回语句

        # 综合属性
        self.attributes: Optional[SynthesizedAttributes] = SynthesizedAttributes()
        
    def is_terminal(self):
        """判断是否为终结符节点"""
        return self.token is not None
    
    def add_child(self, child):
        """添加子节点"""
        self.children.append(child)
        return self

    def __str__(self):
        if self.token:
            return f"{self.symbol}({self.token.value})"
        return f"{self.symbol}[{len(self.children)}]"
    
    def __repr__(self):
        return f"<ParseNode {self.__str__()}>"
