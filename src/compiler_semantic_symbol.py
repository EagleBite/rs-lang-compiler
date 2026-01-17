from dataclasses import dataclass, field
from typing import Optional, List, Dict, Union
from compiler_logger import logger

# -------------------- 类型系统定义 --------------------
@dataclass
class UnitType:
    """无实际返回值的类型，用于无返回函数"""
    @property
    def name(self) -> str:
        return "unit"
    
    def __eq__(self, other) -> bool:
        return isinstance(other, UnitType)

@dataclass
class UninitializedType:
    """尚未初始化的类型，可能已知实际类型"""
    inner_type: "Type"
    is_mutable: bool = False

@dataclass
class BaseType:
    name: str  # 基本类型，例如 "i32", "bool"
    is_mutable: bool = False

@dataclass
class ArrayType:
    element_type: 'Type'
    size: int
    is_mutable: bool = False

@dataclass
class RangeType:
    element_type: 'Type'
    start: Optional[int] = None
    end: Optional[int] = None
    step: int = 1

@dataclass
class TupleType:
    members: List['Type']
    is_mutable: bool = False

@dataclass
class ReferenceType:
    target_type: 'Type'
    is_mutable: bool

@dataclass
class OperatorType:
    category: str
    op: str

    @property
    def name(self) -> str:
        return f"operator_{self.op}"

    def __eq__(self, other) -> bool:
        return isinstance(other, OperatorType) and self.op == other.op

    def __str__(self) -> str:
        return self.name

Type = Union[UnitType, UninitializedType, BaseType, ArrayType, TupleType, ReferenceType, OperatorType, RangeType]

def type_to_string(ty: Type) -> str:
    """将类型对象转换为字符串形式"""
    if isinstance(ty, UnitType):
        return ty.name
    elif isinstance(ty, UninitializedType):
        return f"<uninitialized {type_to_string(ty.inner_type)}>"
    elif isinstance(ty, BaseType):
        return ty.name
    elif isinstance(ty, ArrayType):
        return f"[{type_to_string(ty.element_type)}; {ty.size}]"
    elif isinstance(ty, TupleType):
        return f"({', '.join(type_to_string(m) for m in ty.members)})"
    elif isinstance(ty, ReferenceType):
        prefix = "mut " if ty.is_mutable else ""
        return f"&{prefix}{type_to_string(ty.target_type)}"
    elif isinstance(ty, OperatorType):
        return str(ty)

# -------------------- 符号系统定义 --------------------
class Symbol:
    """通用符号基类"""
    def __init__(self, name: str):
        self.name = name
        self.type_str: str = ""

    def set_type_obj(self, type_obj: Type):
        """设置类型对象并生成对应的字符串形式"""
        self.type_obj = type_obj
        self.type_str = type_to_string(type_obj)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name} {self.type_str}>"

class VariableSymbol(Symbol):
    """变量符号定义"""
    def __init__(self, name: str, type_obj: Optional[Type] = None):
        super().__init__(name)
        if type_obj:
            self.set_type_obj(type_obj)

    def __repr__(self):
        mut = "mut " if getattr(self.type_obj, 'is_mutable', False) else ""
        init_flag = " (initialized)" if isinstance(self.type_obj, UninitializedType) else ""
        return f"<Var {mut}{self.name}: {getattr(self, 'type_str', '<?>')}{init_flag}>"

class ParameterSymbol(Symbol):
    """函数参数符号"""
    def __init__(self, name: str, type_obj: Type, position: int = 0):
        super().__init__(name)
        self.type_obj = type_obj
        self.position = position

    def __repr__(self):
        mut = "mut " if self.type_obj.is_mutable else ""
        return f"<Param {mut}{self.name}: {self.type_str} @{self.position}>"

class FunctionSymbol(Symbol):
    """函数定义符号"""
    def __init__(self, quad_index: int, name: str, return_type_obj: Optional[Type] = None,
                 parameters: Optional[List[VariableSymbol]] = None):
        super().__init__(name)
        self.quad_index = quad_index
        self.return_type_obj = return_type_obj or UnitType()
        self.parameters = parameters or []
        self.set_type_obj(self._compose_func_type())

    def _compose_func_type(self) -> Type:
        """构造函数签名类型"""
        param_tuple = TupleType([p.type_obj for p in self.parameters])
        return TupleType([param_tuple, self.return_type_obj])

    def __repr__(self):
        param_str = ", ".join(str(p) for p in self.parameters)
        return f"<Fn {self.name}({param_str}) -> {self.type_str}>"

# -------------------- 作用域系统 --------------------
class Scope:
    """作用域对象"""
    def __init__(self, name: str, parent: Optional['Scope'] = None):
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}

    def insert(self, symbol: Symbol) -> bool:
        """插入新符号，允许重影"""
        self.symbols[symbol.name] = symbol
        return True

    def lookup(self, name: str, current_scope_only: bool = False) -> Optional[Symbol]:
        """查找符号，可设置是否仅查当前作用域"""
        if name in self.symbols:
            return self.symbols[name]
        if not current_scope_only and self.parent:
            return self.parent.lookup(name)
        return None
    
    def lookup_all_vars(self) -> List[VariableSymbol]:
        """查找当前作用域所有变量符号"""
        return [sym for sym in self.symbols.values() if isinstance(sym, VariableSymbol)]

# -------------------- 符号表主控制器 --------------------
class SymbolTable:
    """符号表总管理器"""
    def __init__(self):
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self._type_registry: Dict[str, Type] = {
            "i32": BaseType("i32"),
            "bool": BaseType("bool"),
        }
        self.scopes: List[Scope] = [self.global_scope]

    def enter_scope(self, name: str):
        """进入一个新作用域"""
        self.current_scope = Scope(name, self.current_scope)
        self.scopes.append(self.current_scope)
        
    def find_scope(self, name: str) -> Optional[Scope]:
        """查找指定名称的作用域"""
        for scope in reversed(self.scopes):
            if scope.name == name:
                return scope
        return None

    def exit_scope(self):
        """退出当前作用域"""
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def register_type(self, name: str, type_obj: Type) -> bool:
        """向类型表注册新类型"""
        if name in self._type_registry:
            logger.warning(f"🔍  重复类型定义: {name}")
            return False
        self._type_registry[name] = type_obj
        logger.info(f"🔄  已注册类型: {name} => {type_obj}")
        return True

    def lookup_type(self, name: str) -> Optional[Type]:
        """查找类型定义"""
        return self._type_registry.get(name)

    def insert(self, symbol: Symbol) -> bool:
        """插入符号到当前作用域"""
        return self.current_scope.insert(symbol)

    def lookup(self, name: str, current_scope_only=False) -> Optional[Symbol]:
        """从当前或父作用域查找符号"""
        symbol = self.current_scope.lookup(name, current_scope_only)
        return symbol

    def lookup_current_scope(self, name: str) -> Optional[Symbol]:
        """仅查找当前作用域内的符号"""
        return self.lookup(name, current_scope_only=True)

    def get_function(self, name: str) -> Optional[FunctionSymbol]:
        """仅在全局作用域中查找函数符号"""
        symbol = self.global_scope.lookup(name)
        return symbol if isinstance(symbol, FunctionSymbol) else None

if __name__ == "__main__":
    # 测试符号表和类型系统
    symbol_table = SymbolTable()
    symbol_table.register_type("f32", BaseType("f32"))
    
    var_x = VariableSymbol("x", BaseType("i32"))
    symbol_table.insert(var_x)
    
    func_main = FunctionSymbol(quad_index=0, name="main", return_type_obj=UnitType())
    symbol_table.insert(func_main)
    
    # print(symbol_table.lookup("x"))  # <Var x: i32>
    print(symbol_table.get_function("main").quad_index)  # <Fn main() -> unit>
    # print(symbol_table.lookup_type("f32"))  # f32
