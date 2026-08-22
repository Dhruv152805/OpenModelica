"""
tests/test_simulation_runner.py
================================
Unit tests for :class:`app.simulation_runner.SimulationRunner`.

Run with::

    pytest tests/

These tests exercise the ``validate()`` and ``build_command()`` methods
without requiring the actual model binary to be present on the test machine.
"""

from __future__ import annotations

import pytest

from app.simulation_runner import SimulationRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dummy_path(tmp_path):
    """Return a real (empty) file path so validate() can reach the OS check."""
    exe = tmp_path / "TwoConnectedTanks"
    exe.touch()
    return str(exe)


# ---------------------------------------------------------------------------
# validate() — happy paths
# ---------------------------------------------------------------------------


class TestValidateHappyPath:
    """Valid parameter combinations that must NOT raise."""

    def test_zero_start_max_stop(self, dummy_path):
        """0, 4 is the widest valid window."""
        runner = SimulationRunner(dummy_path, 0, 4)
        runner.validate()  # must not raise

    def test_typical_range(self, dummy_path):
        """0 ≤ 0 < 3 < 5 — the example from the task spec."""
        runner = SimulationRunner(dummy_path, 0, 3)
        runner.validate()

    def test_adjacent_times(self, dummy_path):
        """start + 1 == stop is the minimum valid gap."""
        runner = SimulationRunner(dummy_path, 2, 3)
        runner.validate()

    def test_start_one(self, dummy_path):
        """Non-zero start_time is still valid."""
        runner = SimulationRunner(dummy_path, 1, 4)
        runner.validate()


# ---------------------------------------------------------------------------
# validate() — error paths
# ---------------------------------------------------------------------------


class TestValidateErrors:
    """Invalid combinations that must raise ValueError or FileNotFoundError."""

    def test_start_equals_stop(self, dummy_path):
        """start == stop must raise."""
        with pytest.raises(ValueError, match="strictly less than"):
            SimulationRunner(dummy_path, 3, 3).validate()

    def test_start_greater_than_stop(self, dummy_path):
        """start > stop must raise."""
        with pytest.raises(ValueError, match="strictly less than"):
            SimulationRunner(dummy_path, 4, 1).validate()

    def test_stop_equals_five(self, dummy_path):
        """stop_time == 5 violates the strict upper bound."""
        with pytest.raises(ValueError, match="< 5"):
            SimulationRunner(dummy_path, 0, 5).validate()

    def test_stop_above_five(self, dummy_path):
        """stop_time > 5 must raise."""
        with pytest.raises(ValueError, match="< 5"):
            SimulationRunner(dummy_path, 0, 10).validate()

    def test_negative_start(self, dummy_path):
        """Negative start_time must raise."""
        with pytest.raises(ValueError, match=">= 0"):
            SimulationRunner(dummy_path, -1, 3).validate()

    def test_file_not_found(self):
        """Non-existent executable path must raise FileNotFoundError."""
        runner = SimulationRunner("/totally/fake/path/exe", 0, 3)
        with pytest.raises(FileNotFoundError, match="not found"):
            runner.validate()


# ---------------------------------------------------------------------------
# build_command()
# ---------------------------------------------------------------------------


class TestBuildCommand:
    """Verify the subprocess command is constructed correctly.

    Flag format used: direct ``-startTime=<v> -stopTime=<v>`` flags.
    This works universally across all OpenModelica builds.  The
    ``-override startTime=<v>,stopTime=<v>`` style only works when the
    model exposes those names as Modelica variables (not always the case).
    """

    def test_direct_flag_format(self):
        """Command must use direct -startTime= / -stopTime= flags."""
        runner = SimulationRunner("/path/to/exe", 0, 3)
        cmd = runner.build_command()
        assert cmd == ["/path/to/exe", "-startTime=0", "-stopTime=3"]

    def test_executable_is_first(self):
        """The executable path must be the first element."""
        runner = SimulationRunner("/my/model", 1, 4)
        assert runner.build_command()[0] == "/my/model"

    def test_start_flag_value(self):
        """The -startTime flag must encode the correct integer value."""
        runner = SimulationRunner("/x", 2, 4)
        cmd = runner.build_command()
        assert "-startTime=2" in cmd

    def test_stop_flag_value(self):
        """The -stopTime flag must encode the correct integer value."""
        runner = SimulationRunner("/x", 2, 4)
        cmd = runner.build_command()
        assert "-stopTime=4" in cmd

    def test_command_length(self):
        """Exactly three elements: exe, -startTime=, -stopTime=."""
        runner = SimulationRunner("/x", 0, 1)
        assert len(runner.build_command()) == 3
