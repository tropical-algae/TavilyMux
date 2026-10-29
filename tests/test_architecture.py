import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "tavily_mux"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_services_do_not_depend_on_http_layer() -> None:
    violations: list[str] = []
    for path in (PACKAGE_ROOT / "services").rglob("*.py"):
        forbidden = {
            module
            for module in _imports(path)
            if module == "fastapi" or module.startswith("tavily_mux.api")
        }
        if forbidden:
            violations.append(f"{path.relative_to(PACKAGE_ROOT)}: {sorted(forbidden)}")

    assert not violations, "service-to-API dependencies found:\n" + "\n".join(violations)


def test_domain_does_not_depend_on_adapters() -> None:
    violations: list[str] = []
    for path in (PACKAGE_ROOT / "domain").rglob("*.py"):
        forbidden = {
            module
            for module in _imports(path)
            if module.startswith(("tavily_mux.api", "tavily_mux.persistence"))
        }
        if forbidden:
            violations.append(f"{path.relative_to(PACKAGE_ROOT)}: {sorted(forbidden)}")

    assert not violations, "domain-to-adapter dependencies found:\n" + "\n".join(violations)


def test_app_factory_contains_no_route_implementation() -> None:
    source = (PACKAGE_ROOT / "app.py").read_text(encoding="utf-8")

    assert "@app." not in source
    assert ".add_api_route(" not in source
    assert "app.include_router(create_router(settings))" in source
