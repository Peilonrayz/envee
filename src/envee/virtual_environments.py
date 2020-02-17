from typing import Dict, Optional, Union, Type
import collections
import functools
import logging
import os.path
import pathlib
import sys
import subprocess
import shutil
import textwrap
import tempfile
import io

import teetime

from . import core
from . import package_managers

__all__ = [
    'VirtualEnvironment',
    'VirtualEnv',
]


class VirtualEnvironment:
    __slots__ = (
        '_path',
        '_program',
        '_flags',
        '_package_manager',
        '_expand_program',
    )

    def __init__(
        self,
        path: Union[str, pathlib.PurePath],
        package_manager: Type[package_managers.PackageManager],
        program: Optional[str] = None,
        flags: Optional[core.Flags] = None,
    ) -> None:
        self._path = path
        self._program = program
        self._flags = flags
        self._package_manager = package_manager
        self._expand_program = functools.lru_cache(8)(core._expand_program)

    def exists(self) -> bool:
        return self._exists()

    def make(self, force: bool = False) -> None:
        if self.exists():
            if not force:
                return
            self.remove()
        self._make()

    def load(self, force: bool = False) -> core.Environment:
        self.make(force=force)
        return core.Environment(
            self._env(),
            self._package_manager(),
            self._expand_program,
        )

    def remove(self) -> None:
        self._remove()

    def _exists(self) -> bool:
        return os.path.exists(self._path)

    def _make(self) -> None:
        if not self.exists():
            os.mkdir(self._path)

    def _env(self) -> Dict[str, str]:
        return os.environ.copy()

    def _remove(self) -> None:
        shutil.rmtree(self._path, ignore_errors=True)


class VirtualEnv(VirtualEnvironment):
    def _make(self) -> None:
        flags = self._flags or core.Flags()
        if self._program is not None:
            flags = flags(f'--python={self._program}')
        core.popen(['python', '-m', 'virtualenv', self._path] + flags).log()

    def _env(self) -> Dict[str, str]:
        env = super()._env()
        env['PATH'] = (
            os.path.abspath(os.path.join(self._path, 'Scripts'))
            + ';'
            + env['PATH']
        )
        return env
