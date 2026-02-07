from jominipy.cst import SyntaxNode, SyntaxToken, from_green
from jominipy.parser import parse
from jominipy.syntax import JominiSyntaxKind


def _first_child_node(node: SyntaxNode, kind: JominiSyntaxKind) -> SyntaxNode | None:
    for child in node.children:
        if isinstance(child, SyntaxNode) and child.kind == kind:
            return child
    return None


def test_red_wrappers_navigation_and_siblings() -> None:
    parsed = parse("a=1\nb=2\n")
    root = from_green(parsed.root, "a=1\nb=2\n")

    source_file = _first_child_node(root, JominiSyntaxKind.SOURCE_FILE)
    assert source_file is not None
    statement_list = _first_child_node(source_file, JominiSyntaxKind.STATEMENT_LIST)
    assert statement_list is not None

    statement_nodes = statement_list.child_nodes()
    assert len(statement_nodes) == 2
    assert statement_nodes[0].kind == JominiSyntaxKind.KEY_VALUE
    assert statement_nodes[1].kind == JominiSyntaxKind.KEY_VALUE
    assert statement_nodes[0].next_sibling() is statement_nodes[1]
    assert statement_nodes[1].prev_sibling() is statement_nodes[0]


def test_red_wrappers_token_text_and_trivia_views() -> None:
    source = "a = 1 # inline\nb=2\n"
    parsed = parse(source)
    root = from_green(parsed.root, source)

    tokens = root.descendants_tokens()
    assert tokens

    reconstructed = "".join(token.text_with_trivia for token in tokens)
    assert reconstructed == source

    scalar_one: SyntaxToken | None = None
    for token in tokens:
        if token.kind == JominiSyntaxKind.INT and token.text_trimmed == "1":
            scalar_one = token
            break

    assert scalar_one is not None
    assert scalar_one.text_trimmed == "1"
    assert scalar_one.text_with_trivia.endswith("# inline")
    assert scalar_one.trailing_trivia_text == " # inline"

    b_token: SyntaxToken | None = None
    for token in tokens:
        if token.kind == JominiSyntaxKind.IDENTIFIER and token.text_trimmed == "b":
            b_token = token
            break
    assert b_token is not None
    assert b_token.leading_trivia_text == "\n"
