"""
Every module under ``src/`` is reachable from a command or a migration.

This is what keeps the 2026-09-22 sweep (backlog task 027) from recurring: a
module nothing imports fails the suite at the pull request, not a month
later. The walk is static -- ``ast`` over every file, absolute ``src.x.y``
and relative imports resolved against the importing package -- so nothing is
executed and no allowlist exists. When the sweep first built this test it
found fourteen modules unreachable, the whole source, routing and model
stack, because no command wired them in; task 029 wired the last of them.

If a module is legitimately unreachable, the fix is to give it a caller or
delete it, not to exempt it here.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
ROOTS = ("src.cli.app",)


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _all_modules() -> dict[str, Path]:
    return {_module_name(p): p for p in SRC.rglob("*.py")}


def _resolve_relative(importer: str, is_package: bool, level: int, module: str | None) -> str:
    base = importer.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + ([module] if module else []))


def _imports(name: str, path: Path, known: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    is_package = path.name == "__init__.py"
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                target = _resolve_relative(name, is_package, node.level, node.module)
            else:
                target = node.module or ""
            if not target.startswith("src"):
                continue
            found.add(target)
            # `from pkg import name` may name a submodule rather than an attribute.
            for alias in node.names:
                candidate = f"{target}.{alias.name}"
                if candidate in known:
                    found.add(candidate)
    return {m for m in found if m in known}


def _reachable(modules: dict[str, Path], roots: tuple[str, ...]) -> set[str]:
    seen: set[str] = set()
    frontier = list(roots)
    while frontier:
        name = frontier.pop()
        if name in seen or name not in modules:
            continue
        seen.add(name)
        # Importing a submodule imports every package above it.
        parts = name.split(".")
        for i in range(1, len(parts)):
            frontier.append(".".join(parts[:i]))
        frontier.extend(_imports(name, modules[name], set(modules)))
    return seen


def test_every_module_under_src_is_reachable_from_a_command_or_a_migration():
    modules = _all_modules()
    migrations = tuple(m for m in modules if m.startswith("src.database.migrations."))
    reachable = _reachable(modules, ROOTS + migrations)

    unreachable = sorted(m for m in modules if m not in reachable and not m.endswith("__init__"))
    unreachable = [m for m in unreachable if modules[m].name != "__init__.py"]
    assert unreachable == [], (
        "these modules are reachable from no command and no migration; give each a caller "
        f"or delete it: {unreachable}"
    )
