use tree_sitter::{
    Language,
    Parser,
    TreeCursor,
};
use oxigraph::{
    store::Store,
    model::{Quad, NamedNode, BlankNode, Literal, Term, Subject}
};
use std::{env, fs, os::unix::io, collections::HashMap, vec::IntoIter, any::Any, ops::Deref};
extern "C" { fn tree_sitter_pddl() -> Language; }

fn walk_treecursor(mut cursor: TreeCursor, callback: fn(tree_sitter::Node, i32)) {
    let root = cursor.node();
    let mut depth = 0;
    loop {
        callback(cursor.node(), depth);
        if !cursor.goto_first_child() {
            if cursor.goto_next_sibling() { continue; }
            if !cursor.goto_next_sibling() {
                break;
            } else {
                if !cursor.goto_next_sibling() { break; }
                depth -= 1;
            }
        } else {
            depth += 1;
        }
    }
}

struct TreeCursorWalker<'a> {
    depth: i32,
    cursor: TreeCursor<'a>,
    first: bool
}

impl<'a> TreeCursorWalker<'a> {
    fn new(cursor: TreeCursor<'a>) -> Self {
        TreeCursorWalker {
            depth: 0,
            cursor,
            first: true
        }
    }
}

impl<'a> Iterator for TreeCursorWalker<'a> {
    type Item = (tree_sitter::Node<'a>, i32);
    fn next(&mut self) -> Option<Self::Item> {
        if !self.first {
            self.first = false;
            return Some((self.cursor.node(), self.depth));
        }
        loop {
            if !self.cursor.goto_first_child() {
                if self.cursor.goto_next_sibling() { continue; }
                if !self.cursor.goto_parent() {
                    return None
                } else {
                    if !self.cursor.goto_next_sibling() { return None; }
                    self.depth -= 1;
                }
            } else {
                self.depth += 1;
            }
            return Some((self.cursor.node(), self.depth));
        }
    }
}

fn print_node(node: tree_sitter::Node, depth: i32) {
    let print: String = (0..depth).map(|_| "  ").collect();
    println!("{}{:?}", print, node);
}

#[derive(Clone)]
enum Identifier {
    NamedNode(NamedNode),
    BlankNode(BlankNode),
}

impl From<NamedNode> for Identifier {
    fn from(value: NamedNode) -> Self {
        Self::NamedNode(value)
    }
}

impl From<BlankNode> for Identifier {
    fn from(value: BlankNode) -> Self {
        Self::BlankNode(value)
    }
}

impl From<Identifier> for Term {
    fn from(value: Identifier) -> Self {
        match value {
            Identifier::NamedNode(node) => Self::NamedNode(node),
            Identifier::BlankNode(node) => Self::BlankNode(node),
        }
    }
}

enum PddlState {
    Default,
}

struct PddlStateWalker {
    current: Identifier,
    current_stack: Vec<Option<Identifier>>,
    depth: i32,
    state: PddlState,
    state_stack: Vec<Option<PddlState>>,
}

impl<'a> PddlStateWalker {
    fn new(current: Identifier) -> Self {
        PddlStateWalker {
            current,
            current_stack: Vec::new(),
            depth: 0,
            state: PddlState::Default,
            state_stack: Vec::new()
        }
    }

    fn new_depth(&mut self, depth: i32) {
        if self.depth == depth { return; }
        if self.depth < depth {
            let mut new_current = None;
            let mut new_state = None;
            for _ in depth..self.depth {
                if let Some(cur) = self.current_stack.pop() {
                    new_current = cur;
                }
                if let Some(state) = self.state_stack.pop() {
                    new_state = state;
                }
            }
            if let Some(new) = new_current {
                self.current = new;
            }
            if let Some(new) = new_state {
                self.state = new;
            }
        } else {
            for _ in self.depth..depth {
                self.current_stack.push(None);
                self.state_stack.push(None);
            }
        }
    }

    fn get_triple_from_node(&self,
                            node: tree_sitter::Node,
                            key_word_map: &HashMap<&str, &str>,
                            ont_namespace: &str,
                            file_namespace: &str,
                            source: &'a [u8]) -> (Term, Term, Term) {
        let text = node.utf8_text(source).unwrap();
        match self.state {
            PddlState::Default => {
                let ont_term: bool;
                let name = 
                    if let Some(val) = key_word_map.get(&text) {
                        ont_term = true;
                        String::from(*val)
                    } else {
                        if Some(':') == text.chars().next() {
                            let mut it_text = text.chars();
                            _ = it_text.next();
                            ont_term = true;
                            it_text.collect()
                        } else {
                            ont_term = false;
                            String::from(text)
                        }
                    };
                if ont_term {
                    let subj: Term = self.current.clone().into();
                    let pred = Term::NamedNode(
                        NamedNode::new(format!("{}{}", ont_namespace, name)).unwrap()
                        );
                    let obj = Term::BlankNode(BlankNode::default());
                    return (subj, pred, obj);
                } else {
                    let subj: Term = self.current.clone().into();
                    let pred = Term::NamedNode(
                        NamedNode::new(format!("{}{}", file_namespace, name)).unwrap()
                        );
                    let obj = Term::BlankNode(BlankNode::default());
                    return (subj, pred, obj);
                }
            },
        };
    }
}

fn main() -> Result<(), std::io::Error>{
    let key_word_map = HashMap::<_, _>::from_iter(
        [
        ("<", "less_than"), 
        (">", "greater_than"), 
        ("<=", "less_than_or_equal"), 
        (">=", "less_than_or_equal"), 
        ("=", "equals"), 
        ("-", "minus"), 
        ("+", "plus"), 
        ("*", "multiply"), 
        ("/", "divide"), 
        // ("and", "and"), 
        // ("not", "not"), 
        // ("or", "or"), 
        // ("increase", "increase"), 
        // ("decrease", "decrease"), 
        // ("assign", "assign"), 
        // ("scale-up", "scale-up"),
        // ("scale-down", "scale-down,"),
        (":parameters", "parameters"), 
        (":precondition", "precondition"), 
        (":effect", "effect"), 
        (":init", "init"), 
        ]
        );
    let language = unsafe { tree_sitter_pddl() };
    let ont_ns = "http://example.com/pddl_ont/";
    let file_ns = "http://example.com/test/";
    let mut parser = Parser::new();
    if let Err(e) = parser.set_language(language) {
        print!("{}", e);
        return Ok(());
    }
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        print!("Expected 2 arguments");
        return Ok(());
    }
    let input_f = &args[1];
    let output_f = &args[2];
    println!("{} {} test", input_f, output_f);
    let input_pddl;
    match fs::read(input_f) {
        Ok(out) => input_pddl = out,
        Err(er) => return Err(er)
    }
    let tree = parser.parse(&input_pddl, None).unwrap();
    let iter_cursor = TreeCursorWalker::new(tree.walk());
    let mut graph = Store::new();
    let mut state = PddlStateWalker::new(
        NamedNode::new("http://example.org/begin/").unwrap().into());
    for (node, depth) in iter_cursor {
        if node.parent() == None || !node.is_named() || node.kind() == "comment" {
            continue;
        }
        state.get_triple_from_node(node, &key_word_map, ont_ns, file_ns, &input_pddl as &[u8]);
        // let print: String = (0..depth).map(|_| "  ").collect();
        // println!("{}{:?}", print, node);
    }
    return Ok(());
}
