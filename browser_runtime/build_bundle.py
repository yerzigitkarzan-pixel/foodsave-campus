"""Build the public browser backend from an explicit source-only allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROJECT = Path(__file__).resolve().parents[1]
MODULES = ('__init__.py', 'analytics.py', 'assistant.py', 'auth.py',
           'catalog.py', 'db.py', 'entry_context.py', 'main.py', 'metrics.py',
           'seed.py', 'xlsx_export.py')


def build(output: Path | None = None) -> dict:
    target = (output or PROJECT / 'browser_runtime/foodsave_backend.zip').resolve()
    sources = [(PROJECT / 'app' / name, 'app/' + name) for name in MODULES]
    sources += [(PROJECT / 'inputs/reference_cells.json', 'inputs/reference_cells.json'),
                (Path(__file__).with_name('runtime_adapter.py'), 'runtime_adapter.py')]
    for source, _ in sources:
        if not source.is_file() or not source.resolve().is_relative_to(PROJECT):
            raise ValueError(f'Bundle source is missing or outside the project: {source.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    included = []
    with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for source, name in sources:
            content = source.read_bytes()
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
            included.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest()})
    return {'archive': str(target), 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'files': included}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build the synthetic browser runtime source bundle.')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output), ensure_ascii=False, indent=2))
