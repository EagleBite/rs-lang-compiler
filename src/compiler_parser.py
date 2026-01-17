"""Rust-like语法分析器"""
from collections import namedtuple, defaultdict
from compiler_parser_node import ParseNode
from compiler_rust_grammar import RUST_GRAMMAR_PPT
from compiler_semantic_checker import SemanticChecker
from compiler_logger import logger
from enum import Enum
from compiler_lexer import Lexer, LexicalType, LexicalElement

# 定义LR(1)项目
LR1Item = namedtuple('LR1Item', ['lhs', 'rhs', 'dot', 'lookahead'])

class Parser:
    def __init__(self):
        self._first_cache = {}
        self.lexer = Lexer()

    def _setup_grammar(self):
        """初始化文法"""
        self.terminals = set(self.grammar.get('terminals', []))
        self.non_terminals = set(self.grammar.get('non_terminals', []))
        self.rules = defaultdict(list) # defaultdict 用于存储产生式 如果某个非终结符没有产生式，则返回空列表
        self.rule_index_map = {}
        self.start = self.grammar['start_symbol'] #Begin
        for idx, prod in enumerate(self.grammar['productions']): # 遍历产生式列表
            left = prod['prod_lhs']
            right = prod['prod_rhs']
            self.non_terminals.add(left)
            self.rules[left].append({'rhs': right, 'idx': idx})
            self.rule_index_map[idx] = {'lhs': left, 'rhs': right}
        self._print_grammar()

    def closure(self, items):
        """LR(1)闭包"""
        closure_set = set()
        for itm in items:
            closure_set.add(self._dict_to_item(itm) if isinstance(itm, dict) else itm)
        changed = True
        while changed:
            changed = False
            for item in list(closure_set):
                if item.dot < len(item.rhs):
                    B = item.rhs[item.dot]
                    if B in self.non_terminals:
                        beta = item.rhs[item.dot+1:]
                        lookaheads = self.first(beta + (item.lookahead,)) if beta else {item.lookahead}
                        for prod in self.rules[B]:
                            for la in lookaheads:
                                new_item = LR1Item(
                                    lhs=B,
                                    rhs=tuple(prod['rhs']),
                                    dot=0,
                                    lookahead=la
                                )
                                if new_item not in closure_set:
                                    closure_set.add(new_item)
                                    changed = True
        return tuple(sorted(closure_set, key=lambda x: (x.lhs, x.rhs, x.dot, x.lookahead)))

    def goto(self, items, symbol):
        """项目集转移"""
        next_set = set()
        for itm in items:
            cur = self._dict_to_item(itm) if isinstance(itm, dict) else itm
            if cur.dot < len(cur.rhs) and cur.rhs[cur.dot] == symbol:
                next_set.add(LR1Item(
                    lhs=cur.lhs,
                    rhs=cur.rhs,
                    dot=cur.dot + 1,
                    lookahead=cur.lookahead
                ))
        return self.closure(next_set) if next_set else None

    def first(self, symbols, visited=None):
        """计算FIRST集"""
        if visited is None:
            visited = set()
        key = tuple(symbols)
        if key in self._first_cache:
            return self._first_cache[key].copy()
        if key in visited:
            return set()
        visited.add(key)
        result = set()
        if not symbols:
            result.add('')
            return result
        for sym in symbols:
            if sym in self.terminals or sym == '$':
                result.add(sym)
                result.discard('')
                break
            elif sym in self.non_terminals:
                epsilon = False
                for prod in self.rules.get(sym, []):
                    if not prod['rhs']:
                        result.add('')
                        epsilon = True
                        continue
                    sub_first = self.first(prod['rhs'], visited.copy())
                    result.update(sub_first - {''})
                    if '' in sub_first:
                        epsilon = True
                if not epsilon:
                    result.discard('')
                    break
            else:
                raise ValueError(f"未知符号: {sym}")
        self._first_cache[key] = result
        return result

    def build_table(self, grammar):
        """构建LR(1)分析表"""
        self.grammar = grammar
        self._setup_grammar()
        logger.debug("开始构建LR(1)分析表")
        self.action = defaultdict(dict)
        self.goto_tbl = defaultdict(dict)
        self.states = []
        start_prod = self.rules[self.start][0]
        # 第一条产生式作为起始项目
        # logger.info(f"起始产生式: {self.start} → {' '.join(start_prod['rhs']) if start_prod['rhs'] else 'ε'}")
        init_item = LR1Item(  
            lhs=self.start,
            rhs=tuple(start_prod['rhs']),
            dot=0,
            lookahead='$'
        )
        init_state = self.closure([init_item])
        self.states = [init_state]
        queue = [init_state]
        state_map = {init_state: 0}
        self._print_state(0, init_state)
        while queue:
            state = queue.pop(0)
            sid = state_map[state]
            logger.debug(f"处理状态{sid}")
            for sym in self.terminals | self.non_terminals:
                next_state = self.goto(state, sym)
                if next_state and len(next_state) > 0:
                    if next_state not in state_map:
                        new_id = len(self.states)
                        state_map[next_state] = new_id
                        self.states.append(next_state)
                        queue.append(next_state)
                        self._print_state(new_id, next_state)
                    new_id = state_map[next_state]
                    if sym in self.terminals:
                        self.action[sid][sym] = ('shift', new_id)
                    else:
                        self.goto_tbl[sid][sym] = new_id
            for item in state:
                if item.dot == len(item.rhs):
                    if item.lhs == self.start and item.lookahead == '$':
                        self.action[sid]['$'] = ('accept',)
                    else:
                        for prod in self.rules[item.lhs]:
                            if tuple(prod['rhs']) == item.rhs:
                                self.action[sid][item.lookahead] = ('reduce', prod['idx'])
                                break
        logger.debug(f"分析表构建完成，共{len(self.states)}个状态")
        return self.action, self.goto_tbl

    def parse(self, code = None, checker: SemanticChecker = None):
        """LR(1)语法分析"""
        self.lexer.reset(code)
        steps = []
        state_stack = [0]
        node_stack = []
        changed = True
        # token_list = list(tokens)
        while True:
            state = state_stack[-1]
            # cur_token = token_list[idx]
            if changed:
                input_pos = self.lexer._current_pos
                cur_token = self.lexer._get_next_element()
                changed = False
            else:
                cur_token = cur_token
                input_pos = input_pos
            if cur_token.type == LexicalType.EOF:
                logger.debug("到达文件末尾，结束分析")
            offset = self.lexer._current_pos - input_pos
            step = {
                "stack": list(state_stack),
                "node_stack": [str(n) for n in node_stack],
                "input": [code[self.lexer._current_pos-offset:]],
                "action": "",
                "production": ""
            }
            action = self.action[state].get(cur_token.type.value)
            if not action:
                expected = sorted(self.action[state].keys())
                # context = token_list[max(0, idx-2):idx+1]
                context = code[max(0, self.lexer._current_pos-20):self.lexer._current_pos+20]
                raise SyntaxError(
                    f"语法错误（第{cur_token.line}行, 第{cur_token.column}列）\n"
                    f"意外Token: {cur_token}\n"
                    f"期望: {expected}\n"
                    f"上下文: {context}"
                )
            if action[0] == 'shift':
                step["action"] = f"移入: {cur_token} -> 状态{action[1]}"
                terminal_node = ParseNode(
                    symbol=cur_token.type.value,
                    children=None,
                    token=cur_token
                )
                node_stack.append(terminal_node)  # 这里是终结符节点
                changed = True
                state_stack.append(action[1])
            elif action[0] == 'reduce':
                prod_idx = action[1]
                prod = self.rule_index_map[prod_idx]
                lhs = prod['lhs']
                rhs_len = len(prod['rhs'])
                step["production"] = f"{lhs} → {' '.join(prod['rhs']) if prod['rhs'] else 'ε'}"
                step["action"] = f"规约: 使用产生式 {prod_idx}"
                children = []
                if rhs_len > 0:
                    state_stack = state_stack[:-rhs_len]
                    children = node_stack[-rhs_len:]
                    node_stack = node_stack[:-rhs_len]
                new_node = ParseNode(symbol=lhs, children=children)  # 这里是非终结符节点
                if checker:
                    checker.on_reduce(node=new_node)
                node_stack.append(new_node)
                goto_state = self.goto_tbl[state_stack[-1]].get(lhs)
                if goto_state is None:
                    raise SyntaxError(f"无效GOTO：状态{state_stack[-1]}遇到{lhs}")
                state_stack.append(goto_state)
            elif action[0] == 'accept':
                step["action"] = "接受: 分析完成"
                break
            else:
                raise SyntaxError(f"无效动作: {action}")
            steps.append(step)
        return node_stack[0], steps

    @staticmethod
    def _dict_to_item(item_dict: dict) -> LR1Item:
        """dict转LR1Item"""
        prod = item_dict['production']
        return LR1Item(
            lhs=prod['lhs'],
            rhs=tuple(prod['rhs']),
            dot=item_dict['dot_pos'],
            lookahead=item_dict['lookahead']
        )

    def _print_grammar(self):
        """打印文法信息"""
        logger.debug("文法信息：")
        logger.debug(f"起始符号: {self.start}")
        logger.debug(f"终结符({len(self.terminals)}): {', '.join(sorted(self.terminals))}")
        logger.debug(f"非终结符({len(self.non_terminals)}): {', '.join(sorted(self.non_terminals))}")
        logger.debug("产生式：")
        max_lhs = max(len(lhs) for lhs in self.rules) if self.rules else 0
        for lhs in sorted(self.rules.keys()):
            for prod in self.rules[lhs]:
                rhs_str = ' '.join(prod['rhs']) if prod['rhs'] else "ε"
                logger.debug(f"  {lhs.ljust(max_lhs)} → {rhs_str} # {prod['idx']}")

    def _print_state(self, sid, state):
        """打印状态项目集"""
        logger.debug(f"状态 {sid} 项目集:")
        for item in sorted(state, key=lambda x: (x.lhs, x.rhs, x.dot)):
            rhs = list(item.rhs)
            rhs.insert(item.dot, '•')
            prod_str = f"{item.lhs} → {' '.join(rhs) if rhs else 'ε'}"
            logger.debug(f"  {prod_str.ljust(40)} , {item.lookahead}")
            
    

