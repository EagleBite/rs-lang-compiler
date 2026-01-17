"""
词法分析器
可分析元素：关键字、标识符、常量、运算符、界符、注释
分析流程：空白、注释、数字、字符串、标识符和关键字、界符、其他、文件结束符

输入内容：源代码
输出内容：词汇元素列表
"""
import os
import sys
sys.path.append(os.getcwd())
from enum import Enum
from compiler_logger import logger

class LexicalType(Enum):
    """词汇类型：元组(值，是否是关键字，是否是运算符，是否是界符)"""
    # 关键字
    FN = ('fn', True, False, False)                     # 函数
    LET = ('let', True, False, False)                   # 变量声明
    MUT = ('mut', True, False, False)                   # 可变声明
    IF = ('if', True, False, False)                     # 条件语句
    ELSE = ('else', True, False, False)                 # 条件语句（否则）
    WHILE = ('while', True, False, False)               # 循环
    RETURN = ('return', True, False, False)             # 返回
    FOR = ('for', True, False, False)                   # for 循环
    IN = ('in', True, False, False)                     # for-in 语句中的 in
    LOOP = ('loop', True, False, False)                 # 无限循环
    BREAK = ('break', True, False, False)               # 跳出循环
    CONTINUE = ('continue', True, False, False)         # 跳过当前循环
    I32 = ('i32', True, False, False)                   # 类型：32位整数

    # 标识符
    IDENTIFIER = ('ID', False, False, False)

    # 常量
    INTEGER = ('NUM', False, False, False)              # 整数
    FLOAT = ('NUM', False, False, False)                # 浮点数
    STRING = ('STRING', False, False, False)            # 字符串
    CHAR = ('CHAR', False, False, False)                # 字符
    BOOL = ('BOOL', False, False, False)                # 布尔值

    # 运算符
    # 基础算术运算符
    PLUS = ('+', False, True, False)                    # +
    MINUS = ('-', False, True, False)                   # -
    MULTIPLY = ('*', False, True, False)                # *
    DIVIDE = ('/', False, True, False)                  # /
    MOD = ('%', False, True, False)                     # %
    # 比较运算符
    EQUAL = ('==', False, True, False)                  # ==  
    NOT_EQUAL = ('!=', False, True, False)              # !=
    LESS = ('<', False, True, False)                    # <
    GREATER = ('>', False, True, False)                 # >
    LESS_EQUAL = ('<=', False, True, False)             # <=
    GREATER_EQUAL = ('>=', False, True, False)          # >=
    # 逻辑运算符
    AND = ('&&', False, True, False)                    # &&
    OR = ('||', False, True, False)                     # ||
    NOT = ('!', False, True, False)                     # !
    # 位运算符
    BIT_AND = ('&', False, True, False)                 # &
    BIT_OR = ('|', False, True, False)                  # |
    BIT_XOR = ('^', False, True, False)                 # ^
    BIT_NOT = ('~', False, True, False)                 # ~
    SHIFT_LEFT = ('<<', False, True, False)             # <<
    SHIFT_RIGHT = ('>>', False, True, False)            # >>
    # 赋值运算符
    ASSIGN = ('=', False, True, False)                  # =
    ADD_ASSIGN = ('+=', False, True, False)             # +=
    SUB_ASSIGN = ('-=', False, True, False)             # -=
    MUL_ASSIGN = ('*=', False, True, False)             # *=
    DIV_ASSIGN = ('/=', False, True, False)             # /=
    MOD_ASSIGN = ('%=', False, True, False)             # %=
    AND_ASSIGN = ('&=', False, True, False)             # &=
    OR_ASSIGN = ('|=', False, True, False)              # |=
    XOR_ASSIGN = ('^=', False, True, False)             # ^=
    SHIFT_LEFT_ASSIGN = ('<<=', False, True, False)     # <<=
    SHIFT_RIGHT_ASSIGN = ('>>=', False, True, False)    # >>=
    # 自增/自减
    INCREMENT = ('++', False, True, False)              # ++
    DECREMENT = ('--', False, True, False)              # --

    # 界符
    # 单字符界符和分隔符
    SEMICOLON = (';', False, False, True)               # ;
    COMMA = (',', False, False, True)                   # ,
    DOT = ('.', False, False, True)                     # .
    COLON = (':', False, False, True)                   # :
    LPAREN = ('(', False, False, True)                  # (
    RPAREN = (')', False, False, True)                  # )
    LBRACE = ('{', False, False, True)                  # {
    RBRACE = ('}', False, False, True)                  # }
    LBRACKET = ('[', False, False, True)                # [
    RBRACKET = (']', False, False, True)                # ]
    QUESTION = ('?', False, False, True)                # ?
    # 双字符界符和分隔符
    DOUBLE_COLON = ('::', False, False, True)           # ::
    ARROW = ('->', False, False, True)                  # ->
    DOTDOT = ('..', False, False, True)                 # ..

    # 结束符
    EOF = ('$', False, False, False)

    @property
    def value(self):
        return self._value_[0]
    @property
    def is_keyword(self):
        return self._value_[1]
    @property
    def is_operator(self):
        return self._value_[2]
    @property
    def is_delimiter(self):
        return self._value_[3]

class LexicalElement:
    """词汇元素"""
    def __init__(self, type_: LexicalType, value_=None, row_=None, col_=None):
        self.type: LexicalType = type_
        self.value = value_
        self.line = row_ # 所在行号
        self.column = col_ # 所在列号（按标识符起始位置）
    
    def __str__(self):
        # 序列化：[Type:value]（值为空时省略:value）
        return f"[{self.type.name}]" if self.value is None else f"[{self.type.name}:{self.value}]"

class Lexer:
    """词法分析器"""
    def __init__(self):
        self._last_token = None # 上一个词法元素
    def _error(self, msg):
        message = f"LexicalParser error at line {self._current_row}, column {self._current_col}: {msg}"
        logger.error(message)
        raise Exception(message)
    
    def _move_next(self):
        """移动到下一个字符"""
        if self._current_char == '\n': # 换行
            self._current_row += 1
            self._current_col = 0
        self._current_pos += 1
        self._current_col += 1
        self._current_char = self._input_text[self._current_pos] if self._current_pos < len(self._input_text) else None # 刷新char

    def _peek_next(self, n=1):
        """预览接下来的第n个字符"""
        return self._input_text[self._current_pos + n] if self._current_pos + n < len(self._input_text) else None
        
    def _ignore_whitespace(self):
        """忽略空白字符"""
        while self._current_char is not None and self._current_char.isspace():
            self._move_next()

    def _ignore_comment(self):
        """忽略注释"""
        # 单行注释
        if self._current_char == '/' and self._peek_next() == '/':
            # 跳过接下来的整行内容
            while self._current_char is not None and self._current_char != '\n':
                self._move_next()
        # 多行注释
        elif self._current_char == '/' and self._peek_next() == '*':
            # 跳过/*
            self._move_next()
            self._move_next()
            # 跳过内容，直到*/
            while self._current_char is not None and (self._current_char != '*' or self._peek_next() != '/'):
                if self._current_char == '\n':
                    self._current_row += 1
                    self._current_col = 0
                self._move_next()
            if self._current_char is None: # 如果直到文件结束都没有找到*/，报错
                self._error("Unterminated multi-line comment")
            # 跳过*/
            self._move_next()
            self._move_next()

    def _process_number(self):
            start_row = self._current_row
            start_col = self._current_col
            buffer = ''
            is_float = False
            
            # 处理负号（当满足一元操作符条件时）
            if self._current_char == '-':
                if self._peek_next() and self._peek_next().isdigit():
                    # 检查负号是否属于一元操作符（表达式开头/运算符/界符后）
                    if self._last_token is None or self._last_token.type not in [
                        LexicalType.IDENTIFIER, 
                        LexicalType.INTEGER, LexicalType.FLOAT,
                        LexicalType.STRING, LexicalType.CHAR, LexicalType.BOOL,
                        LexicalType.RPAREN, LexicalType.RBRACE, LexicalType.RBRACKET
                    ]:
                        buffer = '-'
                        self._move_next()  # 跳过负号
                    else:
                        token = self._process_operator()  # 处理负号作为运算符
                        if token:  # 如果是有效的运算符
                            self._last_token = token  # 更新last_token
                            return token  # 返回运算符元素
            
            # 处理数字部分（整数部分）
            while self._current_char and self._current_char.isdigit():
                buffer += self._current_char
                self._move_next()
            
            # 处理浮点数（小数点后必须跟数字）
            if self._current_char == '.' and self._peek_next() and self._peek_next().isdigit():
                is_float = True
                buffer += self._current_char
                self._move_next()
                while self._current_char and self._current_char.isdigit():
                    buffer += self._current_char
                    self._move_next()
            
            try:
                value = float(buffer) if is_float else int(buffer)
                return LexicalElement(
                    LexicalType.FLOAT if is_float else LexicalType.INTEGER, 
                    value, start_row, start_col
                )
            except ValueError:
                self._error(f"Invalid numeric literal: {buffer}")

    def _process_string(self):
        """处理字符串"""
        start_row = self._current_row # 缓存起始行号
        start_col = self._current_col # 缓存起始列号
        escape_mappings = { # 转义字符字符串与转义字符实体映射
            'n': '\n',
            't': '\t',
            'r': '\r',
            '\\': '\\',
            '"': '"',
            "'": "'",
            '0': '\0'
        }
        buffer = [] # 存储字符串

        self._move_next() # 跳过开始的引号
        while self._current_char and self._current_char != '"': # 循环直到引号结束
            if self._current_char != '\\': # 非转义字符字符串前缀，即普通字符
                buffer.append(self._current_char)
            else: # 转义字符处理
                self._move_next() # 跳过\
                if not self._current_char: # 如果文件结束，退出
                    break
                # 获取转义字符实体，未知转义字符将不会进行转义，直接输出原字符
                buffer.append(escape_mappings.get(self._current_char, f"\\{self._current_char}"))
            self._move_next()
        if self._current_char is None: # 如果直到文件结束都没有找到"，报错
            self._error("Unterminated string literal")
        self._move_next() # 跳过结束的引号
        # 返回字符串元素
        return LexicalElement(LexicalType.STRING, ''.join(buffer), start_row, start_col)
    
    def _process_identifier(self):
        """处理标识符/关键字"""
        start_row = self._current_row # 缓存起始行号
        start_col = self._current_col # 缓存起始列号
        keyword_mappings = {ele.value: ele for ele in LexicalType if ele.is_keyword} # 关键字映射
        buffer = [] # 存储标识符

        # 匹配标识符，允许字母数字下划线
        while self._current_char and (self._current_char.isalnum() or self._current_char == '_'):
            buffer.append(self._current_char)
            self._move_next()
        identifier = ''.join(buffer) # 拼接成字符串
        lexical_type = keyword_mappings.get(identifier, LexicalType.IDENTIFIER) # 是否是关键字
        return LexicalElement(lexical_type, identifier, start_row, start_col)
    
    def _process_operator(self):
        """处理运算符"""
        start_row = self._current_row # 缓存起始行号
        start_col = self._current_col # 缓存起始列号
        operator_mappings = {ele.value: ele for ele in LexicalType if ele.is_operator} # 运算符映射

        # 尝试匹配三字符运算符
        if self._current_char and self._peek_next() and self._peek_next(2):
            op = self._current_char + self._peek_next() + self._peek_next(2)
            if op in operator_mappings: # 如果是三字符运算符
                self._move_next()
                self._move_next()
                self._move_next()
                return LexicalElement(operator_mappings[op], op, start_row, start_col)
        # 尝试匹配双字符运算符
        if self._current_char and self._peek_next(): # 如果有足够的字符
            op = self._current_char + self._peek_next()
            if op in operator_mappings: # 如果是双字符运算符
                self._move_next()
                self._move_next()
                return LexicalElement(operator_mappings[op], op, start_row, start_col)
            if op == '->': # 如果是->，退出，将转_process_delimiters处理
                return None
        # 单字符运算符处理
        if self._current_char in operator_mappings:
            op = self._current_char
            self._move_next()
            return LexicalElement(operator_mappings[op], op, start_row, start_col)
        return None

    def _process_delimiters(self):
        """处理界符，返回对应的LexicalElement"""
        start_row = self._current_row # 缓存起始行号
        start_col = self._current_col # 缓存起始列号
        delimiter_mappings = {ele.value: ele for ele in LexicalType if ele.is_delimiter} # 界符映射

        # 双字符界符检查
        if self._current_char and self._peek_next():
            str = self._current_char + self._peek_next()
            if str in delimiter_mappings:
                self._move_next()
                self._move_next()
                return LexicalElement(delimiter_mappings[str], str, start_row, start_col)
        # 单字符界符检查
        if self._current_char in delimiter_mappings:
            str = self._current_char
            self._move_next()
            return LexicalElement(delimiter_mappings[str], str, start_row, start_col)
        return None

    def _get_next_element(self):
        """获取下一个LexicalElement"""
        while self._current_char is not None:
            if self._current_char.isspace():                             # 忽略空白
                self._ignore_whitespace()
                continue
            if self._current_char == '/' and (self._peek_next() == '/' or self._peek_next() == '*'): # 忽略注释
                self._ignore_comment()
                continue
                
            # 处理数字（包括负数）
            if self._current_char and (self._current_char.isdigit() or 
                (self._current_char == '-' and self._peek_next() and self._peek_next().isdigit())):
                token = self._process_number()
                if token:
                    self._last_token = token  # 更新last_token
                    return token
                    
            # 处理字符串
            if self._current_char == '"':                                
                token = self._process_string()
                self._last_token = token  # 更新last_token
                return token
                
            # 处理标识符和关键字
            if self._current_char.isalpha() or self._current_char == '_': 
                token = self._process_identifier()
                self._last_token = token  # 更新last_token
                return token
                
            # 处理运算符
            if operator_token := self._process_operator():              
                self._last_token = operator_token  # 更新last_token
                return operator_token
                
            # 处理界符
            if delimiter_token := self._process_delimiters():           
                self._last_token = delimiter_token  # 更新last_token
                return delimiter_token
                
            self._error(f"Unknown character: {self._current_char}")      # 其他
        
        # 文件结束
        eof_token = LexicalElement(LexicalType.EOF, None, self._current_row, self._current_col)
        self._last_token = eof_token  # 更新last_token
        return eof_token
    
    def _log_parsing_result(self, elements):
        """输出词法分析结果"""
        from collections import defaultdict
        results = defaultdict(list) # 创建一个默认字典，用于存储行号和对应的LexicalElement列表
        for element in elements:
            results[element.line].append(element) # 将每个LexicalElement添加到对应的行中

        # 打印
        logger.info("====== LEXER RESULT START ======")
        for row_num, code_line in enumerate(self._input_text.split('\n'), 1):
            logger.info(f"{row_num:4d} | {code_line}")
            if row_num in results: # 如果该行有LexicalElement
                logger.info(f"      -> {' '.join([str(token) for token in results[row_num]])}")
        logger.info("======= LEXER RESULT END =======")

    def analyse(self, input_text):
        """
        词法分析，LexicalParser类的唯一公共方法，返回一个LexicalElement列表
        
        :param input_text_: 输入文本
        """
        # 重置解析器状态
        self._input_text = input_text or "" # 输入文本
        self._current_pos = 0 # 当前位置
        self._current_row = 1 # 当前行号
        self._current_col = 1 # 当前列号
        self._current_char = self._input_text[0] if self._input_text else None # 当前字符
        # 词法分析
        elements = []
        while True:
            elements.append(self._get_next_element())
            if elements[-1].type == LexicalType.EOF: # 如果是文件结束符，结束循环
                break
        self._log_parsing_result(elements)
        return elements
    
    def reset(self, input_text=None):
        """重置词法分析器状态"""
        self._input_text = input_text or "" # 输入文本
        self._current_pos = 0 # 当前位置
        self._current_row = 1 # 当前行号
        self._current_col = 1 # 当前列号
        self._current_char = self._input_text[0] if self._input_text else None # 当前字符
