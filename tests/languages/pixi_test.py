from __future__ import annotations

import os
from unittest import mock

import pytest

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.languages import pixi
from pre_commit.util import cmd_output
from testing.language_helpers import run_language

ACTUAL_GET_DEFAULT_VERSION = pixi.get_default_version.__wrapped__


@pytest.fixture
def exe_exists_mck():
    with mock.patch.object(lang_base, 'exe_exists') as mck:
        yield mck


def test_pixi_default_version_system_available(exe_exists_mck):
    exe_exists_mck.return_value = True
    assert ACTUAL_GET_DEFAULT_VERSION() == 'system'


def test_pixi_default_version_system_not_available(exe_exists_mck):
    exe_exists_mck.return_value = False
    assert ACTUAL_GET_DEFAULT_VERSION() == C.DEFAULT


@pytest.mark.parametrize(
    'platform,installer', [('linux', 'install.sh'), ('win32', 'install.ps1')],
)
def test_pixi_install_platform(
    tmp_path, platform, installer,
):
    version = 'v0.39.0'

    def cmd_mck(cmd, *args):
        assert len(args) == 0
        assert os.path.basename(cmd) == installer
        assert os.getenv('PIXI_HOME') == str(tmp_path)
        assert os.getenv('PIXI_VERSION') == version
        assert os.getenv('PIXI_NO_PATH_UPDATE') == '1'

    with mock.patch.object(pixi, 'cmd_output_b') as mck:
        mck.side_effect = cmd_mck
        pixi._install_pixi(str(tmp_path), version=version, platform=platform)


@pytest.mark.parametrize(
    'version,stdout_exp',
    [
        ('v0.37.0', 'pixi 0.37.0'),
        ('v0.38.0', 'pixi 0.38.0'),
        (C.DEFAULT, None),
    ],
)
def test_pixi_install_version(tmp_path, version, stdout_exp):
    pixi._install_pixi(str(tmp_path), version=pixi._pixi_version(version))

    # Test the correct version of pixi gets installed
    with envcontext(pixi.get_env_patch(str(tmp_path), version)):
        ret, stdout, stderr = cmd_output('pixi', '--version')

    assert ret == 0
    assert stderr == ''
    if stdout_exp is not None:
        assert stdout.strip() == stdout_exp


PY_CMD_VERSION = (
    'python -c "import sys; print(f\\"{sys.version_info.major}'
    '.{sys.version_info.minor}.{sys.version_info.micro}\\")"'
)


@pytest.mark.parametrize('py_version', ['3.8.5', '3.12.4'])
def test_pixi_run_with_config(tmp_path, py_version):
    tmp_path.joinpath('pixi.toml').write_text(
        '[project]\n'
        'channels = ["conda-forge"]\n'
        'platforms = ["win-64", "linux-64", "osx-64"]\n'
        'name = "hello_world"\n'
        'version = "0.1.0"\n'
        '\n'
        '[dependencies]\n'
        'python = "==' + py_version + '"\n',
    )

    ret, out = run_language(
        tmp_path,
        pixi,
        PY_CMD_VERSION,
        version='v0.38.0',
    )

    assert out.decode().strip() == py_version
    assert ret == 0


@pytest.mark.parametrize('py_version', ['3.8.5', '3.12.4'])
def test_pixi_run_additional_deps(tmp_path, py_version):
    ret, out = run_language(
        tmp_path,
        pixi,
        PY_CMD_VERSION,
        version='v0.38.0',
        deps=['python ==' + py_version],
    )

    assert out.decode().strip() == py_version
    assert ret == 0
