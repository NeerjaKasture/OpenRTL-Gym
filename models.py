# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Rtl Debugger Environment.

The rtl_debugger environment is a simple test environment that echoes back messages.
"""

from typing import Literal

from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field
from dataclasses import dataclass

@dataclass
class Task:
    id: str
    description: str
    max_steps: int


class EditOp(BaseModel):
    """A single edit operation on the Verilog source (supports multi-line)."""

    op: Literal["replace", "insert_after", "delete"] = Field(
        ...,
        description=(
            "'replace'  — replace lines line_number..end_line with new_content (may be multi-line). "
            "'insert_after' — insert new_content (may be multi-line) after line_number (use 0 for top). "
            "'delete'   — remove lines line_number..end_line."
        ),
    )
    line_number: int = Field(
        ...,
        description="1-indexed start line (refers to the file BEFORE any edits in this step).",
    )
    end_line: int | None = Field(
        default=None,
        description="Optional 1-indexed end line for range operations. Defaults to line_number (single line).",
    )
    new_content: str = Field(
        default="",
        description="Replacement or inserted text. Use \\n for multiple lines. Ignored for 'delete'.",
    )


class RtlDebuggerAction(Action):
    """Action for the Rtl Debugger environment — a list of line-edit operations."""

    edits: list[EditOp] = Field(
        ...,
        title="Edit Operations",
        description="Ordered list of line-edit operations to apply to the current design_active.v.",
    )


class RtlDebuggerObservation(Observation):
    """Observation from the Rtl Debugger environment - compilation and simulation results."""

    task_id: str = Field(default="", description="The identifier of the selected task")
    numbered_code: str = Field(default="", description="The current design_active.v with line numbers for reference")
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
