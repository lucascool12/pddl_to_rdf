from __future__ import annotations
from typing import Callable
from tree_sitter import Language, Parser, Tree, Node
from pyoxigraph import Store

BUILD_LIB = 'build/langs.so'

Language.build_library(
    BUILD_LIB,
    [
        "tree-sitter-pddl"
    ]
)
PDDL = Language(BUILD_LIB, "pddl")

operator_translation = {
    "<": "lesser_than",
    ">": "greater_than",
    "<=": "lesser_than_or_equal",
    ">=": "lesser_than_or_equal",
    "-": "minus",
    "+": "plus",
    "*": "multiply",
    "/": "divide",
    "and": "and",
    "not": "not",
    "or": "or",
}

def walk_tree(tree: Tree, callback: Callable[[Node, int], None]):
    cursor = tree.walk()
    root = cursor.node
    depth = 0
    while True:
        callback(cursor.node, depth)
        if not cursor.goto_first_child():
            if cursor.goto_next_sibling():
                continue
            if not cursor.goto_parent():
                break
            else:
                if cursor.node == root:
                    break
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

if __name__ == "__main__":
    pddl_parser = Parser()
    pddl_parser.set_language(PDDL)
    with open("testdomain.pddl") as file:
        test = file.read()
    tree = pddl_parser.parse(bytes(test, 'utf-8'))
    walk_tree(tree, tree_print)


