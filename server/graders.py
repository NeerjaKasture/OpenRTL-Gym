import json
import os
from openenv.core.env_server.types import State

class Task1Grader:
    """
    Grader for Task 1 (Syntax/Compilation Errors).
    Evaluates based on:
    - Linting and Compilation passed.
    - Number of steps needed.
    """
    def __init__(self, max_steps: int = 10):
        self.max_steps = max_steps

    def __call__(self, state: State, env: "RtlDebuggerEnvironment") -> float:
        result_path = os.path.join(env._task_dir, "result.json")
        if not os.path.exists(result_path):
            return 0.01

        try:
            with open(result_path, "r") as f:
                result_json = json.load(f)
        except json.JSONDecodeError:
            return 0.01

        step_efficiency = (state.step_count / self.max_steps)
        score = 1.0 - step_efficiency
        

        return max(0.01, min(0.99, score))


class Task2Grader:
    """
    Grader for Task 2 (Combinational Logic).
    Evaluates based on:
    - Number of test cases passed.
    - Number of steps needed.
    """
    def __init__(self, max_steps: int = 10):
        self.max_steps = max_steps

    def __call__(self, state: State, env: "RtlDebuggerEnvironment") -> float:
        result_path = os.path.join(env._task_dir, "result.json")
        if not os.path.exists(result_path):
            return 0.01

        try:
            with open(result_path, "r") as f:
                result_json = json.load(f)
        except json.JSONDecodeError:
            return 0.01

        num_passed = result_json.get("num_passed", 0)
        num_tests = result_json.get("num_tests", 1)
        passed_all = result_json.get("passed", False)
        pass_rate = num_passed / num_tests if num_tests > 0 else 0.0

        if passed_all:
            step_efficiency = (state.step_count / self.max_steps)
            score = 1.0 - step_efficiency
        else:
            score = pass_rate * 0.7

        return max(0.01, min(0.99, score))


class Task3Grader:
    """
    Grader for Task 3 (Sequential Logic).
    Evaluates based on:
    - Sequence correctness
    - Transition correctness
    - Penalties for deadlock, oscillation, wrong encoding
    - Reset working
    """
    def __init__(self, max_steps: int = 10):
        self.max_steps = max_steps

    def __call__(self, state: State, env: "RtlDebuggerEnvironment") -> float:
        result_path = os.path.join(env._task_dir, "result.json")
        if not os.path.exists(result_path):
            # No result.json usually means compilation error or simulation timeout (deadlock/oscillation)
            return 0.01

        try:
            with open(result_path, "r") as f:
                result_json = json.load(f)
        except json.JSONDecodeError:
            return 0.01

        seq_count = result_json.get("sequence_correctness", 0)
        trans_count = result_json.get("transition_correctness", 0)
        
        num_passed = result_json.get("num_passed", 0)
        num_tests = result_json.get("num_tests", 1)
        
        seq_rate = seq_count / num_tests if num_tests > 0 else 0.0
        trans_rate = trans_count / num_tests if num_tests > 0 else 0.0
        pass_rate = num_passed / num_tests if num_tests > 0 else 0.0
        
        passed_all = result_json.get("passed", False)
        
        score = 0.0
        # Partial credit based on sequential milestones
        score += seq_rate * 0.4
        score += trans_rate * 0.4
        # Note: reset_working was removed from testbench or ignored for now, 
        # but we could add it back if needed. For now let's use the remaining 0.2
        # as a bonus for passing everything.
        
        if passed_all:
            score += 0.2
            step_efficiency = (state.step_count / self.max_steps)
            score = 1.0 - step_efficiency
            
        return max(0.01, min(0.99, score))


def get_grader(task_id: str):
    """Factory function to retrieve the appropriate grader for a task."""
    graders = {
        "task1": Task1Grader(),
        "task2": Task2Grader(),
        "task3": Task3Grader(),
    }
    return graders.get(task_id, Task1Grader())

