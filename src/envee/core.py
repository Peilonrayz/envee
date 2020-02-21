from __future__ import annotations

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
import typing
from typing import Dict, List, Optional

import teetime

if typing.TYPE_CHECKING:
    from . import virtual_environments
    from . import package_managers

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CommandException(Exception):
    __slots__ = ("ret",)

    def __init__(self, ret, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.ret = ret


class PRet(collections.namedtuple("PRet", "process, return_code, out, err")):
    def _format(self, output, force):
        if force:
            output = str(output)
        else:
            output = output or ""
        output = output.rstrip()
        if "\n" in output:
            output = "\n" + textwrap.indent(output, "    ")
        return output

    def log_out(self, level=logging.INFO, force=False):
        output = self._format(self.out, force)
        if output:
            logger.log(level, output)

    def log_err(self, level=logging.ERROR, force=False):
        output = self._format(self.err, force)
        if output:
            logger.log(level, output)

    def log_return_code(self, level=logging.DEBUG):
        if self.return_code is not None:
            logger.log(level, f"Return Code: {self.return_code}")

    def log(self, out=logging.INFO, err=logging.ERROR, ret=logging.DEBUG):
        self.log_out(out)
        self.log_err(err)
        self.log_return_code(ret)

    def display(self, err=logging.ERROR, ret=logging.DEBUG):
        if self.out is not None:
            print(self.out.rstrip())
        self.log_err(err)
        self.log_return_code(ret)


def _matching_programs(command: str, path: Optional[str]):
    if path is None:
        return
    for location in path.split(";"):
        new_command = os.path.join(location, command)
        directory, file_name = os.path.split(new_command)
        if os.path.exists(directory) and os.path.isdir(directory):
            for (_, _, files) in os.walk(directory):
                for file in files:
                    if file.startswith(file_name):
                        yield os.path.join(directory, file)
                break


@functools.lru_cache(8)
def _expand_program(command: str, path: Optional[str]) -> None:
    if os.path.isabs(command):
        logger.debug(f"Command is absolute. {command}")
        return command
    new_commands = _matching_programs(command, path)
    sentinel = object()
    new_command = next(new_commands, sentinel)
    if new_command is sentinel:
        logger.debug(f"No expansion for program {command} in\npath: {path}")
        return command
    return new_command


def _determine_output(echo=False, stdout=None, stderr=None):
    stdout = (stdout, sys.stdout.buffer)
    stderr = (stderr, sys.stderr.buffer)
    if not echo:
        stdout = stdout[:1]
        stderr = stderr[:1]
    if stdout[0] is None:
        stdout = stdout[1:]
    if stderr[0] is None:
        stderr = stderr[1:]
    return stdout, stderr


def popen(
    commands,
    *args,
    env=None,
    expand_program=_expand_program,
    pipe=True,
    echo=False,
    stdout=None,
    stderr=None,
    **kwargs,
) -> PRet:
    logger.info("> " + " ".join(commands))
    if expand_program:
        commands[0] = expand_program(commands[0], (env or {}).get("PATH"))

    if pipe:
        if stdout is None:
            stdout = tempfile.TemporaryFile()
        if stderr is None:
            stderr = tempfile.TemporaryFile()

    logger.debug("> " + " ".join(commands))
    # logger.debug(commands)
    _stdout, _stderr = _determine_output(echo, stdout, stderr)
    popen = teetime.popen_call(
        commands, *args, stdout=_stdout, stderr=_stderr, **kwargs
    )
    try:
        popen.communicate()
    except KeyboardInterrupt:
        popen.terminate()
        popen.wait()
        raise

    return PRet(
        popen,
        popen.wait(),
        stdout.read().decode("utf-8") if stdout is not None else None,
        stderr.read().decode("utf-8") if stderr is not None else None,
    )


class Flags:
    def __init__(self, *args):
        self._commands = []
        self(*args)

    def __call__(self, *args):
        for arg in args:
            self.append(arg)

    def __len__(self):
        return len(self._commands)

    def append(self, command):
        self._commands.append(command)

    def __add__(self, other):
        if not isinstance(other, (list, Flags)):
            raise TypeError(f"Invalid addition type {type(other)}")
        return self._commands + other

    def __radd__(self, other):
        if not isinstance(other, (list, Flags)):
            raise TypeError(f"Invalid addition type {type(other)}")
        return other + self._commands


class Environment:
    __slots__ = ("_env", "_package_manager", "_expand_program")

    def __init__(
        self,
        env: Dict[str, str],
        package_manager: package_managers.PackageManager,
        expand_program,
    ) -> None:
        self._env = env
        self._package_manager = package_manager
        self._expand_program = expand_program

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if type is CommandException:
            logger.error("Command Exception: " + str(value))
            return True
        return None

    def run(self, *args, env=None, expand_program=True, **kwargs,) -> PRet:
        _expand_program = self._expand_program if expand_program else None
        return popen(*args, env=self._env, expand_program=_expand_program, **kwargs,)

    def install(self, *packages, force=False, cmd=None, **kwargs) -> PRet:
        return self._package_manager.install(
            *packages, force=force, cmd=self.run, **kwargs,
        )

    def list(self, *args, cmd=None, **kwargs) -> List[str]:
        return self._package_manager.list(*args, cmd=self.run, **kwargs)
