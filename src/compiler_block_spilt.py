from compiler_semantic_symbol import SymbolTable, BaseType, VariableSymbol, FunctionSymbol, UnitType, ParameterSymbol
from compiler_rust_grammar import *
from compiler_codegenerator import Quadruple
from compiler_logger import logger
from typing import Dict

class BlockController:
    """控制基本块划分和分析"""
    def __init__(self, quads: list[tuple[int, Quadruple]], symbolTable: SymbolTable):
        # 基础数据
        self.quads = quads              # 全局四元式列表(带有序号idx)
        self.symbolTable = symbolTable  # 全局符号表

        logger.debug("初始化基本块划分分析结果...")
        self._initialize_analysis()  # 初始化分析结果
        logger.debug("基本块划分分析结果初始化完成")

    def _initialize_analysis(self):
        """初始化分析结果"""
        self.func_entries: Dict[str, int] = self._get_function_entry()
        self.func_vars: Dict[str, set] = self._get_function_vars()
        self.func_blocks: Dict[str, list] = self._split_all_functions()

        self.func_cfgs: Dict[str, Dict[int, list[int]]] = {
            f_name: self._build_cfg(blocks) 
            for f_name, blocks in self.func_blocks.items()
        }

        self.live_vars: Dict[str, tuple[list[set[str]], list[set[str]]]] = {
            f_name: self._live_variable_analysis(
                blocks, 
                self.func_cfgs[f_name], 
                self.func_vars[f_name]
            )
            for f_name, blocks in self.func_blocks.items()
        }
        
    
    def get_funcname_by_entry(self, entry_idx: int) -> str:
        """根据入口四元式索引获取函数名"""
        return next(
            (func_name for func_name, start_idx in self.func_entries.items() 
             if start_idx == entry_idx),
            None
        )
    
    def get_scope_by_index(self, index: int):
        """
        根据四元式索引获取对应的函数作用域名和所属的基本块编号
        返回: (函数名, 基本块编号)；如果找不到，返回 (None, None)
        """
        # 先确定属于哪个函数
        if not self.func_entries:
            return (None, None)
        sorted_entries = sorted(self.func_entries.items(), key=lambda x: x[1])
        func_name = None
        for i, (fname, start_idx) in enumerate(sorted_entries):
            end_idx = sorted_entries[i + 1][1] if i + 1 < len(sorted_entries) else float('inf')
            if start_idx <= index < end_idx:
                func_name = fname
                break
        if func_name is None:
            return (None, None)
        # 再确定属于该函数的哪个基本块
        blocks = self.func_blocks[func_name]
        for block_idx, block in enumerate(blocks):
            quad_indices = [idx for idx, _ in block]
            if index in quad_indices:
                return (func_name, block_idx)
        return (func_name, None)

    def _get_function_entry(self) -> Dict[str, int]:
        """获取每个函数入口的四元式索引"""
        # 遍历全局符号表，找到所有函数符号
        # 返回一个字典 {func_name: entry_index}
        logger.debug("获取函数入口四元式索引...")

        return {
            symbol.name: symbol.quad_index
            for symbol in self.symbolTable.global_scope.symbols.values()
            if isinstance(symbol, FunctionSymbol) and symbol.quad_index is not None
        }

    def _get_function_vars(self) -> Dict[str, set]:
        """获取每个函数作用域下的变量名集合"""
        # 遍历函数入口，收集每个函数作用域内的有效变量名
        # 即只收集函数作用域内的变量名，不包括全局变量
        # 返回一个字典 {func_name: {var_name1, var_name2, ...}}
        logger.debug("收集函数作用域内的有效变量名...")

        def collect_vars(scope) -> set[str]:
            """辅助函数--收集单个作用域内的有效变量名"""
            return {
                sym.name for sym in scope.symbols.values()
                if isinstance(sym, (VariableSymbol, ParameterSymbol))
            }
        
        return {
            func_name: collect_vars(self.symbolTable.find_scope(func_name))
            for func_name in self.func_entries.keys()
        }

    def _block_split(self, quads: list[tuple[int, Quadruple]]) -> list[list[tuple[int, Quadruple]]]:
        """
            划分函数四元式为基本块

        Note:
            基本块划分规则：
            1. 程序入口为第一个基本块
            2. 跳转指令的目标地址开始新块
            3. 跳转指令的下一条指令开始新块

        Args:
            quads: 四元式列表，每个元素为(索引, 四元式)元组

        Returns:
            基本块列表，每个块是连续的四元式片段

        Example:
            >>> [(0, quad1), (1, quad2), ...] 
            → [[(0, quad1), (1, quad2)], [(3, quad3)], ...]
        """
        if not quads:
            return []

        # 创建指令索引到位置的映射
        index_to_pos = {inst_idx: pos for pos, (inst_idx, _) in enumerate(quads)}

        # 识别所有基本块起始位置
        block_starts = {0}  # 第一条指令总是块起始

        for current_pos, (_, quad) in enumerate(quads):
            # 处理跳转指令
            if quad.op in {'j', 'jnz'} and quad.result is not None:
                # 添加跳转目标位置
                if quad.result in index_to_pos:
                    block_starts.add(index_to_pos[quad.result])
                # 添加跳转指令的后继位置
                if current_pos + 1 < len(quads):
                    block_starts.add(current_pos + 1)

        # 按位置排序并划分基本块
        sorted_starts = sorted(block_starts)
        return [
            quads[start:end]
            for start, end in zip(
                sorted_starts,
                sorted_starts[1:] + [len(quads)]
            )
        ]

    def _split_all_functions(self) -> Dict[str, list]:
        """
            对函数四元式进行基本块划分并根据调用关系排序

        Returns:
            按调用关系排序的{函数名: 基本块列表}字典
        """
        logger.debug("划分所有函数的基本块并根据调用关系排序...")

        func_blocks = {} # {函数名: 基本块列表}

        # 预构建索引到位置的映射
        index_map = {idx: i for i, (idx, _) in enumerate(self.quads)}

        # 将函数入口字典转换为按照quad_index排序的列表
        sorted_entries = sorted(
            self.func_entries.items(), # (func_name, start_idx)
            key=lambda x: x[1]         # 按入口索引排序
        )

        # 遍历每个函数入口，划分基本块
        for i, (func_name, start_idx) in enumerate(sorted_entries):
            start_pos = index_map[start_idx]
            end_pos = index_map[sorted_entries[i+1][1]] if i+1 < len(sorted_entries) else len(self.quads)

            # 划分当前函数的基本块
            logger.debug(f"划分函数 {func_name} 的基本块: {start_pos} - {end_pos}")
            func_blocks[func_name] = self._block_split(self.quads[start_pos:end_pos])

        # 根据调用关系对函数进行拓扑排序
        # 构建调用图 (被调用者 -> 调用者集合)
        call_graph = {}
        for caller, blocks in func_blocks.items():
            for _, quad in (item for block in blocks for item in block):
                if getattr(quad, 'op', None) == 'call' and (callee := getattr(quad, 'arg1', None)) in func_blocks:
                    call_graph.setdefault(callee, set()).add(caller)

        # 拓扑排序
        order, visited = [], set()
        def visit(f):
            """深度优先访问函数，确保调用者在前"""
            if f not in visited:
                visited.add(f)
                for caller in call_graph.get(f, set()):
                    visit(caller)
                order.append(f)

        # 先访问 main 函数，确保它在最前面
        visit('main') if 'main' in func_blocks else None
        [visit(f) for f in func_blocks if f not in visited]

        return {f: func_blocks[f] for f in order}

    def _build_cfg(self, blocks: list[list[tuple[int, Quadruple]]]) -> Dict[int, list[int]]:
        """
            构建控制流图(CFG)

        Args:
            blocks: 基本块列表, 每个基本块是 [(idx, quad), ...]

        Returns:
            邻接表形式的控制流图CFG {块索引: [后继块索引列表]}
        """
        logger.debug("构建控制流图(CFG)...")

        # 构建指令索引到块索引的映射
        idx_to_block = {
            idx: b_idx 
            for b_idx, block in enumerate(blocks) 
            for idx, _ in block
        }

        cfg = {} # {块索引: 后继块索引列表}
        for i, block in enumerate(blocks):
            successors = set()        # 存储后继块索引
            last_quad = block[-1][1]  # 取最后一条指令

            # 处理跳转指令
            if last_quad.op == 'j' and last_quad.result is not None:
                if last_quad.result in idx_to_block:
                    successors.add(idx_to_block[last_quad.result])
            elif last_quad.op == 'jnz' and last_quad.result is not None:
                if last_quad.result in idx_to_block:
                    successors.add(idx_to_block[last_quad.result])
                if i + 1 < len(blocks):
                    successors.add(i + 1)
            
            # 默认顺序执行
            if not successors and i + 1 < len(blocks):
                successors.add(i + 1)

            cfg[i] = list(successors)

        return cfg

    def _live_variable_analysis(
            self, 
            blocks: list[list[tuple[int, Quadruple]]], 
            cfg: dict[int, list[int]], 
            valid_vars: set[str]
        ) -> tuple[list[set[str]], list[set[str]]]:
        """
            活跃变量分析(只统计valid_vars中的变量)

        Args:
            blocks: 基本块列表，每个块包含(index, quad)元组
            cfg: 控制流图 {块索引: [后继块索引]}
            valid_vars: 当前函数作用域下的有效变量集合
        
        Returns:
            (in_sets, out_sets): 
            - in_sets: 各块入口的活跃变量集合列表
            - out_sets: 各块出口的活跃变量集合列表
        """
        # 初始化每个块的使用和定义集合
        # use[i] = {使用的变量}, defs[i] = {定义的变量}
        # 使用集合包含该块内所有使用的变量，定义集合包含该块内所有定义的变量
        # 只统计有效变量 valid_vars 中的变量
        logger.debug("进行活跃变量分析...")
        
        used_vars = []    # 每个块使用的变量集合
        defined_vars = [] # 每个块定义的变量集合

        for block in blocks:
            read_vars = set()     # 记录使用的变量(读取)
            written_vars = set()  # 记录定义的变量(写入)

            # 遍历块内的四元式
            for _, quad in block:  
                # 检查四元式的操作数                
                for operand in [getattr(quad, 'arg1', None), getattr(quad, 'arg2', None)]:
                    if (operand and isinstance(operand, str) and
                        operand in valid_vars and operand not in written_vars):
                        read_vars.add(operand)

                # 检查四元式的结果
                if (getattr(quad, 'result', None) and isinstance(quad.result, str) and
                    quad.result in valid_vars):
                    written_vars.add(quad.result)

            used_vars.append(read_vars)
            defined_vars.append(written_vars)
        
        # 初始化IN/OUT集合(每个基本块对应一个集合)
        in_sets = [set() for _ in blocks]   # IN集合
        out_sets = [set() for _ in blocks]  # OUT集合
        changed = True

        while changed:
            changed = False

            # 反向遍历基本块，更新IN/OUT集合
            # 反向遍历是因为OUT集合依赖于后继块的IN
            for i in reversed(range(len(blocks))):
                # 记录当前块的IN/OUT集合，以便后续比较
                old_in, old_out = in_sets[i].copy(), out_sets[i].copy()

                # 计算OUT集合: 当前块的后继块的IN集合的并集
                out_sets[i] = set().union(*(in_sets[succ] for succ in cfg[i]))

                # 计算IN集合: 当前块的使用变量 ∪ (OUT集合 - 定义变量)
                in_sets[i] = used_vars[i] | (out_sets[i] - defined_vars[i])

                # 检查是否有变化
                # 如果IN或OUT集合有变化，则标记为需要重新计算
                if old_in != in_sets[i] or old_out != out_sets[i]:
                    changed = True

        return in_sets, out_sets