#! python
from __future__ import annotations
from typing import Callable, Dict, Tuple, Union, List
from typing_extensions import TypeAlias
from tree_sitter import Language, Parser, TreeCursor, Node
from pyoxigraph import Store, NamedNode, BlankNode, Quad, Literal
from dataclasses import dataclass
from functools import partial
from collections import deque
import rdflib
import rdflib.namespace as rdfnamespace
import oxrdflib
import argparse
import sys
import os

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
rdf_value = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#value")
xsd_decimal = NamedNode("http://www.w3.org/2001/XMLSchema#decimal")

IdentifiedNode = "BlankNode | NamedNode"
GraphNode = "BlankNode | NamedNode | Literal"
keywords_alias = """Dict[str,
                                 Tuple[
                                     str,
                                     Callable[
                                         [Node, Node, LatestNode, str],
                                         Tuple[
                                            NamedNode,
                                            Union[None, GraphNode],
                                            List[Tuple[Quad, bool]]
                                            ]
                                     ]]
                                 ]"""

def keyword_pred_and_bn(parent_name: Node,
                        node: Node,
                        latest: LatestNode,
                        namespace: str,
                        *,
                        keyword_pred: str)\
        -> Tuple[NamedNode, GraphNode | None, List[Tuple[Quad, bool]]]:
    key_word = get_text(parent_name)
    key_word = keywords[key_word][0]
    if parent_name == node:
        quads = list()
        bn1 = BlankNode()
        bn2 = BlankNode()
        quads.append((Quad(
            bn2,
            ontology_named(ont, key_word),
            bn1
        ), True))
        return (ontology_named(ont, key_word), bn2, quads)
    else:
        text = get_text(node)
        if text in keywords:
            graph_node = keywords[text][1](node, node, latest, namespace)
            return (rdf_value, graph_node[1], graph_node[2])
        else:
            graph_node = NamedNode(namespace + text)
        return (rdf_value, graph_node, [])

def numeric_effect(parent_name: Node,
                   node: Node,
                   latest: LatestNode,
                   namespace: str) -> Tuple[NamedNode, GraphNode, List[Tuple[Quad, bool]]]:
    key_word = get_text(parent_name)
    key_word = keywords[key_word][0]
    if parent_name == node:
        quads = list()
        bn1 = BlankNode()
        bn2 = BlankNode()
        quads.append((Quad(
            bn2,
            ontology_named(ont, key_word),
            bn1
        ), True))
        return (ontology_named(ont, key_word), bn2, quads)
    elif next(latest.store.quads_for_pattern(
        latest.current,
        rdf_value,
        None), None) is None:
        text = get_text(node)
        try:
            float(text)
            number = True
        except ValueError:
            number = False
        if number:
            amount_node: GraphNode = Literal(text, datatype=xsd_decimal)
        else:
            amount_node = NamedNode(namespace + text)
        pred = rdf_value
        return (pred, amount_node, [])
    else:
        text = get_text(node)
        try:
            float(text)
            number = True
        except ValueError:
            number = False
        if number:
            amount_node = Literal(text, datatype=xsd_decimal)
        else:
            amount_node = NamedNode(namespace + text)
        pred = ontology_named(ont, "with")
        return (pred, amount_node, [])

def no_node(parent_name: Node,
            node: Node,
            latest: LatestNode,
            namespace: str) -> Tuple[NamedNode, None, List[Tuple[Quad, bool]]]:
    key_word = get_text(parent_name)
    return (ontology_named(ont, key_word), None, [])

def init_node(parent_name: Node,
            node: Node,
            latest: LatestNode,
            namespace: str) -> Tuple[NamedNode, GraphNode | None, List[Tuple[Quad, bool]]]:
    key_word = keywords[get_text(parent_name)][0]
    if parent_name == node:
        text = get_text(node)
        graph_node = NamedNode(namespace + text)
        return (ontology_named(ont, key_word), BlankNode(), [])
    else:
        text = get_text(node)
        if text in keywords:
            key_word = keywords[text][0]
            graph_nodes = keywords[text][1](node, node, latest, namespace)
            return (ontology_named(ont, "predicate"), graph_nodes[1], [])
        else:
            graph_node = NamedNode(namespace + text)
        return (ontology_named(ont, "predicate"), graph_node, [])

def predicate_node(parent_name: Node,
            node: Node,
            latest: LatestNode,
            namespace: str) -> Tuple[NamedNode, GraphNode | None, List[Tuple[Quad, bool]]]:
    key_word = keywords[get_text(parent_name)][0]
    if parent_name == node:
        return (ontology_named(ont, key_word), None, [])
    else:
        quads = []
        graph_node = NamedNode(namespace + get_text(node))
        quads.append((Quad(
            graph_node,
            rdf_type,
            ontology_named(ont, "Predicate")
        ), False))
        return (ontology_named(ont, key_word), graph_node, quads)


logical_fn = partial(keyword_pred_and_bn, keyword_pred="logicalExpression")
arithmetic_fn = partial(keyword_pred_and_bn, keyword_pred="arithmeticExpression")

keywords: keywords_alias = {
    "<": ("less_than", numeric_effect),
    ">": ("greater_than", numeric_effect),
    "<=": ("less_than_or_equal", numeric_effect),
    ">=": ("less_than_or_equal", numeric_effect),
    "=": ("equals", numeric_effect),
    "-": ("minus", numeric_effect),
    "+": ("plus", numeric_effect),
    "*": ("multiply", numeric_effect),
    "/": ("divide", numeric_effect),
    "and": ("and", logical_fn),
    "not": ("not", logical_fn),
    "or": ("or", logical_fn),
    "increase": ("increase", numeric_effect),
    "decrease": ("decrease", numeric_effect),
    "assign": ("assign", numeric_effect),
    "scale-up": ("scale-up", numeric_effect),
    "scale-down": ("scale-down", numeric_effect),
    ":parameters": ("parameters", no_node),
    ":precondition": ("precondition", no_node),
    ":effect": ("effect", no_node),
    ":init": ("init", init_node),
    ":predicates": ("hasPredicate", predicate_node),
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
        if len(self.amount_on_depth) != 0:
            for _ in range(0, self.amount_on_depth[-1]):
                self.current = self.prev_current.pop()
            self.amount_on_depth.pop()


def translate_walk(node: Node,
                     depth: int,
                     *,
                     latest: LatestNode,
                     namespace: str):
    if node.parent is None or not node.is_named or node.type == "comment":
        latest.new_depth(depth)
        return
    latest.new_depth(depth)
    parent_stat = get_parent_statement(node)
    state_first = statement_first(parent_stat)
    type = get_type(node.parent)
    if node.type == "name":
        pred = get_pred(node, latest, namespace)
        graph_node, post_add = get_graph_node(node, latest, namespace)
        if graph_node is None:
            return
        q = Quad(
            latest.current,
            pred,
            graph_node
        )
        latest.store.add(q)
        if node.parent.named_children[0] == node:
            latest.append_current(graph_node)
        for el in post_add:
            latest.store.add(el[0])
            if el[1]:
                latest.append_current(el[0].object)
    elif node.type == "parameter":
        bn_exists_quad = next(latest.store.quads_for_pattern(
            latest.current,
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
            latest.current,
            ontology_named(ont, "hasParameters"),
            graph_node
        )
        latest.store.add(q)
        if type is not None:
            q = Quad(
                graph_node,
                rdf_type,
                ontology_named(ont, get_text(type))
            )
            latest.store.add(q)
        s = graph_node
        p = ontology_named(ont, "parameterName")
        o = Literal(get_text(node))
        exists = next(latest.store.quads_for_pattern(s, p, o), None)
        if exists is None:
            q = Quad(s, p, o)
            latest.store.add(q)
    elif node.type == "statement":
        pass


def get_graph_node(node: Node,
                   latest: LatestNode,
                   namespace: str) -> Tuple[GraphNode | None, List[Tuple[Quad, bool]]]:
    node_name = get_text(node)
    parent = node.parent.named_children[0] # type:ignore
    if parent == node:
        parent_parent = node.parent.parent.named_children[0] # type: ignore
    else:
        parent_parent = None
    end_add = []
    if get_text(parent) in keywords or\
        node_name in keywords or\
            (parent_parent is not None and\
             get_text(parent_parent) in keywords):
        if node_name in keywords:
            out = keywords[node_name][1](parent, node, latest, namespace)
            graph_node: GraphNode | None = out[1]
        elif parent_parent is not None and\
                get_text(parent_parent) in keywords:
            out = keywords[get_text(parent_parent)][1]\
                (parent_parent, node, latest, namespace)
            graph_node = out[1]
        else:
            out = keywords[get_text(parent)][1](parent, node, latest, namespace)
            graph_node = out[1]
        end_add = out[2]
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
    # elif node.parent.named_children[0] == node: # type:ignore
    elif get_text(node.parent.named_children[0])[0] == ":": # type: ignore
        graph_node = None
    else:
        graph_node = NamedNode(namespace + node_name)
    # else:
        # graph_node = None
    return (graph_node, end_add)


def get_pred(node: Node, latest: LatestNode, namespace: str) -> NamedNode:
    orig_node = node
    while True:
        pred1 = node.parent.named_children[0] # type:ignore
        if pred1 != orig_node:
            pred_text = get_text(pred1)
            if pred_text in keywords:
                return keywords[pred_text][1](pred1, orig_node, latest, namespace)[0]

        pred = node.parent.prev_named_sibling # type:ignore
        while pred is not None and pred.type == "comment":
            pred = pred.prev_named_sibling
        if pred is not None and pred.type == "name":
            pred_text = get_text(pred)
            if pred_text in keywords:
                return keywords[pred_text][1](pred, orig_node, latest, namespace)[0]
            if pred_text[0] == ":":
                return ontology_named(ont, pred_text[1:len(pred_text)])
            # else:
                # return ontology_named(ont, pred_text)

        pred1 = node.parent.named_children[0] # type:ignore
        pred_text = get_text(pred1)
        if pred_text[0] == ":":
            return ontology_named(ont, pred_text[1:len(pred_text)])
        node = node.parent # type:ignore


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

def next_sibling_ignore_comment(cursor: TreeCursor) -> bool:
    if not cursor.goto_next_sibling():
        return False
    while cursor.node.type == "comment":
        if not cursor.goto_next_sibling():
            return False
    return True

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-i", "--input_file", nargs='?', type=argparse.FileType("r"),
                           default=sys.stdin)
    argparser.add_argument("-o", "--output_file", nargs='?', type=argparse.FileType("w"),
                           default=sys.stdout)
    args = argparser.parse_args()
    pddl_parser = Parser()
    pddl_parser.set_language(PDDL)
    namespace = "http://example.com/test/"
    test = args.input_file.read()
    tree = pddl_parser.parse(bytes(test, 'utf-8'))

    cursor = tree.walk()
    cursor.goto_first_child()
    while cursor.node.type == "comment" or not cursor.node.is_named:
        cursor.goto_next_sibling()
    def_node = statement_first(cursor.node)
    if def_node is None or get_text(def_node) != "define":
        raise Exception("first statement must be define")
    if not cursor.goto_first_child() or\
            not next_sibling_ignore_comment(cursor) or\
            not next_sibling_ignore_comment(cursor):
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
    ptor = partial(translate_walk, latest=latest, namespace=namespace)
    cursor.goto_next_sibling()
    latest.store.add(Quad(inst_iri, rdf_type, dom_prob_iri))
    walk_treecursor(cursor, ptor)
    gr = rdflib.ConjunctiveGraph(store=oxrdflib.OxigraphStore(store=latest.store))
    ex = rdflib.Namespace(namespace)
    ont = rdflib.Namespace(ont)
    nsm = rdfnamespace.NamespaceManager(gr)
    nsm.bind("ex", ex)
    nsm.bind("ont", ont)
    args.output_file.write(gr.serialize(None, "turtle"))


