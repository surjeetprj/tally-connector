"""Enforce boundaries as implementation appears, without importing adapters."""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "src/innoforia_tally_connector"


def test_layer_imports():
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        layer = relative.parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [n.name for n in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for module in modules:
                short = module.removeprefix("innoforia_tally_connector.")
                forbidden = ("PySide6", "httpx", "sqlalchemy", "huey", "integrations", "persistence", "ui", "execution")
                if layer in ("domain", "application"):
                    assert not short.startswith(forbidden), (relative, module)
                if layer == "domain":
                    assert not short.startswith("application"), (relative, module)
                if layer == "ui":
                    assert not short.startswith(("httpx", "sqlalchemy", "huey", "persistence", "integrations", "execution")), (relative, module)
                if relative.parts[:2] == ("integrations", "bahi"):
                    assert not short.startswith("integrations.tally"), (relative, module)
                if relative.parts[:2] == ("integrations", "tally"):
                    assert not short.startswith("integrations.bahi"), (relative, module)
                if relative.parts[:2] == ("application", "masters"):
                    assert not short.startswith(("application.purchases", "application.sales")), (relative, module)
                if "_transport" in short:
                    assert relative.as_posix() == "integrations/tally/gateway.py", (relative, module)
