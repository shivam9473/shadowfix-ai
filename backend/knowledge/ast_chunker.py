"""AST chunking. Tree-sitter is used when its grammars import; otherwise a regex split."""

from __future__ import annotations

import re

from schemas import CodeChunk

_PY_DEF = re.compile(r"^(class |def |async def )", re.MULTILINE)
_JS_DEF = re.compile(r"^(export\s+)?(async\s+)?(function |class |const \w+ = )", re.MULTILINE)


def chunk_source(path: str, source: str) -> list[CodeChunk]:
    language = _language(path)
    if not source.strip():
        return []
    tree_chunks = _tree_sitter_chunks(path, source, language)
    if tree_chunks:
        return tree_chunks
    return _regex_chunks(path, source, language)


def _language(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith((".js", ".jsx")):
        return "javascript"
    if path.endswith((".yml", ".yaml")):
        return "yaml"
    return "text"


def _tree_sitter_chunks(path: str, source: str, language: str) -> list[CodeChunk]:
    if language not in {"python", "javascript"}:
        return []
    try:
        from tree_sitter import Language, Parser
        if language == "python":
            import tree_sitter_python as grammar
        else:
            import tree_sitter_javascript as grammar
    except Exception:
        return []

    parser = Parser(Language(grammar.language()))
    tree = parser.parse(source.encode())
    wanted = {"function_definition", "class_definition", "method_definition"}
    if language == "javascript":
        wanted = {"function_declaration", "class_declaration", "method_definition", "lexical_declaration"}
    chunks: list[CodeChunk] = []
    for node in _walk(tree.root_node):
        if node.type not in wanted:
            continue
        text = source.encode()[node.start_byte : node.end_byte].decode(errors="replace")
        symbol = _symbol_from_node(node, source.encode()) or node.type
        chunks.append(
            CodeChunk(
                path=path,
                symbol=symbol,
                language=language,
                text=f"file: {path}\nsymbol: {symbol}\n{text}",
                parser="tree-sitter",
                start_line=node.start_point[0] + 1,
            )
        )
    return chunks


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _symbol_from_node(node, source: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return source[name.start_byte : name.end_byte].decode(errors="replace")
    return ""


def _regex_chunks(path: str, source: str, language: str) -> list[CodeChunk]:
    pattern = _PY_DEF if language == "python" else _JS_DEF if language == "javascript" else None
    if pattern is None or not pattern.search(source):
        return [
            CodeChunk(
                path=path,
                symbol=path.rsplit("/", 1)[-1],
                language=language,
                text=f"file: {path}\n{source}",
                parser="regex",
                start_line=1,
            )
        ]

    matches = list(pattern.finditer(source))
    chunks: list[CodeChunk] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.start() : end].strip()
        first = body.splitlines()[0]
        symbol = first.split("(")[0].split(":")[0].split()[-1]
        line = source[: match.start()].count("\n") + 1
        chunks.append(
            CodeChunk(
                path=path,
                symbol=symbol,
                language=language,
                text=f"file: {path}\nsymbol: {symbol}\n{body}",
                parser="regex",
                start_line=line,
            )
        )
    return chunks
