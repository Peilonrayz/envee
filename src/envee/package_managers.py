import collections
import functools
import io
import logging
import os.path
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Iterator, List

import teetime

from . import core

__all__ = [
    "PackageManager",
    "Pip",
]


class PackageManager:
    def install(
        self, *packages: str, cmd=core.popen, force: bool = False, **kwargs,
    ) -> core.PRet:
        if not force:
            _list = set(self.list(cmd=cmd))
            packages = [p for p in packages if p not in _list]
            if not packages:
                return core.PRet(None, None, None, None)
        return self._install(*packages, force=force, cmd=cmd, **kwargs)

    def _install(self, *package: str, cmd=core.popen, **kwargs) -> core.PRet:
        return core.PRet(None, None, None, None)

    @functools.lru_cache(1)
    def list(self, cmd=core.popen, force: bool = False, **kwargs,) -> List[str]:
        return list(self._list(cmd=cmd, **kwargs))

    def _list(self, cmd=core.popen, **kwargs) -> Iterator[str]:
        return []


class Pip(PackageManager):
    def _install(
        self, *packages: str, force=False, cmd=core.popen, **kwargs,
    ) -> core.PRet:
        command = ["pip", "install"]
        if force:
            command += ["--force-reinstall"]
        return cmd([*command, *packages], **kwargs)

    def _list(self, cmd=core.popen, pipe=None, **kwargs) -> Iterator[str]:
        ret = cmd(["pip", "list"], pipe=True, **kwargs)
        ret.log(out=logging.DEBUG)
        if ret.return_code:
            raise core.CommandException(ret, "Command failed.")
        packages = iter(ret.out.rstrip().split("\n"))
        next(packages, None)
        next(packages, None)
        for line in packages:
            package, *_ = *line.split(), ""
            yield package
