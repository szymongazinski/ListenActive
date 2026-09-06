"""Collect installed distribution license notices into the release, without credentials."""
import importlib.metadata
from pathlib import Path
import shutil

target = Path('dist/ListenActive/licenses')
target.mkdir(parents=True, exist_ok=True)
for package in importlib.metadata.distributions():
    name = package.metadata['Name']
    for entry in package.files or []:
        if any(word in entry.name.lower() for word in ('license', 'copying', 'notice')):
            source = Path(package.locate_file(entry))
            if source.is_file():
                folder = target / name
                folder.mkdir(exist_ok=True)
                shutil.copy2(source, folder / entry.name)
