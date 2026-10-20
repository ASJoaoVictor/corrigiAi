import os
from pathlib import Path
from dataclasses import dataclass
from app.runtime import resource_path


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def config(self): return self.root / 'config' / 'settings.dpapi'
    @property
    def logs(self): return self.root / 'logs'
    @property
    def work(self): return self.root / 'temp'
    @property
    def models(self): return resource_path('ocr-models')

    def prepare(self):
        for directory in (self.root, self.config.parent, self.logs, self.work):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)


def application_paths(environ=None):
    environ = os.environ if environ is None else environ
    base = environ.get('LOCALAPPDATA')
    if not base:
        raise ValueError('O diretório de dados do usuário Windows não está disponível.')
    return AppPaths(Path(base) / 'corrigiAi')
