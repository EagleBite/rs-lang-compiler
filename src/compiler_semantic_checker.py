"""语义检查器"""
import copy
from typing import Dict, List
from compiler_parser_node import ParseNode, SynthesizedAttributes
from compiler_logger import logger
from compiler_semantic_symbol import VariableSymbol, ParameterSymbol, FunctionSymbol, SymbolTable, Scope
from compiler_semantic_symbol import Type, BaseType, ArrayType, TupleType, ReferenceType, OperatorType, UnitType, UninitializedType, RangeType
from compiler_semantic_symbol import type_to_string
from compiler_codegenerator import IntermediateCodeGenerator

class SemanticError:
    """简化的语义错误类"""
    def __init__(self, message: str, line: int = None, column: int = None):
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        location = ""
        if self.line is not None:
            location = f" 位于行 {self.line}"
            if self.column is not None:
                location += f" 列 {self.column}"
        return f"{self.message}{location}"

class SemanticChecker:
    """语义检查器"""
    def __init__(self):
        self.symbolTable = SymbolTable()                        
        self.pending_type_inference: Dict[str, ParseNode] = {} 
        self.errors = []
        self.current_function = None                       
        self.loop_stack = []
        self.loop_res = []
        self.code_generator = IntermediateCodeGenerator()     
        self.reference_tracker = {}                           
        
    def reset(self):
        """重置"""
        self.symbolTable = SymbolTable()                      
        self.pending_type_inference: Dict[str, ParseNode] = {}  
        self.errors = []                                      
        self.current_function = None                         
        self.reference_tracker = {}                          
        self.code_generator.reset()

    def check(self, node: ParseNode):
        """后序遍历语法树进行语义检查"""
        for child in node.children:
            self.check(child)
        method_name = f"_handle_{node.symbol}"
        action = getattr(self, method_name, self.no_action)
        action(node)

    def on_reduce(self, node: ParseNode):
        """处理非终结符节点"""
        method_name = f"_handle_{node.symbol}"
        action = getattr(self, method_name, self.no_action)
        self._update_position(node=node)
        logger.debug(f"✏️  当前处理: {method_name}")
        action(node)
            
    def no_action(self, node: ParseNode):
        """默认处理规则"""
        logger.info(f"❌  此处未定义处理规则: {node.symbol}")
        pass

    # ---------- 具体节点检查方法 ----------

    def _handle_JFuncStart(self, node: ParseNode):
        """处理开始跳转到main函数"""
        node.attributes.next_list = [self.code_generator.next_quad]
        self.code_generator.emit('j', None, None, None)
        
    def _handle_Program(self, node: ParseNode):

        # 检查是否有待类型推断的符号
        if self.pending_type_inference:
            for var_name, var_node in self.pending_type_inference.items():
                self._report_error(f"无法推断变量 '{var_name}' 的类型，请显式指定类型或赋初值", var_node)
        
        funcStartSymbol = self.symbolTable.lookup('main')
        if not funcStartSymbol:
            self._report_error("程序必须包含一个 'main' 函数作为入口点", node)
            return 

        self.code_generator.backpatch(node.children[0].attributes.next_list, funcStartSymbol.quad_index)
            
    def _handle_Declaration(self, node: ParseNode):
        pass

    def _handle_DeclarationString(self, node: ParseNode):
        pass

    def _handle_Type(self, node: ParseNode):
        """
        处理Type节点

        {'prod_lhs': 'Type', 'prod_rhs': ['i32']},
        {'prod_lhs': 'Type', 'prod_rhs': ['[', 'Type', ';', 'NUM', ']']},
        {'prod_lhs': 'Type', 'prod_rhs': ['(', 'TupleTypeInner', ')']},
        {'prod_lhs': 'Type', 'prod_rhs': ['(', ')']},
        {'prod_lhs': 'Type', 'prod_rhs': ['&', 'mut', 'Type']},
        {'prod_lhs': 'Type', 'prod_rhs': ['&', 'Type']},
        
        """
        first_child = node.children[0]

        if first_child.value == 'i32' or first_child.symbol == 'i32': # 基础类型 (i32)
            node.attributes.type_obj = BaseType("i32")

        elif first_child.value == '[' or first_child.symbol == '[':  # 数组类型 [Type; NUM]
            element_type = node.children[1].attributes.type_obj  # 数组元素类型
            array_size = node.children[3].value                  # 数组大小

            # 检查数组大小是否为正整数
            try:
                array_size = int(array_size)
                if array_size <= 0:
                    self._report_error(f"数组大小必须为正整数，实际为 {array_size}", node.children[3])
                    array_size = 1  # 设置默认值以继续分析
            except ValueError:
                self._report_error(f"无效的数组大小：{array_size}", node.children[3])
                array_size = 1  # 设置默认值以继续分析

            node.attributes.type_obj = ArrayType(element_type=element_type, size=array_size)

        elif first_child.value == '(' or first_child.symbol == '(':  # 元组类型 (TypeList)
            if len(node.children) == 2:  # 空元组
                node.attributes.type_obj = TupleType([])
            else:
                node.attributes.type_obj = TupleType(node.children[1].attributes.elements['types'])

        elif first_child.value == '&' or first_child.symbol == '&':  # 引用类型 &mut T 或 &T
            is_mut = len(node.children) > 2 and node.children[1].value == 'mut' # 是否为可变引用
            target_type_node = node.children[-1]                                # 目标类型对象
            
            node.attributes.type_obj = ReferenceType(
                target_type=target_type_node.attributes.type_obj,
                is_mutable=is_mut
            )

    def _handle_TupleTypeInner(self, node: ParseNode):
        """
        {'prod_lhs': 'TupleTypeInner', 'prod_rhs': ['Type', ',', 'TypeList']},
        {'prod_lhs': 'TupleTypeInner', 'prod_rhs': ['Type', ',']},
        """
        node.attributes.elements = {
            'types': []
        }

        for child in node.children:
            if child.symbol == "Type":
                node.attributes.elements['types'].append(child.attributes.type_obj)
            elif child.symbol == "TypeList":
                node.attributes.elements['types'].extend(child.attributes.elements['types'])
        
    def _handle_TypeList(self, node: ParseNode):
        """
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type']},
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type', ',']},
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type', ',', 'TypeList']},
        """
        node.attributes.elements = {
            'types': []
        }
       
        for child in node.children:
            if child.symbol == "Type":
                node.attributes.elements['types'].append(child.attributes.type_obj)
            elif child.symbol == "TypeList":
                node.attributes.elements['types'].extend(child.attributes.elements['types'])

    def _handle_VarDeclaration(self, node: ParseNode):
        """
        {'prod_lhs': 'VarDeclaration', 'prod_rhs': ['mut', 'ID']},
        {'prod_lhs': 'VarDeclaration', 'prod_rhs': ['ID']},
        """
        if node.children[0].value == 'mut':
            node.attributes.place = node.children[1].value
            node.attributes.is_mutable = True
        else:
            node.attributes.place = node.children[0].value
            node.attributes.is_mutable = False
            
    def _handle_VarDeclarationStatement(self, node: ParseNode):
        """
        处理变量声明语句 VarDeclarationStatement

        {'prod_lhs': 'VarDeclarationStatement', 'prod_rhs': ['let', 'VarDeclaration', ':', 'Type', ';']},
        {'prod_lhs': 'VarDeclarationStatement', 'prod_rhs': ['let', 'VarDeclaration', ';']},

        
        """
        var_name = node.children[1].attributes.place
        is_mutable = node.children[1].attributes.is_mutable
        
        if node.children[-2].symbol == "Type":
            inner_type = node.children[-2].attributes.type_obj
            inner_type.is_mutable = is_mutable
            if var_name in self.pending_type_inference:
                del self.pending_type_inference[var_name] # 重影覆盖之前需要类型推断的变量
        else:
            inner_type = None
            self.pending_type_inference[var_name] = node # 插入待推断字典

        # 未初始化类型
        var_type = UninitializedType(
            inner_type=inner_type,
            is_mutable=is_mutable
        )
            
        # 创建并插入符号
        var_symbol = VariableSymbol(
            name=var_name,
            type_obj=var_type,
        )
        self.symbolTable.insert(var_symbol)
        
    def _handle_VarDeclarationAssignStatement(self, node: ParseNode):
        """
        {'prod_lhs': 'VarDeclarationAssignStatement', 'prod_rhs': ['let', 'VarDeclaration', ':', 'Type', '=', 'Expression', ';']},
        {'prod_lhs': 'VarDeclarationAssignStatement', 'prod_rhs': ['let', 'VarDeclaration', '=', 'Expression', ';']},
        """
        left_place = node.children[1].attributes.place
        right_place = node.children[-2].attributes.place
        is_mutable = node.children[1].attributes.is_mutable

        declared_type = node.children[3].attributes.type_obj  # 声明类型
        expr_type = node.children[-2].attributes.type_obj     # 表达式类型

        if isinstance(expr_type, UninitializedType):
            self._report_error("该变量未初始化，不能作为右值使用", node.children[-2])
            return
        
        elif isinstance(expr_type, UnitType):
            self._report_error("右值表达式没有类型(unit 类型)，不能作为右值使用", node.children[-2])
            return

        # 类型兼容检查
        if len(node.children) > 5 and not self._is_type_compatible(expr_type, declared_type):
            self._report_error(f"类型不匹配: 不能将 {self._format_type(expr_type)} 赋值给 {self._format_type(declared_type)}", node.children[-2])
            var_type = declared_type
        else:
            var_type = expr_type

        # 创建符号并插入符号表
        var_type.is_mutable = is_mutable
        var_symbol = VariableSymbol(name=left_place, type_obj=var_type)
        self.symbolTable.insert(var_symbol)

        # 中间代码生成
        self.code_generator.emit('=', right_place, None, left_place)

# ------------------ 函数定义 -----------------------

    def _handle_ParamVar(self, node: ParseNode):
        """
        处理函数形参变量

        {'prod_lhs': 'ParamVar', 'prod_rhs': ['VarDeclaration', ':', 'Type']},
        """
        node.attributes.func_info = {
            'params': []
        }

        # 提取变量声明和类型节点
        var_name = node.children[0].attributes.place
        is_mutable = node.children[0].attributes.is_mutable
        param_type = node.children[2].attributes.type_obj
        param_type.is_mutable = is_mutable
        
        param_symbol = ParameterSymbol(name=var_name, type_obj=param_type)

        node.attributes.func_info['params'].append(param_symbol)

    def _handle_Parameters(self, node: ParseNode):
        """
        处理函数形参列表

        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar']},
        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar', ',']},
        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar', ',', 'Parameters']},
        """
        node.attributes.func_info = {
            'params': []
        }

        # 遍历所有子节点, 收集参数
        for child in node.children:
            if child.symbol in {"ParamVar", "Parameters"}:
                node.attributes.func_info['params'].extend(child.attributes.func_info['params'])             

    def _handle_FunctionHeaderDeclaration(self, node: ParseNode):
        """
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', 'Parameters', ')']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', ')']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', 'Parameters', ')', '->', 'Type']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', ')', '->', 'Type']},
        """
        func_name = node.children[1].value
        ret_type = UnitType()
        params = []

        # Begin:进入该函数的作用域
        self.symbolTable.enter_scope(func_name)

        # 检查是否有返回类型声明 Return
        if node.children[-2].value == '->':
            ret_type = node.children[-1].attributes.type_obj

        # 处理参数 Param
        if node.children[3].symbol == 'Parameters':
            # 将函数参数加入到该作用域中
            params = node.children[3].attributes.func_info['params']
            for param in params:
                self.symbolTable.insert(param)

        # 将函数信息临时存储起来
        self.current_function = FunctionSymbol(
            quad_index=self.code_generator.next_quad,
            name=func_name,
            return_type_obj=ret_type,
            parameters=params
        )

    def _handle_FunctionDeclaration(self, node: ParseNode):
        """
        {'prod_lhs': 'FunctionDeclaration', 'prod_rhs': ['FunctionHeaderDeclaration', 'FunctionExpressionBlock']}, # 表达式块
        {'prod_lhs': 'FunctionDeclaration', 'prod_rhs': ['FunctionHeaderDeclaration', 'Block']},                   # 语句块
        """
        declared_return_type = self.current_function.return_type_obj
    
        # 处理函数表达式块
        if node.children[-1].symbol == "FunctionExpressionBlock":
            actual_return_place = node.children[-1].attributes.place
            actual_return_type = node.children[-1].attributes.type_obj # 表达式块计算值的类型

            if not self._is_type_compatible(actual_return_type, declared_return_type):
                self._report_error(f"返回值类型不匹配: 声明返回 {self._format_type(declared_return_type)}, 实际返回 {self._format_type(actual_return_type)}", node)
                self.code_generator.emit("RETURN", None, None, "$ret_reg") # 生成一个返回语句
                return

            self.code_generator.emit("RETURN", actual_return_place, None, "$ret_reg") # 

        else:
            # TODO: 这里可能还有些问题 -> 是否隐式添加返回语句
            if not node.children[-1].last_return and not isinstance(self.current_function.return_type_obj, UnitType):
                # 函数声明的最后一句不是返回值并且返回值类型不是无类型 -> 缺少返回语句
                self._report_error(f"非Unit类型函数 '{self.current_function.name}' 缺少返回语句，预期返回类型: {self.current_function.return_type_obj}", node.children[0])
            else:
                # 递归搜索当前节点的子节点，查找是否有ReturnStatement节点，如果有则不需要隐式返回
                def has_return(node: ParseNode) -> bool:
                    """检查节点是否包含返回语句"""
                    if node.symbol == "ReturnStatement":
                        return True
                    for child in node.children:
                        if has_return(child):
                            return True
                    return False
                
                if not has_return(node):
                    self.code_generator.emit('RETURN', None, None, "$ret_reg")  # 生成隐式返回代码
            # 回填
            self.code_generator.backpatch(node.children[-1].attributes.next_list, self.code_generator.next_quad - 1)

        # 将临时存储的函数符号加入到全局作用域中
        self.symbolTable.exit_scope()
        self.symbolTable.insert(self.current_function)
        self.current_function = None

# ------------------ 表达式 -------------------------

    def _handle_Expression(self, node: ParseNode):
        """
        处理表达式节点

        {'prod_lhs': 'Expression', 'prod_rhs': ['AddExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['Expression', 'Relop', 'AddExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['FunctionExpressionBlock']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['SelectExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['LoopStatement']},
        
        """
        if len(node.children) == 1:
            node.attributes = copy.deepcopy(node.children[0].attributes)

            if node.children[0].attributes.next_list:
                self.code_generator.backpatch(node.children[0].attributes.next_list, self.code_generator.next_quad)
            
        elif len(node.children) == 3 and node.children[1].symbol == 'Relop':
            # 布尔表达式计算
            left, op, right = node.children
            left_type = left.attributes.type_obj
            right_type = right.attributes.type_obj

            if not self._is_binop_compatible(op.value, left_type, right_type):
                self._report_error(f"操作符 {op.value} 不支持操作类型 {self._format_type(left_type)} 和 {self._format_type(right_type)}", op)
                node.attributes.type_obj = UnitType()
                return

            # 生成中间代码
            temp_var = self.code_generator.new_temp()
            self.code_generator.emit(op.value, left.attributes.place, right.attributes.place, temp_var)

            node.attributes.place = temp_var
            node.attributes.type_obj = BaseType('bool')
            node.attributes.is_lvalue = False  # 运算结果总是右值

    def _handle_FunctionExpressionBlock(self, node: ParseNode):
        """
        处理函数表达式块

        {'prod_lhs': 'FunctionExpressionBlock', 'prod_rhs': ['{', 'FunctionExpressionString', '}']},

        语义规则:
            1. 继承内部表达式串的计算结果和存储位置
        """
        node.attributes = copy.deepcopy(node.children[1].attributes)

    def _handle_FunctionExpressionString(self, node: ParseNode):
        """
        处理函数表达式串
        
        {'prod_lhs': 'FunctionExpressionString', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'FunctionExpressionString', 'prod_rhs': ['StatementString', 'BackpatchMarker', 'FunctionExpressionString']},

        语义规则:
            1. 单表达式情况:
                - 继承子节点的计算结果和存储位置
            2. 多语句情况:
                - 前驱语句的未完成跳转指向当前语句开始
                - 最后一个语句的返回值作为函数表达式块的返回值
        """
        if len(node.children) == 3: # 多语句情况
            prev_statements = node.children[0].attributes  # 前驱语句序列
            marker = node.children[1].attributes           # 语句开始标记

            # 将前驱语句的未完成跳转指向当前语句开始
            self.code_generator.backpatch(prev_statements.next_list, marker.quad_index)
            node.attributes = node.children[-1].attributes

            # TODO: 
            node.last_return = node.children[-1]

        else: # 单个表达式情况
            node.attributes = node.children[0].attributes

    def _handle_SelectExpression(self, node: ParseNode):
        """
        处理选择表达式

        {'prod_lhs': 'SelectExpression', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'FunctionExpressionBlock', 'IfExitMarker', 'else', 'BackpatchMarker', 'FunctionExpressionBlock', 'ElseExitMarkder']},

        语义规则:
            0. 条件表达式必须是布尔类型 (BranchableExpression中已完成检查)
            1. if分支和else分支的类型必须兼容
            2. 生成中间代码:
        """
        # 获取关键标记点的属性
        cond_result = node.children[1].attributes
        if_start = node.children[2].attributes
        if_block = node.children[3].attributes
        if_end = node.children[4].attributes
        else_start = node.children[6].attributes
        else_block = node.children[7].attributes
        else_end = node.children[8].attributes

        # 检查两个分支类型兼容
        if_block_type = node.children[3].attributes.type_obj
        else_block_type = node.children[7].attributes.type_obj
        if not self._is_type_compatible(if_block_type, else_block_type):
            self._report_error(f"if-else分支类型不匹配: {self._format_type(if_block_type)} vs {self._format_type(else_block_type)}", node)
            node.attributes.type_obj = UnitType()
            return
        
        self.code_generator.backpatch(cond_result.true_list, if_start.quad_index)
        self.code_generator.backpatch(cond_result.false_list, else_start.quad_index)

        temp = self.code_generator.new_temp()  # 存储选择表达式结果的位置

        self.code_generator.backpatch(if_end.next_list, self.code_generator.next_quad)
        self.code_generator.emit('=', if_block.place, None, temp) 
        
        node.attributes.next_list = [self.code_generator.next_quad]
        self.code_generator.emit('j', None, None, None)  # 需要回填

        self.code_generator.backpatch(else_end.next_list, self.code_generator.next_quad)
        self.code_generator.emit('=', else_block.place, None, temp)
        
        node.attributes.place = temp
        node.attributes.type_obj = if_block_type

    def _handle_AddExpression(self, node: ParseNode):
        """
        处理加法表达式

        {'prod_lhs': 'AddExpression', 'prod_rhs': ['Item']},
        {'prod_lhs': 'AddExpression', 'prod_rhs': ['AddExpression', 'AddOp', 'Item']},
        """
        if len(node.children) == 1: # Itenm
            node.attributes = copy.deepcopy(node.children[0].attributes)
            
        else: # 加减运算
            left, op, right = node.children
            left_type = left.attributes.type_obj
            right_type = right.attributes.type_obj

            if not self._is_binop_compatible(op.value, left_type, right_type):
                self._report_error(f"操作符 {op.value} 不支持操作类型 {self._format_type(left_type)} 和 {self._format_type(right_type)}", op)
                node.attributes.type_obj = UnitType()
                return

            # 生成中间代码
            temp_var = self.code_generator.new_temp()
            self.code_generator.emit(op.value, left.attributes.place, right.attributes.place, temp_var)

            node.attributes.place = temp_var
            node.attributes.type_obj = left.attributes.type_obj  # 结果类型与左操作数相同
            node.attributes.is_lvalue = False  # 运算结果总是右值

    def _handle_Item(self, node: ParseNode):
        """
        处理项节点 Item

        {'prod_lhs': 'Item', 'prod_rhs': ['Factor']},
        {'prod_lhs': 'Item', 'prod_rhs': ['Item', 'MulOp', 'Factor']},
        """
        if len(node.children) == 1: # Factor
            node.attributes = copy.deepcopy(node.children[0].attributes)

        else: # 乘除运算
            left, op, right = node.children
            left_type = left.attributes.type_obj
            right_type = right.attributes.type_obj

            if not self._is_binop_compatible(op.value, left_type, right_type):
                self._report_error(f"操作符 {op.value} 不支持操作类型 {self._format_type(left_type)} 和 {self._format_type(right_type)}", op)
                node.attributes.type_obj = UnitType()
                return
            
            # 生成中间代码
            temp_var = self.code_generator.new_temp()
            self.code_generator.emit(op.value, left.attributes.place, right.attributes.place, temp_var)

            node.attributes.place = temp_var
            node.attributes.type_obj = left.attributes.type_obj  # 结果类型与左操作数相同
            node.attributes.is_lvalue = False  # 运算结果总是右值

    def _handle_Factor(self, node: ParseNode):
        """
        处理因子节点 Factor

        {'prod_lhs': 'Factor', 'prod_rhs': ['Element']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['[', 'ArrayElementList', ']']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['[', ']']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['(', 'TupleAssignInner', ')']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['(', ')']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['*', 'Factor']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['&', 'mut', 'Factor']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['&', 'Factor']},
        """
        first = node.children[0]

        if len(node.children) == 1: # Element
            node.attributes = copy.deepcopy(node.children[0].attributes)

        if first.value == '[':    # 数组字面量
            if len(node.children) == 2:  # 空数组 []
                node.attributes.type_obj = ArrayType(element_type=UnitType(), size=0)
            else:
                elements_types = node.children[1].attributes.elements['types']
                common_type = self._get_common_type(elements_types, node)
                node.attributes.type_obj = ArrayType(element_type=common_type, size=len(elements_types))
                node.attributes.elements = node.children[1].attributes.elements

        elif first.value == '(':  # 元组字面量
            if len(node.children) == 2:  # 空元组 ()
                node.attributes.type_obj = TupleType([])
            else:
                node.attributes.type_obj = TupleType(members=[e['types'] for e in node.children[1].attributes.elements])
                node.attributes.elements = node.children[1].attributes.elements

        elif first.value == '*':  # 解引用
            target_type = node.children[1].attributes.type_obj
            if not isinstance(node.children[1].attributes.type_obj, ReferenceType):
                self._report_error("只能解引用指针类型", node)
                node.attributes.type_obj = UnitType()
                return
            
            node.attributes.type_obj = node.children[1].attributes.type_obj.target_type
            node.attributes.place = f"*{node.children[1].attributes.place}"  # 生成解引用代码

        elif first.value == '&':  # 引用
            is_mut = len(node.children) > 2 and node.children[1].value == 'mut'
            factor_node = node.children[-1]

            def _check_ref_avaliable(target_node: ParseNode, is_mut_ref: bool) -> bool:
                """检查引用是否有效"""
                var_name = target_node.attributes.place
                var_state = self.reference_tracker.get(var_name) # 获取引用追踪状态

                if var_state:
                    # 规则1: 可变引用必须来自可变变量
                    if is_mut_ref and not var_state['is_mutable']:
                        self._report_error(f"不能从不可变变量'{var_name}'创建可变引用", target_node)
                        return False
                    # 规则2: 可变引用不能与其他引用共存
                    if is_mut_ref and (var_state['immutable_refs'] > 0 or var_state['mutable_ref']):
                        self._report_error(f"变量'{var_name}'已存在其他引用，无法创建可变引用", target_node)
                        return False
                    # 规则3: 不可变引用不能与可变引用共存
                    if not is_mut_ref and var_state['mutable_ref']:
                        self._report_error(f"变量'{var_name}'已存在可变引用，无法创建不可变引用", target_node)
                        return False

                    if is_mut_ref:
                        var_state['mutable_ref'] = True
                    else:
                        var_state['immutable_refs'] += 1
                else:
                    symbol = self.symbolTable.lookup(var_name)
                    if not symbol:
                        return False
                    
                    if is_mut_ref and symbol.type_obj.is_mutable == False:
                        self._report_error(f"不能从不可变变量'{var_name}'创建可变引用", node)
                        return False
                    self.reference_tracker[var_name] = {
                        'is_mutable': symbol.type_obj.is_mutable, 
                        'immutable_refs': 0 if is_mut_ref else 1, 
                        'mutable_ref': True if is_mut_ref else False
                    }

                return True
            
            if not _check_ref_avaliable(factor_node, is_mut):
                node.attributes.type_obj = UnitType()
                return
            
            # 设置引用属性
            node.attributes.type_obj = ReferenceType(
                target_type=factor_node.attributes.type_obj,
                is_mutable=is_mut
            )
            node.attributes.place = f"&{'mut ' if is_mut else ''}{factor_node.attributes.place}"

    def _handle_ArrayElementList(self, node: ParseNode):
        """
        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression', ',', 'ArrayElementList']},
        """
        node.attributes.elements = {
            'types': [],
            'places': [],
            'const_values': []
        }

        for child in node.children:
            if child.symbol == "Expression":
                node.attributes.elements['types'].append(child.attributes.type_obj)
                node.attributes.elements['places'].append(child.attributes.place)
                node.attributes.elements['const_values'].append(child.attributes.const_value)
            elif child.symbol == "ArrayElementList":
                node.attributes.elements['types'].extend(child.attributes.elements['types'])
                node.attributes.elements['places'].extend(child.attributes.elements['places'])
                node.attributes.elements['const_values'].extend(child.attributes.elements['const_values'])

    def _handle_TupleAssignInner(self, node: ParseNode):
        """
        {'prod_lhs': 'TupleAssignInner', 'prod_rhs': ['Expression', ',', 'TupleElementList']},
        {'prod_lhs': 'TupleAssignInner', 'prod_rhs': ['Expression', ',']},
        """
        node.attributes.elements = {
            'types': [],
            'places': [],
            'const_values': []
        }

        for child in node.children:
            if child.symbol == "Expression":
                node.attributes.elements['types'].append(child.attributes.type_obj)
                node.attributes.elements['places'].append(child.attributes.place)
                node.attributes.elements['const_values'].append(child.attributes.const_value)
            elif child.symbol == "TupleElementList":
                node.attributes.elements['types'].extend(child.attributes.elements['types'])
                node.attributes.elements['places'].extend(child.attributes.elements['places'])
                node.attributes.elements['const_values'].extend(child.attributes.elements['const_values'])

    def _handle_TupleElementList(self, node: ParseNode):
        """
        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression', ',', 'TupleElementList']},
        """
        node.attributes.elements = {
            'types': [],
            'places': [],
            'const_values': []
        }

        for child in node.children:
            if child.symbol == "Expression":
                node.attributes.elements['types'].append(child.attributes.type_obj)
                node.attributes.elements['places'].append(child.attributes.place)
                node.attributes.elements['const_values'].append(child.attributes.const_value)
            elif child.symbol == "TupleElementList":
                node.attributes.elements['types'].extend(child.attributes.elements['types'])
                node.attributes.elements['places'].extend(child.attributes.elements['places'])
                node.attributes.elements['const_values'].extend(child.attributes.elements['const_values'])

    def _handle_Element(self, node: ParseNode):
        """
        处理元素节点Element

        {'prod_lhs': 'Element', 'prod_rhs': ['NUM']},
        {'prod_lhs': 'Element', 'prod_rhs': ['Assignableidentifier']},
        {'prod_lhs': 'Element', 'prod_rhs': ['(', 'Expression', ')']},
        {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', 'Arguments', ')']},
        {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', ')']},

        yu语义规则:
            1. 数字字面量 (NUM) -> 直接转换为整数类型
        
        """
        first_child = node.children[0]

        if first_child.symbol == "NUM": # 数字字面量 (NUM)
            node.attributes.place = node.children[0].value
            node.attributes.type_obj = BaseType('i32')
            node.attributes.const_value = int(first_child.value)
        
        elif first_child.symbol == "Assignableidentifier": # 可赋值标识符 (变量/成员访问等)
            node.attributes = copy.deepcopy(first_child.attributes)
            node.attributes.is_lvalue = False  # 转换为右值

            if node.attributes.array_access:
                # 生成数组加载指令
                temp_var = self.code_generator.new_temp()
                self.code_generator.emit('[]=', node.attributes.array_access['name'], node.attributes.array_access['index'], temp_var)
                node.attributes.place = temp_var
                node.attributes.array_access = None
        
        elif first_child.value == '(': # 括号表达式 (Expression)
            node.attributes = node.children[1].attributes

        elif first_child.symbol == "ID" and node.children[1].value == "(" and node.children[-1].value == ")": # 函数调用 (ID + Arguments)
            # {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', 'Arguments', ')']},
            # {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', ')']},
            
            func_name = node.children[0].value
            func_symbol = self.symbolTable.lookup(func_name)

            # 查找函数符号
            if not func_symbol or not isinstance(func_symbol, FunctionSymbol):
                self._report_error(f"未定义的函数: {func_name}", first_child)
                node.attributes.type_obj = UnitType()
                return

            # 处理参数
            args_attrs = node.children[2].attributes if len(node.children) > 3 else None
            if args_attrs and args_attrs.call_info:
                # 参数类型检查
                args_len = len(args_attrs.call_info['arg_types'])
                params_len = len(func_symbol.parameters)
                if args_len != params_len:
                    self._report_error(f"参数数量不匹配: 需要 {args_len} 个参数，得到 {params_len} 个", node)
                    node.attributes.type_obj = UnitType()

                for i, (arg_type, param) in enumerate(zip(args_attrs.call_info['arg_types'], func_symbol.parameters)):
                    if not self._is_type_compatible(arg_type, param.type_obj):
                        self._report_error(f"参数{i}类型不匹配，需要 {self._format_type(param.type_obj)}, 得到 {self._format_type(arg_type)}", node)
                        node.attributes.type_obj = UnitType()

                # 生成PARAM指令
                for i, arg_place in enumerate(args_attrs.call_info['args']):
                    self.code_generator.emit('param', arg_place, None, f"param_{i+1}")
            
            # 生成CALL指令
            arg_count = len(args_attrs.call_info['args']) if args_attrs else 0
            self.code_generator.emit('call', func_name, arg_count, None)

            # 处理返回值
            if not isinstance(func_symbol.return_type_obj, UnitType):
                node.attributes.place = self.code_generator.new_temp()
                self.code_generator.emit('=', "$ret_reg", None, node.attributes.place)

            node.attributes.type_obj = func_symbol.return_type_obj

    def _handle_Arguments(self, node: ParseNode):
        """
        处理函数调用的参数列表

        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression', ',', 'Arguments']},
        """
        node.attributes.call_info = {
            'args': [],      # 参数存储位置列表
            'arg_types': []  # 参数类型列表
        }

        for child in node.children:
            if child.symbol == "Expression":
                node.attributes.call_info['args'].append(child.attributes.place)
                node.attributes.call_info['arg_types'].append(child.attributes.type_obj)
            
            elif child.symbol == "Arguments":
                node.attributes.call_info['args'].extend(child.attributes.call_info['args'])
                node.attributes.call_info['arg_types'].extend(child.attributes.call_info['arg_types'])

    def _handle_Assignableidentifier(self, node: ParseNode):
        """
        处理可赋值标识符

        {'prod_lhs': 'Assignableidentifier', 'prod_rhs': ['*', 'Assignableidentifier']},
        {'prod_lhs': 'Assignableidentifier', 'prod_rhs': ['AssignableidentifierInner']},

        语义规则:
        """
        if node.children[0].value == '*':  # 指针解引用
            target = node.children[1]

            # 检查目标是否为指针类型
            if not isinstance(target.attributes.type_obj, ReferenceType):
                self._report_error("只能解引用指针类型", node.children[0])
                node.attributes.type_obj = UnitType()
                return
            
            node.attributes.type_obj = target.attributes.type_obj.target_type
            node.attributes.place = f"*{target.attributes.place}"  # 生成解引用代码
            node.attributes.is_lvalue = True
            
        else:  # 基础左值
            node.attributes = copy.deepcopy(node.children[0].attributes)
    
    def _handle_AssignableidentifierInner(self, node: ParseNode):
        """
        处理可赋值标识符

        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['Element', '[', 'Expression', ']']},
        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['Element', '.', 'NUM']},
        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['ID']},

        语义规则:
            1. 数组索引:
                - 检查是否为数组类型
                - 检查索引是否为整数类型
                - 检查索引是否在范围内
            2. 元组成员:
                - 检查是否为元组类型
                - 检查索引是否在范围内
            3. 普通标识符:
                - 检查变量是否已经声明
        """
        if len(node.children) == 4:  # 数组索引 arr[index]
            array = node.children[0]
            index = node.children[2]

            array_type = array.attributes.type_obj
            index_type = index.attributes.type_obj

            if isinstance(array_type, UninitializedType):
                array_type = array_type.inner_type

            if not isinstance(array_type, ArrayType):
                self._report_error(f"非数组类型不能索引: {self._format_type(array_type)}", node)
                node.attributes.type_obj = UnitType()
                return
            
            if not (isinstance(index_type, BaseType) and index_type.name == "i32"):
                self._report_error("数组索引必须是i32类型", index)
                node.attributes.type_obj = UnitType()
                return   

            index_value = index.attributes.const_value
            if index_value is not None:
                if isinstance(index_value, int):
                    if(index_value < 0 or index_value >= array_type.size):
                        self._report_error(f"数组索引越界: 最大 {array_type.size-1}，实际 {index_value}", node.children[2])
                        node.attributes.type_obj = UnitType()
                else:
                    self._report_error(f"数组索引必须是整数，实际:{index_value}", node.children[2])
                    node.attributes.type_obj = UnitType()
            
            # 设置数组访问属性
            logger.info(array_type)
            node.attributes.type_obj = array_type.element_type
            node.attributes.is_lvalue = True
            node.attributes.is_mutable = array_type.is_mutable
            node.attributes.array_access = {
                'name': array.attributes.place,
                'index': index.attributes.place,
                'elem_type': array_type.element_type
            }

        elif len(node.children) == 3:  # 元组成员 tuple.0
            struct = node.children[0]
            index = node.children[2]

            # 类型检查
            struct_type = struct.attributes.type_obj
            if not isinstance(struct_type, TupleType):
                self._report_error(f"非元组类型不能访问成员: {self._format_type(struct_type)}", node)
                node.attributes.type_obj = UnitType()
                return
            
            index_value = int(index.value)
            if index_value < 0 or index_value >= len(struct.attributes.type_obj.members):
                self._report_error(f"成员索引越界: 最大 {len(struct.attributes.type_obj.members)-1}，实际 {index_value}", node.children[2])
                node.attributes.type_obj = UnitType()
                return

            # 设置元组访问属性
            node.attributes.type_obj = struct.attributes.type_obj.members[index_value]
            node.attributes.is_lvalue = True
            node.attributes.is_mutable = struct.attributes.type_obj.is_mutable
            node.attributes.tuple_access = {
                'name': struct.attributes.place,
                'field_idx': index_value,
                'field_type': node.attributes.type_obj
            }

        else:  # 普通标识符    
            var_name = node.children[0].value
            if not (symbol := self.symbolTable.lookup(var_name)):
                self._report_error(f"未声明的变量: {var_name}", node)
                node.attributes.type_obj = UnitType()
                return

            node.attributes.place = var_name
            node.attributes.type_obj = symbol.type_obj
            node.attributes.is_lvalue = True
            node.attributes.is_mutable = symbol.type_obj.is_mutable
                
    def _handle_Relop(self, node: ParseNode):
        node.value = node.children[0].value

    def _handle_AddOp(self, node: ParseNode):
        node.value = node.children[0].value
        
    def _handle_MulOp(self, node: ParseNode):
        node.value = node.children[0].value

# -------------------- 语句块 -------------------------

    def _handle_Block(self, node: ParseNode):
        """
        处理语句块

        {'prod_lhs': 'Block', 'prod_rhs': ['{', '}']},
        {'prod_lhs': 'Block', 'prod_rhs': ['{', 'StatementString', '}']},
        
        """
        if len(node.children) == 3:
            node.attributes.next_list = node.children[1].attributes.next_list
            node.attributes.break_list = node.children[1].attributes.break_list
            node.attributes.continue_list = node.children[1].attributes.continue_list

            # TODO: 关于返回值
            node.last_return = node.children[1].last_return

    def _handle_StatementString(self, node: ParseNode):
        """
        处理语句序列

        {'prod_lhs': 'StatementString', 'prod_rhs': ['Statement']},
        {'prod_lhs': 'StatementString', 'prod_rhs': ['StatementString', 'BackpatchMarker', 'Statement']},
        {'prod_lhs': 'StatementString', 'prod_rhs': ['FunctionExpressionString', ';']},

        语义规则:
            1. 单语句情况:
                - 直接继承语句的控制流属性 next_list
            2. 函数表达式情况:
                - 直接继承函数表达式的计算结果和存储位置
            3. 多语句情况:
                - 将前驱语句的 next_list 回填到 BackpatchMarker 位置
                - 继承最后一条语句的控制流属性 next_list
        """
 
        if len(node.children) == 3: # 多语句情况
            prev_statements = node.children[0].attributes  # 前驱语句序列
            marker = node.children[1].attributes           # 语句开始标记
            current_stmt = node.children[2].attributes     # 当前语句

            # 回填前驱语句的 next_list 到当前语句开始位置
            self.code_generator.backpatch(prev_statements.next_list, marker.quad_index)

            # 继承当前语句的控制流属性
            node.attributes.next_list = current_stmt.next_list
            node.attributes.break_list = self.code_generator.merge_lists(
                prev_statements.break_list, 
                current_stmt.break_list
            )
            node.attributes.continue_list = self.code_generator.merge_lists(
                prev_statements.continue_list, 
                current_stmt.continue_list
            )

            # TODO: 关于返回值
            node.last_return = node.children[-1]

        elif len(node.children) == 2: # 函数表达式情况
            node.attributes = node.children[0].attributes
        
        else: # 单语句情况
            current_stmt = node.children[0].attributes
            node.attributes.next_list = current_stmt.next_list
            node.attributes.break_list = current_stmt.break_list
            node.attributes.continue_list = current_stmt.continue_list

            # TODO: 关于返回值
            node.last_return = node.children[-1]

    def _handle_Statement(self, node: ParseNode):
        """
        处理单条语句
        
        {'prod_lhs': 'Statement', 'prod_rhs': [';']},
        {'prod_lhs': 'Statement', 'prod_rhs': ['AssignStatement']},                # 赋值语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['VarDeclarationStatement']},        # 变量声明语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['VarDeclarationAssignStatement']},  # 变量声明赋值语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['ReturnStatement']},                # 返回语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['IfStatement']},                    # if语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['CirculateStatement']},             # 循环语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['BreakStatement']},                 # break语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['ContinueStatement']},              # continue语句

        语义规则:
            1. 继承子节点的所有属性 (attributes) -- 主要传递控制流属性
        """
        node.attributes = node.children[0].attributes
        if node.children[0].symbol == 'ReturnStatement':
            node.last_return = True

    def _handle_ReturnStatement(self, node: ParseNode):
        """
        处理返回语句

        {'prod_lhs': 'ReturnStatement', 'prod_rhs': ['return', 'Expression', ';']},
        {'prod_lhs': 'ReturnStatement', 'prod_rhs': ['return', ';']},
        
        """
        declared_return_type = self.current_function.return_type_obj
        actual_return_type = node.children[1].attributes.type_obj if len(node.children) == 3 else UnitType()

        if not self._is_type_compatible(actual_return_type, declared_return_type):
            self._report_error(f"返回值类型不匹配: 声明返回 {self._format_type(declared_return_type)}, 实际返回 {self._format_type(actual_return_type)}", node)

        if len(node.children) == 3:
            result_place = node.children[1].attributes.place
            self.code_generator.emit('RETURN', result_place, None, "$ret_reg") # 将计算结果写在寄存器中
        else:
            self.code_generator.emit('RETURN', None, None, "$ret_reg")

    def _handle_AssignStatement(self, node: ParseNode):
        """
        处理赋值语句

        {'prod_lhs': 'AssignStatement', 'prod_rhs': ['Assignableidentifier', '=', 'Expression', ';']},

        处理规则:

        中间代码生成:
            1. 数组相关
                - []= 用于 读取 数组元素（右值）
                - =[] 用于 写入 数组元素（左值）
        """
        lvalue_node, rvalue_node = node.children[0], node.children[2]

        lvalue_type = lvalue_node.attributes.type_obj
        rvalue_type = rvalue_node.attributes.type_obj

        if isinstance(lvalue_type, UnitType):
            return

        lvalue_name = lvalue_node.attributes.place
        is_mutable = lvalue_node.attributes.is_mutable

        # 检查左值是否为可赋值
        if is_mutable == False:
            self._report_error(f"不能给不可变变量赋值: {lvalue_name}", lvalue_node)
            return
        
        # 检查右值是否可以使用
        if isinstance(rvalue_type, UninitializedType):
            self._report_error("该变量未初始化，不能作为右值使用", rvalue_node)
            return
        
        elif isinstance(rvalue_type, UnitType):
            self._report_error("右值表达式没有类型(unit 类型)，不能作为右值使用", rvalue_node)
            return

        # 检查左值是否需要类型推断
        if lvalue_name in self.pending_type_inference:
            symbol = self.symbolTable.lookup(lvalue_name)
            symbol.type_obj = rvalue_type
            del self.pending_type_inference[lvalue_name]

        # 检查左值和右值类型是否兼容
        if not self._is_type_compatible(lvalue_type, rvalue_type):
            self._report_error(f"类型不匹配: 不能将 {self._format_type(rvalue_type)} 赋值给 {self._format_type(lvalue_type)}", node)
            return
            
        if lvalue_node.attributes.array_access:
            # 数组元素赋值 (=[])
            array_name = lvalue_node.attributes.array_access['name']
            array_index = lvalue_node.attributes.array_access['index']
            value_place = rvalue_node.attributes.place

            # 检查数组是否存在
            if not self.symbolTable.lookup(array_name):
                self._report_error(f"未声明的数组: {array_name}", lvalue_node)
                return
            
            self.code_generator.emit('=[]', value_place, array_index, array_name)

        elif lvalue_node.attributes.tuple_access:
            # 元组成员赋值 (暂不实现)
            pass

        else:
            # 普通变量赋值 (=)
            lvalue_place = lvalue_node.attributes.place
            rvalue_place = rvalue_node.attributes.place
            self.code_generator.emit('=', rvalue_place, None, lvalue_place)  

# ------------------- 控制流 ----------------------

    def _handle_LoopMarker(self, node: ParseNode):
        """
        处理循环标志
        
        语义规则:
            1. 将循环开始第一个四元式的索引存储到循环栈中，作为循环标记
            2. 进入新的作用域，命名为 "Loop_{next_quad}"，用于局部变量
        """
        # 将循环开始第一个四元式的索引存储到循环栈中，作为循环标记
        next_quad = self.code_generator.next_quad
        self.loop_stack.append(next_quad)
        self.symbolTable.enter_scope(f"Loop_{next_quad}")

    def _handle_LoopExprMarker(self, node: ParseNode):
        """处理Loop循环表达式标志"""
        tmp_loop_result = self.code_generator.new_temp()
        self.loop_res.append({
            'place': tmp_loop_result,
            'type': None
        })

    def _handle_BackpatchMarker(self, node: ParseNode):
        """处理回填标记"""
        # 回填标记的作用是将下一条四元式索引存储到节点属性中，
        # 以便在后续需要回填时使用
        node.attributes.quad_index = self.code_generator.next_quad

    def _handle_BranchMarker(self, node: ParseNode):
        """处理分支标记"""
        # 空处理函数，所有处理推迟到BranchableExpression
        pass

    def _handle_IfExitMarker(self, node: ParseNode):
        """
        处理if语句的退出标记

        语义规则:
            1. 生成一个无条件跳转四元式 (在含有 else 分支的情况下用于跳过 else 分支)
        """
        node.attributes.next_list = [self.code_generator.next_quad]
        self.code_generator.emit('j', None, None, None)  # 生成待回填的无条件跳转      

    def _handle_ElseExitMarkder  (self, node: ParseNode):
        node.attributes.next_list = [self.code_generator.next_quad]
        self.code_generator.emit('j', None, None, None)  # 生成待回填的无条件跳转      

    def _handle_BranchableExpression(self, node: ParseNode):
        """
        处理条件标记
        
        {'prod_lhs': 'BranchableExpression', 'prod_rhs': ['Expression', 'BranchMarker']}

        语义规则:
            1. 检查条件表达式是否为布尔类型
            2. 控制流生成
                - 将条件表达式转换为跳转逻辑
                - 使用 Expression 节点的属性 place 作为跳转条件
                - 生成四元式: jnz (跳转到真分支) 和 j (跳转到假分支)
        """
        # 检查条件表达式类型
        expr_node = node.children[0]
        if not isinstance(expr_node.attributes.type_obj, BaseType) or expr_node.attributes.type_obj.name != "bool":
            self._report_error("条件表达式必须是布尔类型", expr_node)
            node.attributes.true_list = []
            node.attributes.false_list = []
            return
        
        # 将表达式转换为跳转逻辑
        expr_place = expr_node.attributes.place
        node.attributes.true_list = [self.code_generator.next_quad]
        node.attributes.false_list = [self.code_generator.next_quad + 1]
        self.code_generator.emit("jnz", expr_place, None, None)     # 为真跳转
        self.code_generator.emit("j", None, None, None)             # 为假跳转
    
    def _handle_IfStatement(self, node: ParseNode):
        """
        处理if语句(含可选的 else 分支)

        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block', 'IfExitMarker', 'else', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block', 'IfExitMarker', 'else', 'BackpatchMarker', 'IfStatement']},

        语义规则：
            0. 条件表达式必须是布尔类型 (BranchableExpression中已完成检查)
            1. 管理六个关键标记点:
                - cond_result: 条件表达式结果 (含 true_list 和 false_list)
                - if_start:    if分支的开始位置
                - if_block:    if分支的代码块
                - if_end:      if分支的结束位置 (如果存在 else 分支)
                - else_start:  else分支的开始位置 (如果存在 else 分支)
                - else_block:  else分支的代码块 (如果存在 else 分支)
            2. 回填逻辑:
                - 将 cond_result 的 true_list 回填到 if_start 的四元式索引
                - 将 cond_result 的 false_list 回填到 else_start 的四元式索引 (如果存在 else 分支)
                - 合并 if_block 的 next_list 和 else_block 的 next_list 作为整个 if 语句的 next_list
                - 合并所有子块的 break_list 和 continue_list
        """
        # 获取关键标记点的属性
        cond_result = node.children[1].attributes
        if_start = node.children[2].attributes
        if_block = node.children[3].attributes

        if len(node.children) > 4:  # 存在 else 分支
            if_end = node.children[4].attributes
            else_start = node.children[6].attributes
            else_block = node.children[7].attributes
            self.code_generator.backpatch(cond_result.true_list, if_start.quad_index)
            self.code_generator.backpatch(cond_result.false_list, else_start.quad_index)
            node.attributes.next_list = self.code_generator.merge_lists(
                if_block.next_list,
                if_end.next_list,
                else_block.next_list
            )
            node.attributes.break_list = self.code_generator.merge_lists(
                if_block.break_list, 
                else_block.break_list
            )
            node.attributes.continue_list = self.code_generator.merge_lists(
                if_block.continue_list, 
                else_block.continue_list
            )
        else: # 不存在 else 分支
            self.code_generator.backpatch(cond_result.true_list, if_start.quad_index)
            node.attributes.next_list = self.code_generator.merge_lists(
                cond_result.false_list, 
                if_block.next_list
            )
            node.attributes.break_list = if_block.break_list
            node.attributes.continue_list = if_block.continue_list

    def _handle_CirculateStatement(self, node: ParseNode):
        """
        处理循环语句

        {'prod_lhs': 'CirculateStatement', 'prod_rhs': ['LoopMarker', 'WhileStatement']},
        {'prod_lhs': 'CirculateStatement', 'prod_rhs': ['LoopMarker', 'ForStatement']},
        {'prod_lhs': 'CirculateStatement', 'prod_rhs': ['LoopMarker', 'LoopStatement']},

        语义规则:
            1. 继承循环语句的属性
            2. 管理循环作用域:
                - 进入循环作用域，创建新的符号表作用域
                - 在循环结束后退出循环作用域
        """
        node.attributes = node.children[1].attributes

        # 循环结束后退出循环作用域
        self.loop_stack.pop()  
        self.symbolTable.exit_scope()

    def _handle_WhileStatement(self, node: ParseNode):
        """
        处理while循环语句
        
        {'prod_lhs': 'WhileStatement', 'prod_rhs': ['while', 'BackpatchMarker', 'BranchableExpression', 'BackpatchMarker', 'Block']}

        语义规则：
            0. 条件表达式必须是布尔类型 (BranchableExpression中已完成检查)
            1. 管理四个关键标记点:
                - loop_start:  循环开始位置
                - cond_result: 条件表达式结果 (含 true_list 和 false_list)
                - body_start:  循环体开始位置
                - loop_body:   循环体结束位置
            3. 回填逻辑:
                - 将 loop_body 的 next_list 回填到 loop_start 的四元式索引
                - 将 cond_result 的 true_list 回填到 body_start 的四元式索引
                - 合并 cond_result 的 false_list 和循环的 break_list 作为整个 while 语句的 next_list
            4. 生成无条件跳转指令:
                - 在循环体结束后跳转到循环开始位置
        """       
        # 获取关键标记点的属性
        loop_start = node.children[1].attributes  
        cond_result = node.children[2].attributes 
        body_start = node.children[3].attributes  
        loop_body = node.children[4].attributes   

        # 回填处理
        self.code_generator.backpatch(cond_result.true_list, body_start.quad_index)
        self.code_generator.backpatch(loop_body.next_list, loop_start.quad_index)
        self.code_generator.backpatch(loop_body.continue_list, loop_start.quad_index)
        # 生成跳转指令 循环结束后回到开始位置
        self.code_generator.emit('j', None, None, loop_start.quad_index)

        node.attributes.next_list = self.code_generator.merge_lists(
            cond_result.false_list,
            loop_body.break_list,
        )

    def _handle_IterableStructure(self, node: ParseNode):
        """
        处理可迭代结构
        
        {'prod_lhs': 'IterableStructure', 'prod_rhs': ['Expression', '..', 'Expression']},
        {'prod_lhs': 'IterableStructure', 'prod_rhs': ['Element']},
        
        语法规则:
            1. 如果是范围表达式 `a..b`，则检查 a 和 b 是否为整数类型
            2. 如果是元素表达式，则检查元素是否为可迭代类型
        """
        if len(node.children) == 3: # 范围表达式 `a..b`
            start_type = node.children[0].attributes.type_obj
            end_type = node.children[2].attributes.type_obj

            # 检查两个表达式是否为整数类型
            if not (isinstance(start_type, BaseType) and isinstance(end_type, BaseType) and
                    start_type.name == 'i32' and end_type.name == 'i32'):
                self._report_error("范围表达式必须使用整数", node)
                # 如果类型不匹配，使用默认的范围类型
                default_range_type = RangeType(element_type=BaseType('i32'), start=0, end=0, step=1)
                node.attributes.type_obj = default_range_type
                return

            node.attributes.type_obj = RangeType(
                element_type=start_type,
                start=node.children[0].attributes.place,
                end=node.children[2].attributes.place,
                step=1
            )

        else: # 数组
            element_type = node.children[0].attributes.type_obj

            # 检查元素是否为可迭代类型
            if not isinstance(element_type, ArrayType):
                self._report_error(f"不可迭代的类型 {self._format_type(element_type)}", node)
                # 如果类型不匹配，使用默认的范围类型
                default_range_type = RangeType(element_type=BaseType('i32'), start=0, end=0, step=1)
                node.attributes.type_obj = default_range_type
                return

            # TODO: 目前只传递了元素类型，后续可能需要传递更多信息
            node.attributes.type_obj = element_type

    def _handle_ForExpression(self, node: ParseNode):
        """
        处理 for 循环迭代表达式
        
        {'prod_lhs': 'ForExpression', 'prod_rhs': ['VarDeclaration', 'in', 'IterableStructure']},

        语义规则:
            0. 可迭代对象必须是数组或范围类型 (IterableStructure中已完成检查)
            1. 中间代码生成:
                a. 迭代器初始化阶段
                b. 迭代器更新阶段 <- 循环开始位置
                c. 条件判断阶段
        """
        iterable_type = node.children[2].attributes.type_obj
        
        # 注册循环变量到符号表
        var_decl_node = node.children[0]
        self.symbolTable.insert(VariableSymbol(
            name=var_decl_node.attributes.place, 
            type_obj=iterable_type.element_type
        ))
        
        # 初始化迭代器
        temp_iterator = self.code_generator.new_temp()
        temp_flag = self.code_generator.new_temp()     # 存放循环判断结果
        init_value = iterable_type.start if isinstance(iterable_type, RangeType) else 0
        self.code_generator.emit('=', init_value, None, temp_iterator)

        step = iterable_type.step if isinstance(iterable_type, RangeType) else 1
        end_condition = iterable_type.end if isinstance(iterable_type, RangeType) else iterable_type.size

        # 循环开始部分(先检查再更新)
        node.attributes.quad_index = self.code_generator.next_quad
        self.code_generator.emit('<', temp_iterator, end_condition, temp_flag)
        self.code_generator.emit('=', temp_iterator, None, var_decl_node.attributes.place)
        self.code_generator.emit('+', temp_iterator, step, temp_iterator)

        node.attributes.true_list = [self.code_generator.next_quad]
        node.attributes.false_list = [self.code_generator.next_quad + 1]
        self.code_generator.emit('jnz', temp_flag, None, None)  # 小于是True分支
        self.code_generator.emit('j', None, None, None)         # 大于等于是False分支            

    def _handle_ForStatement(self, node: ParseNode):
        """
        处理 for 循环语句 (转换成类 while 循环)
        
        {'prod_lhs': 'ForStatement', 'prod_rhs': ['for', 'ForExpression', 'BackpatchMarker', 'Block']},

        语义规则:
            0. 可迭代对象必须是数组或范围类型 (ForExpression中已完成检查)
            1. 管理五个关键标记点:
                - init_pos:     迭代器初始化位置
                - cond_result:  条件表达式结果 (含 true_list 和 false_list)
                - body_start:   循环体开始位置  
                - update_pos:   迭代器更新位置
                - loop_body:    循环体结束位置
            2. 回填逻辑:
                - 将 cond_result.true_list 回填到 body_start 的四元式索引
                - 将 loop_body.next_list 回填到 update_pos 的四元式索引
                - 合并 cond_result.false_list 和循环的 break_list 作为整个 for 语句的 next_list
        """
        cond_result = node.children[1].attributes
        body_start = node.children[2].attributes
        loop_body = node.children[3].attributes

        self.code_generator.backpatch(cond_result.true_list, body_start.quad_index)
        self.code_generator.backpatch(loop_body.next_list, cond_result.quad_index)
        self.code_generator.backpatch(loop_body.continue_list, cond_result.quad_index)
        self.code_generator.emit('j', None, None, cond_result.quad_index)

        node.attributes.next_list = self.code_generator.merge_lists(
            cond_result.false_list,
            loop_body.break_list
        )
        
    def _handle_LoopStatement(self, node: ParseNode):
        """
        处理Loop循环语句

        {'prod_lhs': 'LoopStatement', 'prod_rhs': ['LoopMarker', 'loop', 'LoopExprMarker', 'BackpatchMarker', 'Block']},

        语义规则:
            1. 管理四个关键标记点:
                - loop_start: 循环开始位置
                - loop_body:  循环体代码块
                - break_list: 循环退出位置 (用于回填)
            2. 回填逻辑:
                - 将 loop_body.next_list 回填到 loop_start 的四元式索引
                - 生成无条件跳转指令，跳转到循环开始位置
        """
        loop_start = node.children[3].attributes
        loop_body = node.children[4].attributes
        
        self.code_generator.backpatch(loop_body.next_list, loop_start.quad_index)  # 回填循环体的 next_list
        self.code_generator.backpatch(loop_body.continue_list, loop_start.quad_index)  # 回填 continue 跳转位置
        self.code_generator.emit('j', None, None, loop_start.quad_index) # 无条件跳转

        node.attributes.next_list = loop_body.break_list

        node.attributes.place = self.loop_res[-1]['place']
        node.attributes.type_obj = self.loop_res[-1]['type']

        # 循环结束后退出循环作用域
        self.loop_stack.pop()
        self.loop_res.pop()
        self.symbolTable.exit_scope()

    def _handle_BreakStatement(self, node: ParseNode):
        """
        处理break语句

        {'prod_lhs': 'BreakStatement', 'prod_rhs': ['break', ';']},
        {'prod_lhs': 'BreakStatement', 'prod_rhs': ['break', 'Expression', ';']},

        语义规则:
            1. break 语句必须在循环内使用
            2. 如果带有返回值，检查返回值类型是否与循环一致 (即多个break表达式类型一致)
            3. 生成无条件跳转指令 
        """
        if not hasattr(self, 'loop_stack') or not self.loop_stack:
            self._report_error("break语句必须在循环内使用", node)
            return

        # Loop循环需要
        if self.loop_res:
            if len(node.children) > 2:  # break带返回值
                if self.loop_res[-1]['type']:
                    if not self._is_type_compatible(self.loop_res[-1]['type'], node.children[1].attributes.type_obj):
                        self._report_error(f"Loop 循环 break 返回值类型不匹配", node)
                else:
                    self.loop_res[-1]['type'] = node.children[1].attributes.type_obj
                self.code_generator.emit('=', node.children[1].attributes.place, None, self.loop_res[-1]['place'])
            else:
                if self.loop_res[-1]['type']:
                    self._report_error(f"Loop 循环需要返回值类型 {self._format_type(self.loop_res[-1]['type'])}，但break没有提供返回值", node)
                    return
                else:
                    self.loop_res[-1]['type'] = UnitType()               

        node.attributes.break_list = [self.code_generator.next_quad]  # 记录break跳转位置
        self.code_generator.emit('j', None, None, None)

    def _handle_ContinueStatement(self, node: ParseNode):
        """
        处理continue语句

        {'prod_lhs': 'ContinueStatement', 'prod_rhs': ['continue', ';']},

        语义规则:
            1. continue 语句必须在循环内使用
            2. 生成无条件跳转指令，跳转到循环开始位置
        """
        if not hasattr(self, 'loop_stack') or not self.loop_stack:
            self._report_error("continue语句必须在循环内使用", node)
            return
        
        node.attributes.continue_list = [self.code_generator.next_quad]  # 记录continue跳转位置
        self.code_generator.emit('j', None, None, None)
        
    # ---------- 辅助检查工具方法 ----------
    def _report_error(self, message: str, node: ParseNode):
        """记录错误信息"""
        error = SemanticError(message=message, line=node.line, column=node.column)
        self.errors.append(error)
        logger.error(error)

    def _report_error_at(self, message: str, line: int, column: int):
        """记录错误信息，指定行列位置"""
        error = SemanticError(message=message, line=line, column=column)
        self.errors.append(error)
        logger.error(error)

    def _format_type(self, type_obj: Type) -> str:
        """格式化类型为字符串"""
        if isinstance(type_obj, UnitType):
            return "()"
        elif isinstance(type_obj, BaseType):
            return type_obj.name
        elif isinstance(type_obj, ArrayType):
            return f"Array<{self._format_type(type_obj.element_type)}, size={type_obj.size}>"
        elif isinstance(type_obj, TupleType):
            members = ", ".join(self._format_type(m) for m in type_obj.members)
            return f"({members})"
        elif isinstance(type_obj, ReferenceType):
            mut = "mut " if type_obj.is_mutable else ""
            return f"&{mut}{self._format_type(type_obj.target_type)}"
        elif isinstance(type_obj, UninitializedType):
            return f"Uninitialized<{self._format_type(type_obj.inner_type)}>"
        
        return str(type_obj)

    def _update_position(self, node: ParseNode):
        """更新节点的位置 用于错误信息输出"""
        if len(node.children) != 0:
            first_child = node.children[0]
            node.line = first_child.line
            node.column = first_child.column

    def _get_common_type(self, element_types: List[Type], node: ParseNode) -> Type:
        """获取表达式列表的共同类型"""
        if not element_types:
            return UnitType()

        first_type = element_types[0]
        for ty in element_types[1:]:
            if ty != first_type:
                self._report_error(f"数组元素类型不一致: {first_type} 和 {ty}", node)

        return first_type

    def _is_type_compatible(self, actual: Type, expected: Type) -> bool:
        # 1. 未初始化类型
        if isinstance(actual, UninitializedType):
            logger.info(f"❌  未初始化类型 {actual.inner_type} {expected}")
            return self._is_type_compatible(actual.inner_type, expected)
        
        if isinstance(expected, UninitializedType):
            return self._is_type_compatible(actual, expected.inner_type)
        
        # 2. 完全同类匹配（引用对象同类型）
        if type(actual) != type(expected):
            return False
        
        # 3. Unit 类型
        if isinstance(actual, UnitType) and isinstance(expected, UnitType):
            return True
        
        # 4. 基础类型（i32, bool, void 等）
        if isinstance(actual, BaseType) and isinstance(expected, BaseType):
            return actual.name == expected.name
        
        # 5. 数组类型：元素类型兼容且长度相同
        if isinstance(actual, ArrayType) and isinstance(expected, ArrayType):
            return (actual.size == expected.size and
                    self._is_type_compatible(actual.element_type, expected.element_type))
        
        # 6. 元组类型：成员数量相同且对应成员类型兼容
        if isinstance(actual, TupleType) and isinstance(expected, TupleType):
            if len(actual.members) != len(expected.members):
                return False
            return all(self._is_type_compatible(a, e) for a, e in zip(actual.members, expected.members))
        
        # 7. 引用类型：目标类型相同即可
        if isinstance(actual, ReferenceType) and isinstance(expected, ReferenceType):
            return self._is_type_compatible(actual.target_type, expected.target_type)
        
        return False
        
    def _is_binop_compatible(self, op: str, left_type: Type, right_type: Type) -> bool:
        """检查二元运算的操作数类型是否兼容"""
        # 1. 处理未初始化类型
        if isinstance(left_type, UninitializedType):
            left_type = left_type.inner_type
        if isinstance(right_type, UninitializedType):
            right_type = right_type.inner_type

        # 2. 根据运算符分类处理
        if op in {'+', '-', '*', '/', '%'}:  # 算术运算
            return (isinstance(left_type, BaseType) and isinstance(right_type, BaseType) and
                    left_type.name in {'i32'} and left_type.name == right_type.name)
        
        elif op in {'<', '>', '<=', '>=', '==', '!='}:  # 比较运算
            # 允许数值比较，或同类型比较（如结构体判等）
            return (self._is_type_compatible(left_type, right_type) and
                    (isinstance(left_type, BaseType) or  # 数值/布尔比较
                     isinstance(left_type, ReferenceType)))  # 引用判等
        
        elif op in {'&&', '||'}:  # 逻辑运算
            # 要求两边都是布尔类型
            return (isinstance(left_type, BaseType) and 
                    isinstance(right_type, BaseType) and
                    left_type.name == 'bool' and
                    right_type.name == 'bool')
        
        return False

    def get_errors(self):
        return self.errors
    
    def get_quads(self):
        return self.code_generator.quads
    
    