"""Record the exact shipped sources and dependency versions without executing them."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess

root = Path(os.environ['ASTROSTACK_PAYLOAD'])
packages = sorted(
    [{'name': d.metadata['Name'], 'version': d.version}
     for d in importlib.metadata.distributions(path=[str(root / 'runtime/Lib/site-packages')])],
    key=lambda d: d['name'].lower())
files = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file()}
manifest = {
    'version': '1.4.0-preview',
    'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'python': '3.12.10', 'architecture': 'win_amd64', 'packages': packages, 'sha256': files,
}
(root / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('ASTROSTACK_MANIFEST_OK', len(files), 'files')
