"""
simulation_runner.py
====================
Pure-Python, Qt-free logic for launching a compiled OpenModelica model
executable with user-supplied simulation parameters.

The module is deliberately kept free of any PyQt6 imports so that it can be
unit-tested without a display server.

Flag-format note
----------------
OpenModelica simulation executables support two flag styles:

  Style A (``-override``):
      Works when ``startTime`` / ``stopTime`` are exposed as *model* variables.
      ``TwoConnectedTanks.exe -override startTime=0,stopTime=3``

  Style B (direct flags) — used here:
      Works universally; ``startTime`` and ``stopTime`` are treated as
      experiment-level settings regardless of how the model was compiled.
      ``TwoConnectedTanks.exe -startTime=0 -stopTime=3``

Working-directory note
----------------------
The executable looks for ``<ModelName>_init.xml`` in the **current working
directory** at startup.  :meth:`SimulationRunner.run` therefore sets
``cwd`` to the directory that contains the executable.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SimulationResult:
    """
    Holds the outcome of a single simulation run.

    Attributes
    ----------
    success : bool
        ``True`` when the process exited with return-code 0.
    output : str
        Combined stdout + stderr from the child process.
    return_code : int
        Raw OS return-code (0 = success).
    error_message : Optional[str]
        Human-readable error description when ``success`` is ``False``.
    """

    success: bool
    output: str
    return_code: int = 0
    error_message: Optional[str] = field(default=None)


class SimulationRunner:
    """
    Wraps the launch of a compiled OpenModelica model executable, passing
    ``startTime`` / ``stopTime`` via the ``-override`` flag.

    Parameters
    ----------
    executable_path : str
        Absolute or relative path to the compiled model binary.
    start_time : int
        Simulation start time in seconds.  Must satisfy ``0 <= start_time``.
    stop_time : int
        Simulation stop time in seconds.  Must satisfy ``start_time < stop_time < 5``.

    Example
    -------
    >>> runner = SimulationRunner("/path/to/TwoConnectedTanks", 0, 3)
    >>> result = runner.run()
    >>> print(result.output)
    """

    #: Maximum permitted stop-time (exclusive) as per the task specification.
    MAX_STOP_TIME: int = 5

    def __init__(
        self,
        executable_path: str,
        start_time: int,
        stop_time: int,
    ) -> None:
        self.executable_path: str = executable_path
        self.start_time: int = start_time
        self.stop_time: int = stop_time

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Raise ``ValueError`` if the simulation parameters are out of range.

        Constraints enforced
        --------------------
        * ``0 <= start_time``
        * ``start_time < stop_time``
        * ``stop_time < MAX_STOP_TIME``  (i.e. ``< 5``)

        Raises
        ------
        ValueError
            When any constraint is violated, with a descriptive message.
        FileNotFoundError
            When the executable path does not point to an existing file.
        """
        if self.start_time < 0:
            raise ValueError(
                f"start_time must be >= 0, got {self.start_time!r}."
            )
        if self.start_time >= self.stop_time:
            raise ValueError(
                f"start_time ({self.start_time}) must be strictly less than "
                f"stop_time ({self.stop_time})."
            )
        if self.stop_time >= self.MAX_STOP_TIME:
            raise ValueError(
                f"stop_time must be < {self.MAX_STOP_TIME}, "
                f"got {self.stop_time!r}."
            )
        if not os.path.isfile(self.executable_path):
            raise FileNotFoundError(
                f"Executable not found: {self.executable_path!r}"
            )

    # ------------------------------------------------------------------
    # Command construction
    # ------------------------------------------------------------------

    def build_command(self) -> list[str]:
        """
        Return the subprocess command list that launches the model.

        Uses *direct flag* style (``-startTime=<v> -stopTime=<v>``) which
        works for all OpenModelica builds.  The ``-override`` style only
        works when the model exposes those names as Modelica variables, which
        is not guaranteed for compiled packages.

        Returns
        -------
        list[str]
            E.g. ``["/path/to/exe", "-startTime=0", "-stopTime=3"]``
        """
        return [
            self.executable_path,
            f"-startTime={self.start_time}",
            f"-stopTime={self.stop_time}",
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _build_env() -> dict:
        """
        Return an environment dict with OpenModelica's ``bin/`` directory
        prepended to ``PATH`` so the executable can load its runtime DLLs
        on Windows without requiring a system-wide PATH change.

        The method checks the two most common installation locations and
        falls back to the inherited environment unchanged when neither is
        found (e.g. on Linux where the shared libs are handled by the
        system linker).
        """
        import copy
        env = copy.deepcopy(os.environ)
        om_candidates = [
            r"C:\Program Files\OpenModelica1.27.0-64bit\bin",
            r"C:\OpenModelica1.27.0-64bit\bin",
        ]
        for candidate in om_candidates:
            if os.path.isdir(candidate):
                env["PATH"] = candidate + os.pathsep + env.get("PATH", "")
                break
        return env

    def run(self) -> SimulationResult:
        """
        Validate parameters, then launch the model executable as a subprocess.

        Key runtime requirements handled automatically
        ---------------------------------------------
        * **Working directory** is set to the folder containing the executable
          so the binary can locate ``<Model>_init.xml`` (it searches the cwd).
        * **OpenModelica DLLs** — on Windows the OM ``bin/`` directory is
          injected into ``PATH`` so the exe finds its runtime libraries
          without a manual system PATH change.

        Returns
        -------
        SimulationResult
            Populated with the combined stdout+stderr, return-code, and a
            convenience ``success`` flag.

        Raises
        ------
        ValueError
            If parameters are invalid (delegated from :meth:`validate`).
        FileNotFoundError
            If the executable does not exist (delegated from :meth:`validate`).
        subprocess.TimeoutExpired
            If the simulation does not complete within 60 seconds.
        """
        self.validate()

        # The exe must run from its own directory so _init.xml is found.
        exe_dir = str(Path(self.executable_path).resolve().parent)
        exe_abs = str(Path(self.executable_path).resolve())

        cmd = [exe_abs] + self.build_command()[1:]  # replace path with absolute
        env = self._build_env()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=exe_dir,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return SimulationResult(
                success=False,
                output="",
                return_code=-1,
                error_message=f"Simulation timed out after 60 s: {exc}",
            )

        combined_output = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        return SimulationResult(
            success=ok,
            output=combined_output,
            return_code=proc.returncode,
            error_message=None if ok else f"Process exited with code {proc.returncode}.",
        )
