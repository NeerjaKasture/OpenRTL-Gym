# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Rtl Debugger Environment Implementation.

On reset(), a random task is loaded from the tasks/ directory.
Each task folder must contain:
    design_buggy.v  - the immutable original buggy module shown to the agent
    makefile        - the cocotb makefile (must reference design_active.v)
    test_*.py       - the cocotb testbench(es) that produce result.json

design_active.v is created on reset() as a mutable working copy of design_buggy.v.
The agent overwrites design_active.v each step, so it iterates on its own previous fix.
"""

import difflib
import json
import os
import random
import re
import shutil
import subprocess
import traceback
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import RtlDebuggerAction, RtlDebuggerObservation
except ImportError:
    from models import RtlDebuggerAction, RtlDebuggerObservation

from .graders import get_grader

# Tasks directory is usually at the project root.
# We first try the current working directory (e.g. /app/env in Docker), 
# then fall back to the package-relative path.
_TASKS_DIR = os.path.join(os.getcwd(), "tasks")
if not os.path.isdir(_TASKS_DIR):
    _TASKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tasks"))


def _list_tasks() -> list[str]:
    """Return sorted list of task directory paths found under _TASKS_DIR.

    A valid task must contain design_buggy.v and a makefile.
    """
    if not os.path.isdir(_TASKS_DIR):
        return []
    return sorted(
        os.path.join(_TASKS_DIR, name)
        for name in os.listdir(_TASKS_DIR)
        if os.path.isdir(os.path.join(_TASKS_DIR, name))
        and os.path.exists(os.path.join(_TASKS_DIR, name, "design_buggy.v"))
        and os.path.exists(os.path.join(_TASKS_DIR, name, "makefile"))
    )


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def _levenshtein_line_distance(original: str, modified: str) -> int:
    """
    Compute a line-based edit distance between two strings.
    Treats line addition, deletion, and substitution as 1 operation each.
    """
    import difflib
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()
    
    matcher = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    distance = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            # substitution of a block of lines
            distance += max(i2 - i1, j2 - j1)
        elif tag == 'insert':
            distance += (j2 - j1)
        elif tag == 'delete':
            distance += (i2 - i1)
            
    return distance





class RtlDebuggerEnvironment(Environment):
    """
    RTL Debugging environment.

    On reset(), a random task is selected from the tasks/ directory.
    - design_buggy.v is read and shown to agent as the original reference.
    - design_active.v is created as a fresh mutable copy of design_buggy.v.

    On each step(), the agent submits revised code which:
      1. Is written to design_active.v (overwrites the previous attempt).
      2. Is compiled with iverilog — fatal gate if it fails.
      3. Is simulated via `make` (cocotb + icarus).
      4. Has result.json parsed for pass/fail metrics.
      5. Levenshtein distance is measured from the *previous* design_active.v.

    A separate grader() function computes the final normalized score [0,1].
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        """Initialize the rtl_debugger environment."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task_dir: str = ""
        self._design_code: str = ""   # contents of design_buggy.v (immutable reference)
        self._task_context: str = ""  # contents of context.md
        self._task_name: str = ""

    @property
    def _active_design_path(self) -> str:
        return os.path.join(self._task_dir, "design_active.v")

    def reset(self, options: dict | None = None) -> RtlDebuggerObservation:  # type: ignore[override]
        """
        Reset the environment and load a task.
        Runs the initial 'buggy' design through simulation to provide baseline feedback.
        """
        self._state = State(episode_id=str(uuid4()), step_count=0)

        tasks = _list_tasks()
        if not tasks:
            return RtlDebuggerObservation(
                task_id="",
                design_code="",
                feedback=f"No tasks found in {_TASKS_DIR}.",
                compiled=False,
                passed_tests=False,
                done=False,
                reward=0.0,
            )

        # Handle explicit task selection via options
        selected_task_dir = None
        if options and "TASK_NAME" in options:
            target_name = options["TASK_NAME"]
            for t_dir in tasks:
                if os.path.basename(t_dir) == target_name:
                    selected_task_dir = t_dir
                    break
        
        if not selected_task_dir:
            selected_task_dir = random.choice(tasks)

        self._task_dir = selected_task_dir
        self._task_name = os.path.basename(self._task_dir)
        buggy_path = os.path.join(self._task_dir, "design_buggy.v")
        self._design_code = _read(buggy_path)
        
        context_path = os.path.join(self._task_dir, "context.md")
        if os.path.exists(context_path):
            self._task_context = _read(context_path)
        else:
            self._task_context = ""

        # Initialise design_active.v from the buggy design
        shutil.copy(buggy_path, self._active_design_path)

        # Run baseline simulation to provide initial feedback
        baseline_obs = self._run_evaluation(lev_distance=0)
        
        # Override baseline feedback to include a header
        baseline_obs.feedback = f"--- (Buggy code feedback) ---\n" + baseline_obs.feedback
        return baseline_obs

    def step(self, action: RtlDebuggerAction) -> RtlDebuggerObservation:  # type: ignore[override]
        """
        Compile and simulate the submitted Verilog code against the task testbench.
        """
        self._state.step_count += 1
        code = action.fixed_code

        try:
            # --- Levenshtein vs the *previous* design_active.v (last agent attempt) ---
            prev_active = _read(self._active_design_path)
            lev_distance = _levenshtein_line_distance(prev_active, code)

            # --- 1. Write agent's code to design_active.v ---
            with open(self._active_design_path, "w") as f:
                f.write(code)

            return self._run_evaluation(lev_distance=lev_distance)

        except Exception as exc:
            traceback.print_exc()
            return RtlDebuggerObservation(
                task_id=self._task_name,
                design_code=self._design_code,
                feedback=f"[Internal Server Error] {type(exc).__name__}: {exc}",
                compiled=False,
                passed_tests=False,
                pass_rate=0.0,
                progress_ratio =0,
                reward=-1.0,
                done=False,
            )

    def _run_evaluation(self, lev_distance: int) -> RtlDebuggerObservation:
        """
        Internal helper to compile, simulate, and score the current design_active.v.
        Used by both reset() and step().
        """
        # --- 1. Compile check (mandatory gate) ---
        compile_cmd = ["iverilog", "-t", "null", "design_active.v"]
        compile_res = subprocess.run(
            compile_cmd, cwd=self._task_dir, capture_output=True, text=True
        )

        if compile_res.returncode != 0:
            feedback = compile_res.stderr or compile_res.stdout
            return RtlDebuggerObservation(
                task_id=self._task_name,
                design_code=self._design_code,
                task_context=self._task_context,
                feedback=f"[Compile Error]\n{feedback}",
                compiled=False,
                passed_tests=False,
                pass_rate=0.0,
                progress_ratio =0,
                levenshtein_distance=lev_distance,
                reward=-2.0,
                done=False,
            )

        # --- 2. Run cocotb testbench via make in the task dir ---
        try:
            make_res = subprocess.run(
                ["make"],
                cwd=self._task_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            make_feedback = make_res.stdout + make_res.stderr
        except subprocess.TimeoutExpired:
            return RtlDebuggerObservation(
                task_id=self._task_name,
                design_code=self._design_code,
                task_context=self._task_context,
                feedback="[Simulation Timeout] Your design likely contains an infinite loop (e.g., an always @ block without a state change or sensitivity list issue). Simulation killed after 60s.",
                compiled=True,
                passed_tests=False,
                pass_rate=0.0,
                progress_ratio =0,
                levenshtein_distance=lev_distance,
                reward=-5.0,
                done=False,
            )

        # --- 3. Parse result.json (written by cocotb into the task dir) ---
        result_path = os.path.join(self._task_dir, "result.json")
        if not os.path.exists(result_path):
            return RtlDebuggerObservation(
                task_id=self._task_name,
                design_code=self._design_code,
                task_context=self._task_context,
                feedback=f"=== Simulation/Build Error ===\nSimulation crashed before producing results.\nError Log:\n{make_feedback}",
                compiled=True,
                passed_tests=False,
                pass_rate=0.0,
                progress_ratio =0,
                levenshtein_distance=lev_distance,
                reward=-3.0,
                done=False,
            )

        with open(result_path, "r") as f:
            result_data = json.load(f)

        num_tests = result_data.get("num_tests", 1)
        num_passed = result_data.get("num_passed", 0)
        pass_rate = num_passed / num_tests if num_tests > 0 else 0.0
        passed_all = result_data.get("passed", False)

        # Base reward for overall correctness
        reward = pass_rate * 12.0
        
        # Bonus reward for sequential correctness (fixing earliest bugs first)
        results_list = result_data.get("results", [])
        sequential_passes = 0
        for r in results_list:
            if r.get("pass", True):
                sequential_passes += 1
            else:
                break
                
        progress_ratio  = sequential_passes / max(num_tests, 1)
        reward += progress_ratio * 3.0  
        reward -= min(lev_distance * 0.01, 1.0) 

        if lev_distance == 0 and self._state.step_count > 0:
            reward -= 2.0
        if passed_all:
            reward += 20.0

        seq_count = result_data.get("sequence_correctness", "?")
        trans_count = result_data.get("transition_correctness", "?")

        feedback_lines = [
            f"Compiled: OK | Tests: {num_passed}/{num_tests} passed | Seq: {seq_count}/{num_tests} | Trans: {trans_count}/{num_tests} | First failure after: {progress_ratio:.2f} of sequence"
        ]
        
        # Parse failed test cases from result.json
        if "results" in result_data:
            failed_tests = [r for r in result_data["results"] if not r.get("pass", True)]
            if failed_tests:
                feedback_lines.append("\n=== Failed Test Cases ===")
                for ft in failed_tests[:10]:
                    inp = ft.get("inputs") or ft.get("input", {})
                    inputs_str = ", ".join(f"{k}={v}" for k, v in inp.items()) if isinstance(inp, dict) else str(inp)
                    cycle = ft.get("test_id", "?")
                    expected = ft.get("expected_output", "?")
                    actual = ft.get("actual_output", "?")
                    
                    state_info = ""
                    if "transition_to" in ft:
                        was_s  = ft.get("actual_state_meaning", ft.get("actual_state", "?"))
                        went_s = ft.get("transition_to_meaning", ft.get("transition_to", "?"))
                        exp_s  = ft.get("expected_next_state_meaning", ft.get("expected_next_state", "?"))
                        state_info = f" | was state {was_s}, went to state {went_s} (expected state {exp_s})"
                    
                    feedback_lines.append(f"- Cycle {cycle}: [{inputs_str}] -> Expected: {expected}, Got: {actual}{state_info}")

        feedback = "\n".join(filter(None, feedback_lines))
        grader = get_grader(self._task_name)
        final_score = grader(self._state, self)

        return RtlDebuggerObservation(
            task_id=self._task_name,
            design_code=self._design_code,
            task_context=self._task_context,
            feedback=feedback,
            compiled=True,
            passed_tests=passed_all,
            pass_rate=pass_rate,
            progress_ratio=progress_ratio,
            levenshtein_distance=lev_distance,
            reward=reward,
            done=passed_all,
            score=final_score,
        )

    @property
    def state(self) -> State:
        """
        Get the current environment state.

        Returns:
            Current State with episode_id and step_count
        """
        return self._state
