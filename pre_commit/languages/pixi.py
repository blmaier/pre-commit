from __future__ import annotations

import contextlib
import functools
import os
import shutil
import sys
import tempfile
import urllib.request
from collections.abc import Generator
from collections.abc import Sequence

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.envcontext import PatchesT
from pre_commit.envcontext import Var
from pre_commit.prefix import Prefix
from pre_commit.util import cmd_output_b
from pre_commit.util import make_executable
from pre_commit.util import win_exe

ENVIRONMENT_DIR = 'pixi_env'
health_check = lang_base.basic_health_check


@functools.lru_cache(maxsize=1)
def get_default_version() -> str:
    # Use the system installed pixi if found
    if lang_base.exe_exists('pixi'):
        return 'system'
    else:
        return C.DEFAULT


def get_env_patch(envdir: str, version: str) -> PatchesT:
    if version == 'system':
        return ()

    return (
        ('PATH', (os.path.join(envdir, 'bin'), os.pathsep, Var('PATH'))),
        ('PIXI_HOME', envdir),
    )


@contextlib.contextmanager
def in_env(prefix: Prefix, version: str) -> Generator[None]:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    with envcontext(get_env_patch(envdir, version)):
        yield


def _pixi_version(language_version: str) -> str:
    """Transform the language version into a pixi version."""
    if language_version == C.DEFAULT:
        return 'latest'
    else:
        return language_version


def _install_pixi(
    envdir: str, version: str, platform: str | None = None,
) -> None:
    if platform is None:
        platform = sys.platform

    # Download pixi installer
    if platform == 'win32':
        installer_name = 'install.ps1'
    else:
        installer_name = 'install.sh'
    resp = urllib.request.urlopen('https://pixi.sh/' + installer_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        exe = os.path.join(tmpdir, win_exe(installer_name))
        with open(exe, 'wb') as f:
            shutil.copyfileobj(resp, f)
        make_executable(exe)

        # install pixi into `$PIXI_HOME/bin`
        with envcontext(
            (
                ('PIXI_HOME', envdir),
                ('PIXI_VERSION', version),
                ('PIXI_NO_PATH_UPDATE', '1'),
            ),
        ):
            cmd_output_b(exe)


def install_environment(
    prefix: Prefix,
    version: str,
    additional_dependencies: Sequence[str],
) -> None:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    os.makedirs(envdir, exist_ok=True)

    with envcontext(get_env_patch(envdir, version)):
        if version != 'system':
            _install_pixi(envdir, _pixi_version(version))

        if not os.path.isfile(prefix.path('pixi.toml')):
            lang_base.setup_cmd(prefix, ('pixi', 'init', '--format', 'pixi'))

        if additional_dependencies:
            lang_base.setup_cmd(
                prefix, ('pixi', 'add', '--', *additional_dependencies),
            )

        # We can't rely on pixi-run to install the environment, as the run_hook
        # runs concurrently and breaks installation. Install everything here so
        # it is done in serial.
        # See https://github.com/prefix-dev/pixi/issues/1482
        lang_base.setup_cmd(prefix, ('pixi', 'install', '--all'))


def run_hook(
    prefix: Prefix,
    entry: str,
    args: Sequence[str],
    file_args: Sequence[str],
    *,
    is_local: bool,
    require_serial: bool,
    color: bool,
) -> tuple[int, bytes]:
    cmd = (
        'pixi',
        'run',
        '--manifest-path',
        prefix.path('pixi.toml'),
        '--no-lockfile-update',
        '--',
        *lang_base.hook_cmd(entry, args),
    )

    return lang_base.run_xargs(
        cmd,
        file_args,
        require_serial=require_serial,
        color=color,
    )
