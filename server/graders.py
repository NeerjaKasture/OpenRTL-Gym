import json
import os
from openenv.core.env_server.types import State
from server.rtl_debugger_environment import RtlDebuggerEnvironment

class RtlGrader:
    """
    External Grader for the RTL Debugger Environment.
    Evaluates the final state of the environment after the episode finishes.
    """
    
    def __call__(self, state: State, env: RtlDebuggerEnvironment) -> float:
        """
        OpenEnv interface for grading.
        Reads the final result.json from the active task directory and computes the score.
        """
        result_path = os.path.join(env._task_dir, "result.json")
        
        # If no result.json exists, the simulation crashed or failed to compile
        if not os.path.exists(result_path):
            return 0.01

        try:
            with open(result_path, "r") as f:
                result_json = json.load(f)
        except json.JSONDecodeError:
            return 0.01

        num_tests  = result_json.get("num_tests", 1)
        num_passed = result_json.get("num_passed", 0)
        passed_all = result_json.get("passed", False)

        pass_rate       = num_passed / num_tests if num_tests > 0 else 0.0
        step_efficiency = (state.step_count / 8)  # max_steps = 8

        if passed_all:
            # Solved — difficulty determined by how many steps it needed
            score = 1.0 - step_efficiency   
        else:
            # Not solved — difficulty = how far it got from a full solution
            score = (pass_rate * 0.7)

        # Clamp to (0, 1) range strictly
        return max(0.01, min(0.99, score))
