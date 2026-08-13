import hashlib
import re as _re
from pathlib import Path

from tree_sitter import Language

from app.services.ingest.models import CodeAnalysis, CodeArtifact
from app.services.ingest.requirements_extractor import find_req_ids

_LANG_EXT = {
    ".py": ("python", lambda: Language(__import__("tree_sitter_python").language())),
    ".ts": ("typescript", lambda: Language(__import__("tree_sitter_typescript").language_typescript())),
    ".tsx": ("typescript", lambda: Language(__import__("tree_sitter_typescript").language_tsx())),
    ".js": ("javascript", lambda: Language(__import__("tree_sitter_javascript").language())),
    ".java": ("java", lambda: Language(__import__("tree_sitter_java").language())),
}

_PY_DOCSTRING = {"function_definition", "class_definition", "decorated_definition"}


def analyze_code(repo_path: str) -> list[CodeAnalysis]:
    root = Path(repo_path)
    analyses: list[CodeAnalysis] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".proto":
            analyses.append(_analyze_proto(path))
            continue
        lang = _LANG_EXT.get(suffix)
        if lang is None:
            continue
        name, loader = lang
        try:
            language = loader()
        except Exception:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        analysis = _analyze_text(name, language, text, path)
        if analysis:
            analyses.append(analysis)
    return analyses


def _analyze_text(language: str, language_obj, text: str, path: Path) -> CodeAnalysis:
    from tree_sitter import Parser

    parser = Parser(language_obj)
    tree = parser.parse(text.encode("utf-8"))

    analysis = CodeAnalysis(language=language)
    root_node = tree.root_node

    def node_text(node) -> str:
        return text[node.start_byte : node.end_byte]

    def docstring(node) -> str:
        text_bytes = text.encode("utf-8")
        child = node.child_by_field_name("body")
        if child and child.type in _PY_DOCSTRING:
            stmts = [c for c in child.named_children if c.type == "expression_statement"]
            for stmt in stmts:
                expr = stmt.child_by_field_name("expression")
                if expr and expr.type == "string":
                    return text_bytes[expr.start_byte : expr.end_byte].decode("utf-8", "replace")[:200]
        return ""

    def walk(node, module: str):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            name = node_text(name_node) if name_node else "anonymous"
            artifact = CodeArtifact(
                artifact_id=f"C-{module}.{name}",
                name=name,
                kind="function",
                module=module,
                description=docstring(node),
                req_ids=find_req_ids(node_text(node)),
            )
            analysis.artifacts.append(artifact)
            if artifact.req_ids:
                analysis.dependencies.setdefault(module, []).extend(artifact.req_ids)
            return
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            name = node_text(name_node) if name_node else "Anonymous"
            artifact = CodeArtifact(
                artifact_id=f"C-{module}.{name}",
                name=name,
                kind="class",
                module=module,
                description=docstring(node),
                req_ids=find_req_ids(node_text(node)),
            )
            analysis.artifacts.append(artifact)
            for child in node.named_children:
                walk(child, f"{module}.{name}")
            return
        if node.type == "decorated_definition":
            decorators = [n for n in node.named_children if n.type == "decorator"]
            definition = next((n for n in node.named_children if n.type in ("function_definition", "class_definition")), None)
            if definition:
                walk(definition, module)
            route = _route_from_decorators(decorators, node_text, text)
            if route:
                endpoint = CodeArtifact(
                    artifact_id=f"C-{module}.{route[1]}",
                    name=route[1],
                    kind="endpoint",
                    module=module,
                    description=route[0],
                    req_ids=find_req_ids(node_text(node)),
                )
                analysis.endpoints.append(endpoint)
            return

    for child in root_node.named_children:
        walk(child, path.stem)

    if path.stem not in analysis.modules:
        analysis.modules.append(path.stem)
    imports = _py_imports(text)
    if imports:
        analysis.dependencies.setdefault(path.stem, []).extend(imports)
    return analysis


def _route_from_decorators(decorators, node_text, text):
    for dec in decorators:
        dec_text = node_text(dec)
        if any(route in dec_text for route in ("@app.", "@router.", "@bp.")):
            match = _re_route.search(dec_text)
            if match:
                return (f"HTTP {dec_text.split('(')[0]} -> {match.group(1)}", match.group(1))
    return None


_re_route = _re.compile(r"['\"]([^'\"]+)['\"]")

_DECORATOR_RE = _re.compile(r"@(?:\w+\.)?(?:app|router|bp)\.(?:get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]")


def _py_imports(text: str) -> list[str]:
    modules = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("import ", "from ")):
            modules.append(line.split(" ")[1].split(".")[0])
    return modules


def _analyze_proto(path: Path) -> CodeAnalysis:
    analysis = CodeAnalysis(language="protobuf")
    text = path.read_text(encoding="utf-8", errors="replace")
    analysis.modules.append(path.stem)
    for match in _re_message.finditer(text):
        name = match.group(1)
        body = text[match.start() : match.end()][:600]
        analysis.messages.append(
            CodeArtifact(
                artifact_id=f"C-{path.stem}.{name}",
                name=name,
                kind="message",
                module=path.stem,
                description=" ".join(body.split())[:200],
                req_ids=find_req_ids(body),
            )
        )
    return analysis


_re_message = _re.compile(r"\bmessage\s+(\w+)\s*\{")


def file_hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
