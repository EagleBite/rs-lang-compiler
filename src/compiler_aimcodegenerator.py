from compiler_codegenerator import *
from compiler_parser import Parser
from compiler_semantic_symbol import SymbolTable, BaseType, VariableSymbol, FunctionSymbol, UnitType
from compiler_semantic_checker import SemanticChecker
from compiler_block_spilt import *
from compiler_rust_grammar import *
from compiler_logger import logger
from compiler_error_handler import ErrorException, ErrorCode
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

@dataclass
class StackVarInfo:
    """栈变量信息"""
    name: str                   # 变量名
    offset: int                 # 在栈帧中的偏移量
    is_in_memory: bool = False  # 是否在内存中（默认不在内存中）

class FunctionStackFrame:
    """函数栈帧信息"""
    def __init__(self, name: str = "", old_sp: int = 0, return_addr: int = 0,
                 param_num: int = 0, params: list = [tuple()],  # (参数名, 偏移量, is_in_memory) 
                 local_num: int = 0, local_vars: list = [tuple()]
                ):
        """
            初始化函数栈帧信息

        Args:
            name: 函数名
            old_sp: 调用前的栈指针
            return_addr: 返回地址
            params: 参数列表 [(name, offset)]
            local_vars: 局部变量列表 [(name, offset)]      
        """
        self.name = name
        self.old_sp = old_sp
        self.return_addr = return_addr

        self.param_num = param_num
        self.local_num = local_num
        self.params = params          # (参数名, 偏移量, is_in_memory)
        self.local_vars = local_vars  # (变量名, 偏移量, is_in_memory)
    
    def size(self) -> int:
        """计算栈帧总大小(Bytes)"""
        return (
            4 +                         # 返回地址
            4 * (self.param_num + 1) +  # 参数列表大小
            4 * (self.local_num + 1) +  # 局部变量大小
            8                           # 保留8字节
        )
    
    def get_var_offset(self, varname: str) -> Optional[int]:
        """获取变量在栈帧中的偏移量 用于访问内存 Memory """
        return next((offset for name, offset, _ in self.local_vars if name == varname), None)
    
    def set_var_memflag(self, varname: str, is_in_memory: bool):
        """设置变量是否在内存中"""
        for i, (name, offset, _) in enumerate(self.local_vars):
            if name == varname:
                self.local_vars[i] = (name, offset, is_in_memory)
                return
    
    def if_var_in_memory(self, varname: str):
        """检查变量是否在内存中"""
        return next((is_in_memory for name, _, is_in_memory in self.local_vars if name == varname), False)
    
class FunctionStack:
    """函数栈，存放所有函数的栈帧信息"""
    def __init__(self, symbolTable: SymbolTable):
        self.symbolTable = symbolTable              # 符号表，存储函数和变量信息
        self.frames: list[FunctionStackFrame] = []  # 栈帧列表，存放所有函数的栈帧信息
    
    def build_frame(self,func_name: str) -> FunctionStackFrame:
        """构建某个函数的栈帧信息"""
        scope = self.symbolTable.find_scope(func_name)          # 获取函数所在的作用域
        old_sp =  self.frames[-1].size() if self.frames else 0  # 获取old_sp，如果没有栈帧则为0
        return_addr = 0

        param_num = 0
        local_num = 0
        params = []
        local_vars = []
        offset = -4

        # 遍历函数作用域中的符号，获取参数和局部变量信息
        for symbol in scope.symbols.values():
            if isinstance(symbol, ParameterSymbol):
                param_num += 1
                params.append((symbol.name, -4 * (param_num + 1) + offset))

            elif isinstance(symbol, VariableSymbol):
                local_num += 1
                local_vars.append((symbol.name, -4 * (param_num + 1) - 4 * (local_num + 1) + offset, False))
        
        # 创建栈帧对象
        frame = FunctionStackFrame(func_name, old_sp, return_addr, param_num, params, local_num, local_vars)
        self.frames.append(frame)

        return frame
        
    def get_frame(self, name: str) -> Optional[FunctionStackFrame]:
        """获取某个函数的栈帧信息"""
        for frame in self.frames:
            if frame.name == name:
                return frame
            
        return None
    
class MemController():
    """内存分配控制器"""
    def __init__(self, function_stack: FunctionStack = None):
        """初始化内存控制器"""
        TEMP_REGS = [f"$t{i}" for i in range(10)]  # $t0-$t9 临时寄存器
        SAVE_REGS = [f"$s{i}" for i in range(8)]   # $s0-$s7 保存寄存器
        ARG_REGS  = [f"$a{i}" for i in range(4)]   # $a0-$a3 参数寄存器
        RET_REG   = [f"$v{i}" for i in range(2)]   # $v0-$v1 返回值寄存器
        SP_REG    = "$sp"                          # $sp 栈顶指针寄存器
        RA_REG    = "$ra"                          # $ra 返回地址寄存器

        # 寄存器池     
        self.varregs = TEMP_REGS + SAVE_REGS # 可用于变量分配的寄存器
        self.pararegs = ARG_REGS             # 参数传递专用寄存器
        self.retregs = RET_REG               # 返回值寄存器
        self.spreg = SP_REG                  # 栈顶指针寄存器
        self.rareg = RA_REG                  # 返回地址寄存器

        # 寄存器分配状态
        self.rvalues: Dict[tuple[str,str], str] = {}  # 变量寄存器映射 {(函数名,变量名): 寄存器}
        self.usedregs: Set[str] = set()               # 当前已占用的寄存器集合
        self.valregs: list = self.varregs.copy()      # 可用寄存器池

        # 变量使用位置追踪
        self.var_use_pos: Dict[str, list] = {}  # 变量名 -> [使用位置列表]
                                                # 使用位置格式: (函数名, 基本块索引, 四元式索引)
        # 关联的函数栈管理器
        self.function_stack: Optional[FunctionStack] = function_stack
        
    def get_live_vars_after(self, cur_pos: tuple[str, int, int]) -> list[str]:
        """
            返回在当前四元式位置之后还会被用到的变量名列表(在当前函数中)

        Args:
            cur_pos: 当前四元式位置 (函数名, 基本块索引, 四元式索引)
        """
        func_name = cur_pos[0]
        live_vars = []

        # 如果变量在当前位置之后还会被使用且位于寄存器中，则认为它是活跃的
        # 遍历所有变量的使用位置
        for var, use_list in self.var_use_pos.items():
            if (var != '$ret_reg' and                                          # 排除返回寄存器
                (func_name, var) in self.rvalues and                           # 先检查变量是否在寄存器中
                any(pos[0] == func_name and pos > cur_pos for pos in use_list) # 再检查变量位于的使用位置是否在当前位置之后
            ):
                live_vars.append(var)

        return live_vars

    def alloc_reg(self, varname: str, cur_pos: tuple, code: list) -> str:
        """
            为变量分配寄存器
        
        Args:
            varname: 需要分配的变量名
            cur_pos: 当前位置 (函数名, 基本块索引, 四元式索引)
            code: 生成的指令列表 (用于插入spill代码)
        
        Returns:
            str: 分配到的寄存器名

        算法步骤:
            1. 检查变量是否已经在寄存器中，如果是，直接返回对应寄存器名
            2. 检查是否有空闲寄存器，如果有，直接分配一个空闲寄存器
            3. 如果没有空闲寄存器，选择“下次使用最远”的变量进行寄存器让渡
            --| 3.1. 如果被让渡的变量在当前函数之后再也不会用到，则不需要保存到内存
            --| 3.2. 如果被让渡的变量在当前函数之后还会用到，则需要将其保存到内存
        """
        # 1. 如果变量已在寄存器中，直接返回
        func_name = cur_pos[0]
        key = (func_name, varname)

        # ---- 情况1：变量已有寄存器 ----
        if key in self.rvalues:
            return self.rvalues[key]

        # ---- 情况2：有空闲寄存器 ----
        free_regs = [r for r in self.valregs if r not in self.usedregs]
        if free_regs:
            reg = free_regs[0]
            self.rvalues[key] = reg
            self.usedregs.add(reg)

        # ---- 情况3：需要寄存器让渡 ----
        else:
            # 寻找"下次使用最远"的牺牲变量
            farthest_next = None     # (函数名, 块索引, 四元式索引)
            victim_var = None        # 被牺牲的变量名
            victim_func = None       # 被牺牲的函数名

            # 遍历所有已分配寄存器的变量，找到下次使用最远的变量
            for (alloc_func, alloc_var), reg in self.rvalues.items():
                use_list = self.var_use_pos.get(alloc_var, [])
                next_use = next((pos for pos in use_list if pos >= cur_pos), None)

                if next_use is None:
                    victim_var, victim_func = alloc_var, alloc_func
                    break  # 找到最佳牺牲者，立即终止，不再需要比较
                elif not farthest_next or next_use > farthest_next:
                    victim_var, victim_func, farthest_next = alloc_var, alloc_func, next_use
            
            # 获取牺牲变量的寄存器
            reg = self.rvalues[(victim_func, victim_var)]

            # 如果牺牲的变量在当前函数之后还会被用到，需要保存到内存
            # 如果牺牲的寄存器是其他函数的变量，因为在call时已保存，所以无需进行保存
            # 如果牺牲的变量在当前函数之后再也不会用，所以也无需进行保存
            if victim_func == func_name and victim_var in self.get_live_vars_after(cur_pos):
                if self.function_stack:
                    frame = self.function_stack.get_frame(victim_func)           # 获取当前函数的栈帧
                    offset = frame.get_var_offset(victim_var) if frame else None # 获取变量在栈帧中的偏移量
                    
                    # 如果偏移量不为None，说明变量在栈帧中
                    if offset is not None:
                        frame.set_var_memflag(victim_var, True)  # 标记为在内存中
                        code.append(f"    sw {reg}, {offset}({self.spreg}) # <寄存器溢出> 将 {victim_var} 的值从寄存器 {reg} 保存到 {victim_func} 函数的栈帧偏移位置 {offset}")

            # 释放被牺牲的寄存器，并分配给新变量
            del self.rvalues[(victim_func, victim_var)]
            self.usedregs.discard(reg)
            self.rvalues[key] = reg
            self.usedregs.add(reg)    

        return self.rvalues[key]
    
class AimCodeGenerator:
    """"目标代码生成器"""
    def __init__(self, quads: list, symbolTable: SymbolTable):
        """
            初始化目标代码生成器

        Args:
            quads (list): 四元式序列
            symbolTable (SymbolTable): 符号表，存储变量和函数的信息
        """
        # 初始化四元式和符号表
        self.quads = quads
        self.symbolTable = symbolTable

        # 初始化生成的目标代码相关属性
        self.labels: Dict[str, list[str]] = {}  # 存储函数标签
        self.code: List[str] = []               # 生成的目标代码

        # 初始化各个控制器
        self.block_controller = BlockController(quads, symbolTable)
        self.function_stack = FunctionStack(symbolTable)
        self.mem_controller = MemController(self.function_stack)

        self.build_var_use_pos()
        
    def build_var_use_pos(self):
        """统计每个变量的所有使用位置，赋值给 self.mem_controller.var_use_pos"""
        var_use_pos = defaultdict(list)

        for func_name, blocks in self.block_controller.func_blocks.items():
            for block_idx, block in enumerate(blocks):
                for quad_idx, (idx, quad) in enumerate(block):
                    # 获取四元式所有操作数(过滤None和非字符串)
                    operands = filter(None, [
                        getattr(quad, 'arg1', None),
                        getattr(quad, 'arg2', None), 
                        getattr(quad, 'result', None)
                    ])
                    for var in (v for v in operands if isinstance(v, str)):
                        var_use_pos[var].append((func_name, block_idx, quad_idx))
        
        # 更新内存控制器的变量使用位置
        self.mem_controller.var_use_pos = var_use_pos
        
    def quad_to_code(self, quad_with_index: tuple[int, Quadruple], cur_pos: Tuple[str, int, int]) -> List[str]:
        """
            将四元式转换为目标代码

        Args:
            quad: 四元式对象
            cur_pos: 当前四元式位置 (函数名, 基本块索引, 四元式索引)
        """
        code = []                                        # 生成的目标代码列表
        index, quad = quad_with_index                    # 解包四元式和索引
        op, arg1, arg2, result = quad                    # 四元式的操作符和操作数

        func_name = cur_pos[0]                           # 获取当前函数名
        frame = self.function_stack.get_frame(func_name) # 获取当前函数的栈帧

        # 参数调用
        if op == 'param':
            # 提取参数索引（从result中解析param1/param2等）
            param_num = next((int(c) for c in result if c.isdigit()), None)

            # 参数有效性检查
            if param_num is None or param_num < 1:
                raise ErrorException(
                    message=f"无效的参数寄存器格式: {result} (当前仅支持param1~param4)", 
                    error_code=ErrorCode.InvalidParamRegisterFormat
                )
            
            # 参数寄存器范围检查
            if param_num > 4:
                raise ErrorException(
                    message=f"参数寄存器 {result} 超出范围 (当前仅支持至多4个参数传递)", 
                    error_code=ErrorCode.PARAM_LIMIT
                )
            
            # 获取目标寄存器
            target_reg = self.mem_controller.pararegs[param_num - 1]  # 获取目标寄存器

            if isinstance(arg1, str):
                src_reg = self.mem_controller.alloc_reg(arg1, cur_pos, code=code)
                self.mem_controller.rvalues[(f'param{param_num}', arg1)] = target_reg
                code.append(f"    add {target_reg}, {src_reg}, $zero  # 将参数 {arg1} 存入寄存器 {target_reg}")
            elif isinstance(arg1, int):
                self.mem_controller.rvalues[(f'param{param_num}', arg1)] = target_reg
                code.append(f"    li {target_reg}, {arg1}  # 将常量 {arg1} 存入寄存器 {target_reg}")       
            else:
                raise ErrorException(
                    message=f"无效的参数类型: {arg1}",
                    error_code=ErrorCode.GENERAL_ERROR,
                    fix_suggestion="参数只能是变量名或立即数"
                )
        
        # 调用函数
        elif op == 'call':
            # 函数调用前保护寄存器状态
            live_vars = self.mem_controller.get_live_vars_after(cur_pos)
            code.append(f"    # 函数调用保护寄存器状态")
            for var in live_vars:
                offset = frame.get_var_offset(var) if frame else None
                if offset is not None:
                    reg = self.mem_controller.rvalues.get((func_name, var), None)
                    code.append(f"    sw {reg}, {offset}({self.mem_controller.spreg})  # 保存变量 {var} 到栈帧")

            # 函数调用前分配栈帧空间
            if frame:
                code.append(f"    sw {self.mem_controller.spreg}, -{frame.size()}({self.mem_controller.spreg})  # 保存旧的栈顶指针")
                code.append(f"    addi {self.mem_controller.spreg}, {self.mem_controller.spreg}, -{frame.size()}  # 分配栈帧空间")
                code.append(f"    sw {self.mem_controller.rareg}, {-4}({self.mem_controller.spreg})  # 保存返回地址")
            
            # 调用函数
            code.append(f"    jal {arg1}  # 调用函数 {arg1}")
            
            # 函数调用后恢复寄存器状态
            code.append(f"    lw {self.mem_controller.rareg}, {-4}({self.mem_controller.spreg})  # 恢复返回地址")
            if frame:
                code.append(f"    addi {self.mem_controller.spreg}, {self.mem_controller.spreg}, {frame.size()}  # 恢复栈顶指针")
                for var in live_vars:
                    offset = frame.get_var_offset(var) if frame else None
                    if offset is not None:
                        reg = self.mem_controller.rvalues.get((func_name, var), None)
                        code.append(f"    lw {reg}, {offset}({self.mem_controller.spreg})  # 恢复变量 {var} 从栈帧")

        elif op in ('+', '-', '*', '/', '<', '<=', '>', '>=', '==', '!='):
            # 操作符到指令的映射
            op_info = {
                # 算术运算
                '+': {'inst': 'add', 'imm_inst': 'add',  'calc': lambda a,b: a + b},
                '-': {'inst': 'sub', 'imm_inst': 'sub',  'calc': lambda a,b: a - b},
                '*': {'inst': 'mul', 'imm_inst': 'mul',  'calc': lambda a,b: a * b},
                '/': {'inst': 'div', 'imm_inst': 'div',  'calc': lambda a,b: a // b, 'zero_check': True},

                # 比较运算
                '<':  {'inst': 'slt', 'imm_inst': 'slt', 'calc': lambda a,b: a < b},
                '<=': {'inst': 'sle', 'imm_inst': 'sle', 'calc': lambda a,b: a <= b},
                '>':  {'inst': 'sgt', 'imm_inst': 'sgt', 'calc': lambda a,b: a > b},
                '>=': {'inst': 'sge', 'imm_inst': 'sge', 'calc': lambda a,b: a >= b},
                '==': {'inst': 'seq', 'imm_inst': 'seq', 'calc': lambda a,b: a == b},
                '!=': {'inst': 'sne', 'imm_inst': 'sne', 'calc': lambda a,b: a != b}
            }
            info = op_info[op]
            result_reg = self.mem_controller.alloc_reg(result, cur_pos, code=code)

            # 1. 处理两个立即数的情况
            if isinstance(arg1, int) and isinstance(arg2, int):
                if op == '/' and arg2 == 0:
                    raise ValueError("Division by zero")
                
                code.append(f"    li {result_reg}, {info['calc'](arg1, arg2)}  # 计算 {arg1} {op} {arg2}")
            
            # 2. 处理变量与立即数的混合运算
            elif (isinstance(arg1, str) and isinstance(arg2, int)) or (isinstance(arg1, int) and isinstance(arg2, str)):
                is_var_first = isinstance(arg1, str)
                var, const = (arg1, arg2) if is_var_first else (arg2, arg1)

                # 除法零检查
                if info.get('zero_check') and is_var_first and const == 0:
                    raise ValueError("除0异常: 除数不能为0")

                # 加载变量寄存器
                var_reg = self.mem_controller.alloc_reg(var, cur_pos, code=code)
                if frame and frame.if_var_in_memory(var):
                    code.append(f"    lw {var_reg}, {frame.get_var_offset(var)}({self.mem_controller.spreg})  # 加载 {var}")
                code.append(f"    li {result_reg}, {const}  # 加载常量 {const}") # 统一先加载常量到结果寄存器
                if is_var_first:
                    code.append(f"    {info['imm_inst']} {result_reg}, {var_reg}, {result_reg}  # {var} - {const}")
                else:
                    code.append(f"    {info['imm_inst']} {result_reg}, {result_reg}, {var_reg}  # {const} - {var}")
            
            # 3. 处理两个变量的情况
            elif isinstance(arg1, str) and isinstance(arg2, str):
                reg1 = self.mem_controller.alloc_reg(arg1, cur_pos, code=code)
                reg2 = self.mem_controller.alloc_reg(arg2, cur_pos, code=code)

                # 处理内存中的变量
                for var, reg in [(arg1, reg1), (arg2, reg2)]:
                    if frame and frame.if_var_in_memory(var):
                        code.append(f"    lw {reg}, {frame.get_var_offset(var)}({self.mem_controller.spreg})  # 加载 {var}")

                code.append(f"    {info['inst']} {result_reg}, {reg1}, {reg2}  # {arg1} {op} {arg2} -> {result}")

            else:
                raise ValueError(f"Unsupported operands for {op}: {arg1}, {arg2}")

        # 无条件跳转
        elif op == 'j':
            func_name_jmp, block_idx = self.block_controller.get_scope_by_index(result)
            if func_name_jmp is None or block_idx is None:
                raise ValueError(f"Jump target {result} not found")
            code.append(f"    j {func_name_jmp}_block_{block_idx}  # 跳转到函数 {func_name_jmp} 的基本块 {block_idx}")

        # 条件跳转（不等于）
        elif op == 'jnz':
            reg = self.mem_controller.alloc_reg(arg1, cur_pos, code=code)
            func_name_jmp, block_idx = self.block_controller.get_scope_by_index(result)
            if func_name_jmp is None or block_idx is None:
                raise ValueError(f"Jump target {result} not found")
            code.append(f"    bne {reg}, $zero, {func_name_jmp}_block_{block_idx}  # 如果 {arg1} != 0 跳转到 {func_name_jmp}_block_{block_idx}")

        # 赋值跳转
        elif op == '=':
            if isinstance(arg1, int):
                reg = self.mem_controller.alloc_reg(result, cur_pos, code=code)
                code.append(f"    li {reg}, {arg1}  # 将常量 {arg1} 赋值给 {result}")
            elif isinstance(arg1, str):
                if arg1 == '$ret_reg':
                    result_reg = self.mem_controller.alloc_reg(result, cur_pos, code=code)
                    code.append(f"    add {result_reg}, {self.mem_controller.retregs[0]}, $zero  # 将返回寄存器的值赋给 {result}")
                else:
                    reg = self.mem_controller.alloc_reg(arg1, cur_pos, code=code)
                    if frame and frame.if_var_in_memory(arg1):
                        code.append(f"    lw {reg}, {frame.get_var_offset(arg1)}({self.mem_controller.spreg})  # 加载参数 {arg1} 到寄存器")
                    result_reg = self.mem_controller.alloc_reg(result, cur_pos, code=code)
                    code.append(f"    add {result_reg}, {reg}, $zero  # 将 {arg1} 的值赋给 {result}")
            else:
                raise ValueError(f"Unsupported assignment: {arg1} to {result}")

        # 返回操作
        elif op == 'RETURN':
            func_name_ret, _ = self.block_controller.get_scope_by_index(index=index)
            if func_name_ret == "main":
                code.append("    li $v0, 10  # syscall: exit")
                code.append("    syscall")
            else:
                if isinstance(arg1, str):
                    return_reg = self.mem_controller.retregs[0]
                    reg = self.mem_controller.alloc_reg(arg1, cur_pos, code=code)
                    code.append(f"    add {return_reg}, {reg}, $zero  # 将 {arg1} 的值作为返回值")
                    code.append(f"    jr $ra  # 返回到调用点")
                elif isinstance(arg1, int):
                    return_reg = self.mem_controller.retregs[0]
                    code.append(f"    li {return_reg}, {arg1}  # 将常量 {arg1} 作为返回值")
                    code.append(f"    jr $ra  # 返回到调用点")
                elif arg1 is None:
                    code.append(f"    jr $ra  # 无返回值，直接返回")
                else:
                    raise ValueError(f"Unsupported return value: {arg1}")
            code.append("     ")

        return code
            
    def create_label(self, func_name: str, block_idx: int) -> str:
        """创建基本块标签"""
        return f"{func_name}_block_{block_idx}"
            
    def generate_code(self):
        """生成目标代码"""
        
        # 生成.data段(没有全局变量和常量，因此为空)
        self.code.append(".data")
        self.code.append("     ")
        # 生成.text段
        self.code.append(".text")
        self.code.append(".globl main")
        self.code.append("     ")
        
        # 按函数处理四元式
        for func_name, blocks in self.block_controller.func_blocks.items():
            frame = self.function_stack.build_frame(func_name) # 创建函数栈帧
            self.code.append(f"{func_name}:")
            self.labels[func_name] = []

            # 处理函数参数
            for i, param in enumerate(frame.params):
                # 把寄存器中存在(parami, xxx)的parami改成func_name
                for key in list(self.mem_controller.rvalues.keys()):
                    if key[0] == f'param{i+1}':
                        temp = self.mem_controller.rvalues[key]
                        self.mem_controller.rvalues[(func_name, param[0])] = temp
                        del self.mem_controller.rvalues[key]
                        break  # 一般只会有一个，找到就可以break
            
            # 根据基本块划分生成函数标签
            for block_idx, block in enumerate(blocks):
                label = self.create_label(func_name, block_idx)
                self.labels[func_name].append(label)
                self.code.append(f"{label}:")
                
                # 处理每个基本块中的四元式
                for q_idx, (quad_idx, quad) in enumerate(block):
                    cur_pos = (func_name, block_idx, q_idx)
                    code_lines = self.quad_to_code((quad_idx, quad), cur_pos)
                    self.code.extend(code_lines)
    