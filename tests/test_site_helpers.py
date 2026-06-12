"""Load the site generator script as a module (scripts/ is not a package)."""

import importlib.util
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parent.parent / "scripts" / "build_site_catalogue.py"


def load_built_site(out_dir: Path, count: int) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("build_site_catalogue", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result: dict[str, Any] = module.build_site(out_dir, count=count)
    return result
