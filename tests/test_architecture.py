"""架构边界守卫：防止反向依赖和业务层被基础设施污染。"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _imported_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _assert_forbidden_imports(directory: str, forbidden: set[str]) -> None:
    files = list((ROOT / directory).rglob("*.py"))
    assert files, f"{directory} 目录不能为空"
    offenders: list[str] = []
    for path in files:
        roots = _imported_roots(path)
        bad = sorted(roots & forbidden)
        if bad:
            offenders.append(f"{path.relative_to(ROOT)}: {', '.join(bad)}")
    assert not offenders, f"{directory} 出现非法依赖:\n" + "\n".join(offenders)


def test_shared_has_no_infrastructure_or_framework_dependencies() -> None:
    _assert_forbidden_imports(
        "app/shared",
        {"fastapi", "sqlalchemy", "redis", "pymilvus", "openai"},
    )


def test_domain_does_not_depend_on_api_or_infrastructure() -> None:
    _assert_forbidden_imports(
        "app/domain",
        {"app.api", "app.infrastructure"},
    )


def test_core_does_not_depend_on_api_layer() -> None:
    _assert_forbidden_imports(
        "app/core",
        {"app.api"},
    )


def test_shared_only_contains_python_modules_and_readme() -> None:
    files = [
        path
        for path in (ROOT / "app/shared").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    unexpected = [
        path.relative_to(ROOT).as_posix()
        for path in files
        if not (path.name == "README.md" or path.suffix == ".py")
    ]
    assert unexpected == []
