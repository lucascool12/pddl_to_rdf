from __future__ import annotations
from typing import Callable, Dict, TypeAlias, Tuple, Union
from tree_sitter import Language, Parser, TreeCursor, Node
from pyoxigraph import Store, NamedNode, BlankNode, Quad, Literal
from dataclasses import dataclass
from functools import partial
from collections import deque
import rdflib
import rdflib.namespace as rdfnamespace
import oxrdflib

BUILD_LIB = 'build/langs.so'

Language.build_library(
    BUILD_LIB,
    [
        "tree-sitter-pddl"
    ]
)
PDDL = Language(BUILD_LIB, "pddl")

ont = "http://example.com/pddl_ont/"
rdf_type = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
xsd_decimal = NamedNode("http://www.w3.org/2001/XMLSchema#decimal")

IdentifiedNode: TypeAlias = "BlankNode | NamedNode"
GraphNode: TypeAlias = "BlankNode | NamedNode | Literal"
keywords_alias: TypeAlias = Dict[str,
                                 Tuple[
                                     str,
                                     Callable[
                                         [Node, Node, str],
                                         Tuple[NamedNode, Union[None, GraphNode]]
                                     ]]
                                 ]

def keyword_pred_and_bn(parent_name: Node,
                        node: Node,
                        namespace: str,
                        *,
                        keyword_pred: str) -> Tuple[NamedNode, GraphNode]:
    key_word = get_text(parent_name)
    if parent_name == node:
        return (ontology_named(ont, keyword_pred), BlankNode())
    else:
        return (ontology_named(ont, keywords[key_word][0]),
                NamedNode(namespace + get_text(node)))

def numeric_effect(parent_name: Node,
                   node: Node,
                   namespace: str) -> Tuple[NamedNode, GraphNode]:
    key_word = get_text(parent_name)
    if parent_name == node:
        return (ontology_named(ont, "numericEffect"), BlankNode())
    else:
        text = get_text(node)
        try:
            amount = float(text)
        except ValueError:
            raise Exception(
                f"numeric effect amount is not a number on: {node.start_point}"
            )
        amount_node = Literal(str(amount), datatype=xsd_decimal)
        pred = ontology_named(ont, "with")
        print(pred)
        return (pred, amount_node)


def change_name(parent_name: Node,
            node: Node,
            namespace: str) -> Tuple[NamedNode, None]:
    key_word = get_text(parent_name)
    return (ontology_named(ont, key_word), None)


logical_fn = partial(keyword_pred_and_bn, keyword_pred="logicalExpression")
arithmetic_fn = partial(keyword_pred_and_bn, keyword_pred="arithmeticExpression")

keywords: keywords_alias = {
    "<": ("less_than", arithmetic_fn),
    ">": ("greater_than", arithmetic_fn),
    "<=": ("less_than_or_equal", arithmetic_fn),
    ">=": ("less_than_or_equal", arithmetic_fn),
    "-": ("minus", arithmetic_fn),
    "+": ("plus", arithmetic_fn),
    "*": ("multiply", arithmetic_fn),
    "/": ("divide", arithmetic_fn),
    "and": ("and", logical_fn),
    "not": ("not", logical_fn),
    "or": ("or", logical_fn),
    "increase": ("increase", numeric_effect),
    "decrease": ("decrease", numeric_effect),
    "assign": ("assign", numeric_effect),
    "scale-up": ("scale-up", numeric_effect),
    "scale-down": ("scale-down", numeric_effect),
    ":parameters": ("parameters", change_name),
    ":precondition": ("precondition", change_name),
    ":effect": ("effect", change_name),
}


ignore_node = {
    "comment"
}

def walk_treecursor(cursor: TreeCursor, callback: Callable[[Node, int], None]):
    root = cursor.node
    parent_root = root.parent
    depth = 0
    while True:
        callback(cursor.node, depth)
        print(cursor.node.type)
        # print(get_text(cursor.node))
        if not cursor.goto_first_child():
            if cursor.goto_next_sibling():
                continue
            if not cursor.goto_parent():
                break
            else:
                # if cursor.node == root:
                    # break
                if not cursor.goto_next_sibling():
                    break
                depth -= 1
        else:
            depth += 1

def tree_print(node: Node, depth: int):
    if node.is_named:
        for _ in range(0,depth):
            print("  ", end="")
        print(f"({node.type} {node.start_point} {node.end_point})")

@dataclass
class LatestNode:
    current: BlankNode | NamedNode
    store: Store
    graph: BlankNode
    depth: int
    prev_current: deque[BlankNode | NamedNode]
    amount_on_depth: deque[int]

    def append_current(self, new_current):
        self.prev_current.append(self.current)
        self.current = new_current
        self.amount_on_depth[-1] += 1

    def new_depth(self, depth):
        for _ in range(self.depth, depth):
            self.amount_on_depth.append(0)
        for _ in range(depth, self.depth):
            self.pop()
        self.depth = depth

    def pop(self):
        for _ in range(0, self.amount_on_depth[-1]):
            self.current = self.prev_current.pop()
        self.amount_on_depth.pop()


def translate_walk(node: Node,
                     depth: int,
                     *,
                     parent: LatestNode,
                     namespace: str):
    if node.parent is None or not node.is_named or node.type == "comment":
        parent.new_depth(depth)
        return
    # for _ in range(depth, parent.depth):
    #     parent.pop()
    parent.new_depth(depth)
    parent_stat = get_parent_statement(node)
    state_first = statement_first(parent_stat)
    type = get_type(node.parent)
    # if node == node.parent.named_children[0]:
    #     pass
    if node.type == "name":
        print(get_pred(node, namespace))
        pred = get_pred(node, namespace)
        graph_node = get_graph_node(node, namespace)
        if graph_node is None:
            return
        q = Quad(
            parent.current,
            pred,
            graph_node
        )
        print(q)
        parent.store.add(q)
        if node.parent.named_children[0] == node:
            parent.append_current(graph_node)
    elif node.type == "parameter":
        bn_exists_quad = next(parent.store.quads_for_pattern(
            parent.current,
            ontology_named(ont, "hasParameters"),
            None
        ), None)
        if bn_exists_quad is None:
            graph_node = BlankNode()
        else:
            graph_node = bn_exists_quad.object
            if not isinstance(graph_node, BlankNode):
                raise Exception("Unreachable")
        q = Quad(
            parent.current,
            ontology_named(ont, "hasParameters"),
            graph_node
        )
        print(q)
        parent.store.add(q)
        if type is not None:
            q = Quad(
                graph_node,
                rdf_type,
                ontology_named(ont, get_text(type))
            )
            parent.store.add(q)
        s = graph_node
        p = ontology_named(ont, "parameterName")
        o = Literal(get_text(node))
        exists = next(parent.store.quads_for_pattern(s, p, o), None)
        if exists is None:
            q = Quad(s, p, o)
            parent.store.add(q)
    elif node.type == "statement":
        pass
    print(parent.prev_current)
    print(parent.amount_on_depth)


def get_graph_node(node: Node, namespace: str) -> GraphNode | None:
    node_name = get_text(node)
    parent = node.parent.named_children[0] # type:ignore
    print(node_name)
    print(node_name in keywords)
    if get_text(parent) in keywords or\
        node_name in keywords:
        if get_text(parent) in keywords:
            graph_node: GraphNode | None =\
                keywords[get_text(parent)][1](parent, node, namespace)[1]
        else:
            graph_node = keywords[node_name][1](node, node, namespace)[1]
    elif node_name[0] == ":" and node.parent.named_children[0] == node: # type:ignore
        sib = node.next_named_sibling
        if sib is None or sib.type != "name":
            graph_node = None
        elif get_text(sib)[0] != ":":
            graph_node = NamedNode(namespace + get_text(sib))
        else:
            graph_node = None
    elif node_name[0] == ":":
        graph_node = ontology_named(ont, node_name)
    else:
        graph_node = NamedNode(namespace + node_name)
    return graph_node


def get_pred(node: Node, namespace: str) -> NamedNode:
    orig_node = node
    while True:
        pred = node.parent.prev_named_sibling # type:ignore

        if pred is not None and pred.type == "name":
            pred_text = get_text(pred)
            if pred_text[0] == ":":
                return ontology_named(ont, pred_text[1:len(pred_text)])
            else:
                return ontology_named(ont, pred_text)
        pred = node.parent.named_children[0] # type:ignore
        pred_text = get_text(pred)
        if pred_text[0] == ":":
            return ontology_named(ont, pred_text[1:len(pred_text)])
        if pred_text in keywords:
            return keywords[pred_text][1](pred, orig_node, namespace)[0]
        node = node.parent # type:ignore
        # raise Exception("not implemented or something")


def get_type(node: Node) -> Node | None:
    try:
        type = node.named_children[-1]
        if type.type != "type":
            return None
        return type
    except IndexError:
        return None

def get_text(node: Node) -> str:
    return node.text.decode('utf-8')

def statement_first(node: Node) -> Node:
    return node.named_children[0]

def ontology_named(namespace: str, name: str) -> NamedNode:
    alias = keywords.get(name)
    if alias is not None:
        return NamedNode(namespace + alias[0])
    return NamedNode(namespace + name)

def get_parent_statement(node: Node) -> Node:
    while node.type != "statement":
        node = node.parent # type:ignore
    return node

if __name__ == "__main__":
    pddl_parser = Parser()
    pddl_parser.set_language(PDDL)
    namespace = "http://example.com/test/"
    with open("testsub.pddl") as file:
        test = file.read()
    tree = pddl_parser.parse(bytes(test, 'utf-8'))

    cursor = tree.walk()
    cursor.goto_first_child()
    while cursor.node.type == "comment" or not cursor.node.is_named:
        cursor.goto_next_sibling()
    def_node = statement_first(cursor.node)
    if def_node is None or get_text(def_node) != "define":
        raise Exception("first statement must be define")
    if not cursor.goto_first_child() or\
            not cursor.goto_next_sibling() or\
            not cursor.goto_next_sibling():
        raise Exception("No domain or problem definition")
    prob_or_dom = statement_first(cursor.node)
    try:
        domain_name_node = cursor.node.named_children[1]
    except IndexError:
        raise Exception("missing domain/problem name")
    inst_name = get_text(domain_name_node)
    dom_prob_iri = ontology_named(ont, get_text(prob_or_dom))
    inst_iri = NamedNode(namespace + get_text(domain_name_node))
    latest = LatestNode(inst_iri, Store(), BlankNode(), 0, deque(), deque())
    ptor = partial(translate_walk, parent=latest, namespace=namespace)
    # print(get_text(cursor.node))
    cursor.goto_next_sibling()
    # cursor.goto_next_sibling()
    print(get_text(cursor.node))
    print(cursor.node.type)
    print(Quad(inst_iri, rdf_type, dom_prob_iri))
    latest.store.add(Quad(inst_iri, rdf_type, dom_prob_iri))
    walk_treecursor(cursor, ptor)
    gr = rdflib.ConjunctiveGraph(store=oxrdflib.OxigraphStore(store=latest.store))
    ex = rdflib.Namespace(namespace)
    ont = rdflib.Namespace(ont)
    nsm = rdfnamespace.NamespaceManager(gr)
    nsm.bind("ex", ex)
    nsm.bind("ont", ont)
    gr.serialize("test.ttl", "turtle")


