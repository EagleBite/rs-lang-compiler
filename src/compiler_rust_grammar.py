
RUST_GRAMMAR = {
    # 终结符需要自行定义 出现在左侧的符号加入到非终结符中
    'terminals' : {
        # 关键字
        'fn', 'mut', 'return', '->', 'let', 'if', 'else', 'while', 'for', 'loop', 'break', 'continue', 'in',
        # 类型
        'i32', 
        # 标识符和字面量
        'ID', 'NUM',
        # 运算符
        '+', '-', '*', '/', '%', '&',
        '==', '!=', '<', '<=', '>', '>=',
        '||', '&&',
        # 界符
        '(', ')', '[', ']', '{', '}', ';', ',', ':', '=', '.', '..', 
    },
    # 可以通过产生式自动生成 出现在产生式左侧的符号加入到非终结符中
    'non_terminals' : {
    },
    # 每一项是一个产生式 是一推一的关系
    'productions' : [
        # 0. 基础结构(Basic Construct)
        {'prod_lhs': 'Begin', 'prod_rhs': ['program']},
        {'prod_lhs': 'program', 'prod_rhs': ['declaration_list']},
        {'prod_lhs': 'declaration_list', 'prod_rhs': ['declaration', 'declaration_list']},
        {'prod_lhs': 'declaration_list', 'prod_rhs': []},
        {'prod_lhs': 'declaration', 'prod_rhs': ['function_declaration']},

        # 1. 函数声明(Function Declaration)
        {'prod_lhs': 'function_declaration', 'prod_rhs': ['function_header', 'block']},               # 块
        {'prod_lhs': 'function_declaration', 'prod_rhs': ['function_header', 'expr_block']},          # 表达式块
        {'prod_lhs': 'function_header', 'prod_rhs': ['fn', 'ID', '(', 'param_list', ')', 'return_type']},
        {'prod_lhs': 'return_type', 'prod_rhs': ['->', 'type']},
        {'prod_lhs': 'return_type', 'prod_rhs': []},
        {'prod_lhs': 'param_list', 'prod_rhs': ['param']},
        {'prod_lhs': 'param_list', 'prod_rhs': ['param', ',', 'param_list']},
        {'prod_lhs': 'param_list', 'prod_rhs': []},
        {'prod_lhs': 'param', 'prod_rhs': ['variable_declaration', ':', 'type']},

        # 2. 块(Block) & 表达式块(Expression_Block)
        # TODO: 修改表达式块的产生式
        {'prod_lhs': 'block', 'prod_rhs': ['{', 'statement_list', '}']},
        {'prod_lhs': 'statement_list', 'prod_rhs': []},
        {'prod_lhs': 'statement_list', 'prod_rhs': ['statement_with_semi', 'statement_list']},
        {'prod_lhs': 'expr_block', 'prod_rhs': ['{', 'statement_list_expression', '}']},
        {'prod_lhs': 'statement_list_expression', 'prod_rhs': ['bare_expression_statement']},
        {'prod_lhs': 'statement_list_expression', 'prod_rhs': ['statement_with_semi', 'statement_list_expression']},
        {'prod_lhs': 'loop_expr_block', 'prod_rhs': ['{', 'statement_list', 'break_statement_with_expr', '}']},

        # 3. 变量和类型
        {'prod_lhs': 'variable_declaration', 'prod_rhs': ['mut', 'ID']}, # 可变变量声明
        {'prod_lhs': 'variable_declaration', 'prod_rhs': ['ID']},        # 不可变变量声明 -- 需要修改
        {'prod_lhs': 'type', 'prod_rhs': ['i32']},
        {'prod_lhs': 'type', 'prod_rhs': ['[', 'type', ';', 'NUM', ']']},
        {'prod_lhs': 'type', 'prod_rhs': ['(', 'tuple_type_inner', ')']},
        {'prod_lhs': 'type', 'prod_rhs': ['&', 'mut', 'type']}, # 可变引用
        {'prod_lhs': 'type', 'prod_rhs': ['&', 'type']},        # 不可变引用

        {'prod_lhs': 'tuple_type_inner', 'prod_rhs': []},
        {'prod_lhs': 'tuple_type_inner', 'prod_rhs': ['type', ',', 'tuple_type_list']},
        {'prod_lhs': 'tuple_type_list', 'prod_rhs': []},
        {'prod_lhs': 'tuple_type_list', 'prod_rhs': ['type']},
        {'prod_lhs': 'tuple_type_list', 'prod_rhs': ['type', ',', 'tuple_type_list']},

        # 4. 语句(Statement)
        {'prod_lhs': 'statement', 'prod_rhs': ['statement_with_semi']},        # 普通语句（带分号）
        {'prod_lhs': 'statement', 'prod_rhs': ['bare_expression_statement']},  # 表达式语句（不带分号）

        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['variable_declaration_stmt']},              # 变量声明语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['variable_declaration_assignment_stmt']},   # 变量声明赋值语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['assignment_stmt']},                        # 赋值语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['return_statement']},                       # 返回语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['if_stmt']},                                # if语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['loop_stmt']},                              # 循环语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['break_statement']},                        # break语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['continue_statement']},                     # continue语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': [';']},                                      # 空语句（分号）

        # 4.1. 表达式语句
        {'prod_lhs': 'statement_with_semi', 'prod_rhs': ['bare_expression_statement', ';']},  # 表达式语句(有分号)
        {'prod_lhs': 'bare_expression_statement', 'prod_rhs': ['value_expr']},                # 表达式语句(无分号)
        # 4.2. 变量声明语句
        {'prod_lhs': 'variable_declaration_stmt', 'prod_rhs': ['let', 'variable_declaration', ':', 'type', ';']},
        {'prod_lhs': 'variable_declaration_stmt', 'prod_rhs': ['let', 'variable_declaration', ';']},
        {'prod_lhs': 'variable_declaration_assignment_stmt', 'prod_rhs': ['let', 'variable_declaration', '=', 'value_expr', ';']},
        {'prod_lhs': 'variable_declaration_assignment_stmt', 'prod_rhs': ['let', 'variable_declaration', ':', 'type', '=', 'value_expr', ';']},
        # 4.3. 赋值语句
        {'prod_lhs': 'assignment_stmt', 'prod_rhs': ['place_expr', '=', 'value_expr', ';']},
        # 4.4. 返回语句
        {'prod_lhs': 'return_statement', 'prod_rhs': ['return', ';']},
        {'prod_lhs': 'return_statement', 'prod_rhs': ['return', 'value_expr', ';']},
        # 4.5. if语句
        {'prod_lhs': 'if_stmt', 'prod_rhs': ['if', 'value_expr', 'block', 'else_part']},
        {'prod_lhs': 'else_part', 'prod_rhs': []},
        {'prod_lhs': 'else_part', 'prod_rhs': ['else', 'block']},
        {'prod_lhs': 'else_part', 'prod_rhs': ['else', 'if_stmt']},
        # 4.6. 循环语句
        {'prod_lhs': 'loop_stmt', 'prod_rhs': ['while', 'value_expr', 'block']},
        {'prod_lhs': 'loop_stmt', 'prod_rhs': ['for', 'variable_declaration', 'in', 'iterable_structure', 'block']},
        {'prod_lhs': 'loop_stmt', 'prod_rhs': ['loop', 'block']},
        # 4.7. break语句
        {'prod_lhs': 'break_statement', 'prod_rhs': ['break_statement_with_expr']},
        {'prod_lhs': 'break_statement', 'prod_rhs': ['break_statement_without_expr']},
        {'prod_lhs': 'break_statement_with_expr', 'prod_rhs': ['break', 'value_expr', ';']},
        {'prod_lhs': 'break_statement_without_expr', 'prod_rhs': ['break', ';']},
        # 4.8. continue语句
        {'prod_lhs': 'continue_statement', 'prod_rhs': ['continue', ';']},
        
        # 可迭代结构
        {'prod_lhs': 'iterable_structure', 'prod_rhs': ['value_expr', '..', 'value_expr']},
        {'prod_lhs': 'iterable_structure', 'prod_rhs': ['value_expr']},

        # 5. 表达式(Expression)
        # Expressions are divided into two main categories: place expressions and value expressions
        # - A place expression is an expression that represents a memory location.
        # - A value expression is an expression that represents an actual value.
        # Note: Historically, place expressions were called lvalues and value expressions were called rvalues.
        # 5.1 Place Expression (左值表达式)
        {'prod_lhs': 'place_expr', 'prod_rhs': ['place_expr_base']},
        {'prod_lhs': 'place_expr', 'prod_rhs': ['*', 'place_expr']},  # 指针解引用
        {'prod_lhs': 'place_expr_base', 'prod_rhs': ['ID']},
        {'prod_lhs': 'place_expr_base', 'prod_rhs': ['(', 'place_expr', ')']},
        {'prod_lhs': 'place_expr_base', 'prod_rhs': ['place_expr_base', '[', 'value_expr', ']']},  # 数组索引
        {'prod_lhs': 'place_expr_base', 'prod_rhs': ['place_expr_base', '.', 'NUM']},              # 字段访问      
        # 5.2 Value Expression (右值表达式)
        # 表达式层次：条件 → 逻辑或 → 逻辑与 → 关系 → 加减 → 乘除 → 一元 → 后缀 → 基本
        {'prod_lhs': 'value_expr', 'prod_rhs': ['[', 'array_element_list', ']']},   # 数组字面量
        {'prod_lhs': 'value_expr', 'prod_rhs': ['(', 'tuple_element_inner', ')']},  # 元组字面量
        {'prod_lhs': 'value_expr', 'prod_rhs': ['logical_or_expr']},
        {'prod_lhs': 'value_expr', 'prod_rhs': ['conditional_expr']},
        # 条件表达式 if condition { branch_1 } else { branch_2 }
        {'prod_lhs': 'conditional_expr', 'prod_rhs': ['logical_or_expr']},
        {'prod_lhs': 'conditional_expr', 'prod_rhs': ['if', 'logical_or_expr', 'expr_block', 'else', 'expr_block']},
        # 逻辑或
        {'prod_lhs': 'logical_or_expr', 'prod_rhs': ['logical_or_expr', 'logic_or_op', 'logical_and_expr']},
        {'prod_lhs': 'logical_or_expr', 'prod_rhs': ['logical_and_expr']},
        # 逻辑与
        {'prod_lhs': 'logical_and_expr', 'prod_rhs': ['logical_and_expr', 'logic_and_op', 'relational_expr']},
        {'prod_lhs': 'logical_and_expr', 'prod_rhs': ['relational_expr']},       
        # 关系表达式
        {'prod_lhs': 'relational_expr', 'prod_rhs': ['relational_expr', 'relational_op', 'additive_expr']},
        {'prod_lhs': 'relational_expr', 'prod_rhs': ['additive_expr']},
        # 加减表达式
        {'prod_lhs': 'additive_expr', 'prod_rhs': ['additive_expr', 'additive_op', 'multiplicative_expr']},
        {'prod_lhs': 'additive_expr', 'prod_rhs': ['multiplicative_expr']},
        # 乘除表达式
        {'prod_lhs': 'multiplicative_expr', 'prod_rhs': ['multiplicative_expr', 'multiplicative_op', 'unary_expr']},
        {'prod_lhs': 'multiplicative_expr', 'prod_rhs': ['unary_expr']},
        # 一元表达式
        {'prod_lhs': 'unary_expr', 'prod_rhs': ['unary_op', 'unary_expr']},
        {'prod_lhs': 'unary_expr', 'prod_rhs': ['postfix_expr']},
        {'prod_lhs': 'unary_expr', 'prod_rhs': ['NUM']},
        # 后缀表达式
        {'prod_lhs': 'postfix_expr', 'prod_rhs': ['postfix_expr', '(', 'argument_list', ')']},  # 函数调用
        {'prod_lhs': 'postfix_expr', 'prod_rhs': ['primary_expr']},
        # 基本表达式
        {'prod_lhs': 'primary_expr', 'prod_rhs': ['place_expr']},
        {'prod_lhs': 'primary_expr', 'prod_rhs': ['(', 'value_expr', ')']}, # 加括号()
        {'prod_lhs': 'primary_expr', 'prod_rhs': ['expr_block']},           # 表达式块{}
        # 循环表达式
        {'prod_lhs': 'primary_expr', 'prod_rhs': ['loop_expr']},
        {'prod_lhs': 'loop_expr', 'prod_rhs': ['loop', 'loop_expr_block']},

        # 数组元素列表
        {'prod_lhs': 'array_element_list', 'prod_rhs': []},
        {'prod_lhs': 'array_element_list', 'prod_rhs': ['value_expr']},
        {'prod_lhs': 'array_element_list', 'prod_rhs': ['value_expr', ',', 'array_element_list']},
        # 元组元素列表
        {'prod_lhs': 'tuple_element_inner', 'prod_rhs': []},
        {'prod_lhs': 'tuple_element_inner', 'prod_rhs': ['value_expr', ',', 'tuple_element_list']},
        {'prod_lhs': 'tuple_element_list', 'prod_rhs': []},
        {'prod_lhs': 'tuple_element_list', 'prod_rhs': ['value_expr']},
        {'prod_lhs': 'tuple_element_list', 'prod_rhs': ['value_expr', ',', 'tuple_element_list']},
        # 实参列表
        {'prod_lhs': 'argument_list', 'prod_rhs': []},
        {'prod_lhs': 'argument_list', 'prod_rhs': ['value_expr']},
        {'prod_lhs': 'argument_list', 'prod_rhs': ['value_expr', ',', 'argument_list']},
        
        # 6. 运算符
        # 6.1. 关系运算符
        {'prod_lhs': 'relational_op', 'prod_rhs': ['==']},
        {'prod_lhs': 'relational_op', 'prod_rhs': ['!=']},
        {'prod_lhs': 'relational_op', 'prod_rhs': ['<']},
        {'prod_lhs': 'relational_op', 'prod_rhs': ['<=']},
        {'prod_lhs': 'relational_op', 'prod_rhs': ['>']},
        {'prod_lhs': 'relational_op', 'prod_rhs': ['>=']},
        # 6.2. 加减运算符
        {'prod_lhs': 'additive_op', 'prod_rhs': ['+']},
        {'prod_lhs': 'additive_op', 'prod_rhs': ['-']},
        # 6.3. 乘除运算符
        {'prod_lhs': 'multiplicative_op', 'prod_rhs': ['*']}, # 乘号
        {'prod_lhs': 'multiplicative_op', 'prod_rhs': ['/']},
        {'prod_lhs': 'multiplicative_op', 'prod_rhs': ['%']},
        # 6.4. 一元运算符
        {'prod_lhs': 'unary_op', 'prod_rhs': ['&']},          # 引用
        {'prod_lhs': 'unary_op', 'prod_rhs': ['&', 'mut']},
        # 6.5. 逻辑运算符
        {'prod_lhs': 'logic_or_op', 'prod_rhs': ['||']},
        {'prod_lhs': 'logic_and_op', 'prod_rhs': ['&&']},
    ],
    'start_symbol' : 'Begin'
}

RUST_GRAMMAR_PPT = {
    # 终结符需要自行定义 出现在左侧的符号加入到非终结符中
    'terminals' : {
        # 关键字
        'fn', 'mut', 'return', '->', 'let', 'if', 'else', 'while', 'for', 'loop', 'break', 'continue', 'in',
        # 类型
        'i32', 
        # 标识符和字面量
        'ID', 'NUM',
        # 运算符
        '+', '-', '*', '/', '%', '&',
        '==', '!=', '<', '<=', '>', '>=',
        # 界符
        '(', ')', '[', ']', '{', '}', ';', ',', ':', '=', '.', '..', 
    },
    # 可以通过产生式自动生成
    'non_terminals' : {
    },
    # 每一项是一个产生式 是一推一的关系
    'productions' : [
        # Program structure
        {'prod_lhs': 'Begin', 'prod_rhs': ['Program']},
        {'prod_lhs': 'JFuncStart', 'prod_rhs': []},
        {'prod_lhs': 'Program', 'prod_rhs': ['JFuncStart', 'DeclarationString']},
        {'prod_lhs': 'DeclarationString', 'prod_rhs': ['Declaration', 'DeclarationString']},
        {'prod_lhs': 'DeclarationString', 'prod_rhs': ['Declaration']},
        {'prod_lhs': 'Declaration', 'prod_rhs': ['FunctionDeclaration']},

        # 函数声明
        {'prod_lhs': 'FunctionDeclaration', 'prod_rhs': ['FunctionHeaderDeclaration', 'FunctionExpressionBlock']}, # 表达式块
        {'prod_lhs': 'FunctionDeclaration', 'prod_rhs': ['FunctionHeaderDeclaration', 'Block']},                   # 语句块

        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', 'Parameters', ')']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', ')']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', 'Parameters', ')', '->', 'Type']},
        {'prod_lhs': 'FunctionHeaderDeclaration', 'prod_rhs': ['fn', 'ID', '(', ')', '->', 'Type']},
        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar']},
        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar', ',']},
        {'prod_lhs': 'Parameters', 'prod_rhs': ['ParamVar', ',', 'Parameters']},
        {'prod_lhs': 'ParamVar', 'prod_rhs': ['VarDeclaration', ':', 'Type']},

        # 语句块(Block) & 表达式块(Expression Block)
        {'prod_lhs': 'Block', 'prod_rhs': ['{', '}']},
        {'prod_lhs': 'Block', 'prod_rhs': ['{', 'StatementString', '}']},
        {'prod_lhs': 'StatementString', 'prod_rhs': ['Statement']},
        {'prod_lhs': 'StatementString', 'prod_rhs': ['StatementString', 'BackpatchMarker', 'Statement']},
        {'prod_lhs': 'StatementString', 'prod_rhs': ['FunctionExpressionString', ';']},
        {'prod_lhs': 'FunctionExpressionBlock', 'prod_rhs': ['{', 'FunctionExpressionString', '}']},
        {'prod_lhs': 'FunctionExpressionString', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'FunctionExpressionString', 'prod_rhs': ['StatementString', 'BackpatchMarker', 'FunctionExpressionString']},

        # 变量声明
        {'prod_lhs': 'VarDeclaration', 'prod_rhs': ['mut', 'ID']},
        {'prod_lhs': 'VarDeclaration', 'prod_rhs': ['ID']},

        # 类型
        {'prod_lhs': 'Type', 'prod_rhs': ['i32']},
        {'prod_lhs': 'Type', 'prod_rhs': ['[', 'Type', ';', 'NUM', ']']},
        {'prod_lhs': 'Type', 'prod_rhs': ['(', 'TupleTypeInner', ')']},
        {'prod_lhs': 'Type', 'prod_rhs': ['(', ')']},
        {'prod_lhs': 'Type', 'prod_rhs': ['&', 'mut', 'Type']},
        {'prod_lhs': 'Type', 'prod_rhs': ['&', 'Type']},
        {'prod_lhs': 'TupleTypeInner', 'prod_rhs': ['Type', ',', 'TypeList']},
        {'prod_lhs': 'TupleTypeInner', 'prod_rhs': ['Type', ',']},
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type']},
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type', ',']},
        {'prod_lhs': 'TypeList', 'prod_rhs': ['Type', ',', 'TypeList']},

        # 语句
        {'prod_lhs': 'Statement', 'prod_rhs': [';']},
        # {'prod_lhs': 'Statement', 'prod_rhs': ['Expression', ';']},              # 表达式语句 - 这一部分应该用于将表达式串转换为语句串
        {'prod_lhs': 'Statement', 'prod_rhs': ['AssignStatement']},                # 赋值语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['VarDeclarationStatement']},        # 变量声明语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['VarDeclarationAssignStatement']},  # 变量声明赋值语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['ReturnStatement']},                # 返回语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['IfStatement']},                    # if语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['CirculateStatement']},             # 循环语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['LoopStatement']},                  # Loop 循环语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['BreakStatement']},                 # break语句
        {'prod_lhs': 'Statement', 'prod_rhs': ['ContinueStatement']},              # continue语句

        {'prod_lhs': 'BreakStatement', 'prod_rhs': ['break', ';']},
        {'prod_lhs': 'BreakStatement', 'prod_rhs': ['break', 'Expression', ';']},
        {'prod_lhs': 'ContinueStatement', 'prod_rhs': ['continue', ';']},

        {'prod_lhs': 'ReturnStatement', 'prod_rhs': ['return', 'Expression', ';']},
        {'prod_lhs': 'ReturnStatement', 'prod_rhs': ['return', ';']},

        {'prod_lhs': 'VarDeclarationStatement', 'prod_rhs': ['let', 'VarDeclaration', ':', 'Type', ';']},
        {'prod_lhs': 'VarDeclarationStatement', 'prod_rhs': ['let', 'VarDeclaration', ';']},

        {'prod_lhs': 'AssignStatement', 'prod_rhs': ['Assignableidentifier', '=', 'Expression', ';']},

        {'prod_lhs': 'VarDeclarationAssignStatement', 'prod_rhs': ['let', 'VarDeclaration', ':', 'Type', '=', 'Expression', ';']},
        {'prod_lhs': 'VarDeclarationAssignStatement', 'prod_rhs': ['let', 'VarDeclaration', '=', 'Expression', ';']},

        # Control flow
        # 控制流标记 用于指导条件表达式中间代码的生成
        {'prod_lhs': 'BackpatchMarker', 'prod_rhs': []},  # 用于存储回填的标记
        {'prod_lhs': 'BranchMarker', 'prod_rhs': []},     # 用于分支的标记
        {'prod_lhs': 'IfExitMarker', 'prod_rhs': []},     # 用于if语句的退出标记
        {'prod_lhs': 'ElseExitMarkder', 'prod_rhs': []},  # 用于else语句的退出标记
        {'prod_lhs': 'LoopMarker', 'prod_rhs': []},       # 循环语句标记
        {'prod_lhs': 'LoopExprMarker', 'prod_rhs': []},   # Loop循环语句标记
        
        # 条件控制表达式
        {'prod_lhs': 'BranchableExpression', 'prod_rhs': ['Expression', 'BranchMarker']},
        {'prod_lhs': 'IterableStructure', 'prod_rhs': ['Expression', '..', 'Expression']},
        {'prod_lhs': 'IterableStructure', 'prod_rhs': ['Element']},
        {'prod_lhs': 'ForExpression', 'prod_rhs': ['VarDeclaration', 'in', 'IterableStructure']},

        # 条件控制语句
        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block', 'IfExitMarker', 'else', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'IfStatement', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'Block', 'IfExitMarker', 'else', 'BackpatchMarker', 'IfStatement']},
        
        # 循环控制语句
        {'prod_lhs': 'CirculateStatement', 'prod_rhs': ['LoopMarker', 'WhileStatement']},
        {'prod_lhs': 'CirculateStatement', 'prod_rhs': ['LoopMarker', 'ForStatement']},

        {'prod_lhs': 'WhileStatement', 'prod_rhs': ['while', 'BackpatchMarker', 'BranchableExpression', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'ForStatement', 'prod_rhs': ['for', 'ForExpression', 'BackpatchMarker', 'Block']},
        {'prod_lhs': 'LoopStatement', 'prod_rhs': ['LoopMarker', 'loop', 'LoopExprMarker', 'BackpatchMarker', 'Block']},
        

        # Expressions
        {'prod_lhs': 'Expression', 'prod_rhs': ['AddExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['Expression', 'Relop', 'AddExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['FunctionExpressionBlock']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['SelectExpression']},
        {'prod_lhs': 'Expression', 'prod_rhs': ['LoopStatement']},

        {'prod_lhs': 'SelectExpression', 'prod_rhs': ['if', 'BranchableExpression', 'BackpatchMarker', 'FunctionExpressionBlock', 'IfExitMarker', 'else', 'BackpatchMarker', 'FunctionExpressionBlock', 'ElseExitMarkder']},

        {'prod_lhs': 'AddExpression', 'prod_rhs': ['Item']},
        {'prod_lhs': 'AddExpression', 'prod_rhs': ['AddExpression', 'AddOp', 'Item']},

        {'prod_lhs': 'Item', 'prod_rhs': ['Factor']},
        {'prod_lhs': 'Item', 'prod_rhs': ['Item', 'MulOp', 'Factor']},

        {'prod_lhs': 'Factor', 'prod_rhs': ['Element']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['[', 'ArrayElementList', ']']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['[', ']']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['(', 'TupleAssignInner', ')']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['(', ')']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['*', 'Factor']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['&', 'mut', 'Factor']},
        {'prod_lhs': 'Factor', 'prod_rhs': ['&', 'Factor']},

        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'ArrayElementList', 'prod_rhs': ['Expression', ',', 'ArrayElementList']},

        {'prod_lhs': 'TupleAssignInner', 'prod_rhs': ['Expression', ',', 'TupleElementList']},
        {'prod_lhs': 'TupleAssignInner', 'prod_rhs': ['Expression', ',']},

        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'TupleElementList', 'prod_rhs': ['Expression', ',', 'TupleElementList']},

        {'prod_lhs': 'Assignableidentifier', 'prod_rhs': ['*', 'Assignableidentifier']},
        {'prod_lhs': 'Assignableidentifier', 'prod_rhs': ['AssignableidentifierInner']},

        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['Element', '[', 'Expression', ']']},
        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['Element', '.', 'NUM']},
        {'prod_lhs': 'AssignableidentifierInner', 'prod_rhs': ['ID']},

        {'prod_lhs': 'Element', 'prod_rhs': ['NUM']},
        {'prod_lhs': 'Element', 'prod_rhs': ['Assignableidentifier']},
        {'prod_lhs': 'Element', 'prod_rhs': ['(', 'Expression', ')']},
        {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', 'Arguments', ')']},
        {'prod_lhs': 'Element', 'prod_rhs': ['ID', '(', ')']},

        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression']},
        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression', ',']},
        {'prod_lhs': 'Arguments', 'prod_rhs': ['Expression', ',', 'Arguments']},

        # Operators
        {'prod_lhs': 'Relop', 'prod_rhs': ['<']},
        {'prod_lhs': 'Relop', 'prod_rhs': ['<=']},
        {'prod_lhs': 'Relop', 'prod_rhs': ['>']},
        {'prod_lhs': 'Relop', 'prod_rhs': ['>=']},
        {'prod_lhs': 'Relop', 'prod_rhs': ['==']},
        {'prod_lhs': 'Relop', 'prod_rhs': ['!=']},

        {'prod_lhs': 'AddOp', 'prod_rhs': ['+']},
        {'prod_lhs': 'AddOp', 'prod_rhs': ['-']},

        {'prod_lhs': 'MulOp', 'prod_rhs': ['*']},
        {'prod_lhs': 'MulOp', 'prod_rhs': ['/']}
    ],
    'start_symbol' : 'Begin'
}