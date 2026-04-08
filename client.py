# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Rtl Debugger Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import RtlDebuggerAction, RtlDebuggerObservation
except ImportError:
    from models import RtlDebuggerAction, RtlDebuggerObservation  # type: ignore


class RtlDebuggerEnv(
    EnvClient[RtlDebuggerAction, RtlDebuggerObservation, State]
):
    """
    Client for the Rtl Debugger Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with RtlDebuggerEnv(base_url="http://localhost:7860") as client:
        ...     result = client.reset()
        ...     print(result.observation.echoed_message)
        ...
        ...     result = client.step(RtlDebuggerAction(message="Hello!"))
        ...     print(result.observation.echoed_message)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = RtlDebuggerEnv.from_docker_image("rtl_debugger-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(RtlDebuggerAction(message="Test"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: RtlDebuggerAction) -> Dict:
        """
        Convert RtlDebuggerAction to JSON payload for step message.

        Args:
            action: RtlDebuggerAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "edits": [e.model_dump() for e in action.edits],
        }

    def _parse_result(self, payload: Dict) -> StepResult[RtlDebuggerObservation]:
        """
        Parse server response into StepResult[RtlDebuggerObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with RtlDebuggerObservation
        """
        obs_data = payload.get("observation", {})
        observation = RtlDebuggerObservation(
            task_id=obs_data.get("task_id", ""),
            numbered_code=obs_data.get("numbered_code", ""),
            task_context=obs_data.get("task_context", ""),
            feedback=obs_data.get("feedback", ""),
            compiled=obs_data.get("compiled", False),
            passed_tests=obs_data.get("passed_tests", False),
            pass_rate=obs_data.get("pass_rate", 0.0),
            progress_ratio=obs_data.get("progress_ratio", 0.0),
            levenshtein_distance=obs_data.get("levenshtein_distance", 0),
            reward=obs_data.get("reward", 0.0),
            done=obs_data.get("done", False),
            score=obs_data.get("score", 0.0),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
