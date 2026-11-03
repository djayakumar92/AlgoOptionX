"""The separate demo runtime cannot reach broker/research/harness/network code."""
import ast
from pathlib import Path
from algooptionx.paths import PROJECT_ROOT


def test_demo_has_no_network_research_or_execution_adapter():
    forbidden=('algooptionx.research','algooptionx_harness','requests','httpx','urllib','socket','dhanhq','subprocess')
    for path in (PROJECT_ROOT/'src/algooptionx/demo').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            modules=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            assert not any(module.startswith(forbidden) for module in modules),path


def test_demo_frontend_has_only_its_same_origin_api():
    source=(PROJECT_ROOT/'apps/web/src/features/demo/api.ts').read_text()
    assert 'fetch(`/api/demo/${path}`' in source
    assert 'https://' not in source and '/api/commands' not in source
