# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Rtl Debugger Environment.

The rtl_debugger environment is a simple test environment that echoes back messages.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field
from dataclasses import dataclass

@dataclass
class Task:
    id: str
    description: str
    max_steps: int



class RtlDebuggerAction(Action):
    """Action for the Rtl Debugger environment - submitting Verilog code."""

    fixed_code: str = Field(
        ...,
        title="Verilog Code Submission",
        description="Paste your corrected Verilog design here. Ensure the module name and ports match the original.",
        json_schema_extra={
            "lang": "verilog",
            "placeholder": "Paste your Verilog code here...",
        },
    )


class RtlDebuggerObservation(Observation):
    """Observation from the Rtl Debugger environment - compilation and simulation results."""

    task_id: str = Field(default="", description="The identifier of the selected task")
    design_code: str = Field(default="", description="The current buggy design code to fix")
    task_context: str = Field(default="", description="Instructional context describing the task")
    feedback: str = Field(default="", description="Feedback from compilation or simulation")
    compiled: bool = Field(default=False, description="Whether the code compiled successfully")
    passed_tests: bool = Field(default=False, description="Whether all test cases passed")
    pass_rate: float = Field(default=0.0, description="Functional Pass Rate (0.0 to 1.0)")
    progress_ratio: float = Field(default=0.0, description="Ratio of sequence completed before first failure")
    levenshtein_distance: int = Field(default=0, description="Number of lines changed")
    reward: float = Field(default=0.0, description="Final Reward / Score computed by the Grader")
    done: bool = Field(default=False, description="Whether the episode is done")
    score: float = Field(default=0.0, description="Final grader score [0.0, 1.0] — populated on the last step when done=True")
