"""Coding rules of README §7.5 that no linter in our toolchain checks."""

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCES = ("src", "cadder/src", "cadder/freecad-addon", "tests", "cadder/tests", "firmware")
SCOPES = (ast.FunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _module_names(tree: ast.Module) -> set[str]:
    """Imports, functions, classes and variables bound at module level (also under an ``if``)."""
    names: set[str] = set()
    statements = list(tree.body)
    for statement in statements:  # grows while walking into conditional blocks
        match statement:
            case ast.If(body=body, orelse=orelse):
                statements += [*body, *orelse]
            case ast.Import(names=aliases) | ast.ImportFrom(names=aliases):
                names |= {(alias.asname or alias.name).split(".")[0] for alias in aliases}
            case ast.FunctionDef(name=name) | ast.ClassDef(name=name):
                names.add(name)
            case ast.Assign(targets=targets):
                names |= {target.id for target in targets if isinstance(target, ast.Name)}
            case ast.AnnAssign(target=ast.Name(id=name)):
                names.add(name)
    return names


def _fixtures(tree: ast.Module) -> set[str]:
    """Pytest fixtures of the module: a test requests one by naming a parameter after it."""
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and any("fixture" in ast.unparse(d) for d in node.decorator_list)
    }


def _shadowing(source: str) -> Iterator[tuple[int, str]]:
    """Line and name of each local or parameter that hides a module-level name."""
    tree = ast.parse(source)
    module_names, fixtures = _module_names(tree), _fixtures(tree)
    for scope in ast.walk(tree):
        if not isinstance(scope, SCOPES):
            continue
        declared_global = {name for node in ast.walk(scope) if isinstance(node, ast.Global) for name in node.names}
        for node in ast.walk(scope):
            match node:
                case ast.Name(id=name, ctx=ast.Store()) if name not in declared_global:
                    pass
                case ast.arg(arg=name) if name not in fixtures:
                    pass
                case _:
                    continue
            if name in module_names:
                yield node.lineno, name


def test_the_shadowing_scan_finds_a_hidden_name() -> None:
    source = "from os import path\n\ndef f():\n    path = 1\n    return path\n"
    assert list(_shadowing(source)) == [(4, "path")]


def test_no_local_name_shadows_a_module_level_name() -> None:
    offenders = {
        f"{file.relative_to(ROOT)}:{line} {name}"
        for folder in SOURCES
        for file in (ROOT / folder).rglob("*.py")
        for line, name in _shadowing(file.read_text())
    }
    assert sorted(offenders) == []
