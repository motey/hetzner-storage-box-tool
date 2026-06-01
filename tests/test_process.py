from __future__ import annotations

import pytest

from hsbt.process import run_command, open_process


class TestRunCommand:
    def test_success_echo(self):
        result = run_command("echo hello")
        assert result.return_code == 0
        assert "hello" in result.stdout

    def test_failure_raises_by_default(self):
        with pytest.raises(ChildProcessError):
            run_command("exit 1")

    def test_failure_no_raise(self):
        result = run_command("exit 1", raise_error=False)
        assert result.return_code == 1
        assert result.error_for_raise is not None

    def test_stdout_multiline_captured(self):
        result = run_command("printf 'line1\\nline2\\n'")
        assert "line1" in result.stdout
        assert "line2" in result.stdout

    def test_extra_env_injected(self):
        result = run_command("echo $HSBT_TEST_VAR", extra_envs={"HSBT_TEST_VAR": "injected"})
        assert "injected" in result.stdout

    def test_command_stored_on_result(self):
        result = run_command("echo ok")
        assert result.command is not None
        assert len(result.command) > 0

    def test_stderr_captured(self):
        result = run_command("echo oops >&2; exit 1", raise_error=False)
        assert result.return_code == 1

    def test_error_for_raise_is_none_on_success(self):
        result = run_command("true")
        assert result.error_for_raise is None

    def test_error_for_raise_contains_code(self):
        result = run_command("exit 42", raise_error=False)
        assert "42" in str(result.error_for_raise)


class TestOpenProcess:
    def test_yields_at_least_once(self):
        outputs = list(open_process("echo done"))
        assert len(outputs) >= 1

    def test_final_yield_has_return_code(self):
        outputs = list(open_process("echo done"))
        assert outputs[-1].return_code == 0

    def test_failure_final_yield_nonzero(self):
        outputs = list(open_process("exit 2", raise_error=False))
        assert outputs[-1].return_code == 2

    def test_failure_raises_by_default(self):
        with pytest.raises(ChildProcessError):
            list(open_process("exit 1"))

    def test_stdout_lines_accumulated(self):
        outputs = list(open_process("printf 'a\\nb\\nc\\n'"))
        all_lines = outputs[-1].stdout_lines
        assert any("a" in line for line in all_lines)
