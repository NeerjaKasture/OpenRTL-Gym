"""
Inference Script — RTL Debugger Environment
============================================
MANDATORY
- Before submitting, ensure the following variables are set in your environment:
    API_BASE_URL   The API endpoint for the LLM (e.g. https://router.huggingface.co/v1)
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root of the project.
- Participants must use the OpenAI client for all LLM calls using the above variables.

"""

import os
import re
import textwrap
import time
from typing import List, Tuple
import json

# Load .env from this file's directory or any parent (picks up repo-root .env)
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=False))  # walks up from __file__ location
except ImportError:
    pass  # dotenv not installed; rely on environment variables being set manually

from openai import OpenAI

try:
    from .client import RtlDebuggerEnv
    from .models import EditOp, RtlDebuggerAction
except ImportError:
    from client import RtlDebuggerEnv  # type: ignore
    from models import EditOp, RtlDebuggerAction  # type: ignore

# --- Configuration -------------------------------------------------------------
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HF_TOKEN = os.getenv("HF_TOKEN")

# if OPENAI_API_KEY:
#     # Use OpenAI directly
#     API_BASE_URL = os.getenv("API_BASE_URL") # use default (None) for OpenAI
#     API_KEY = OPENAI_API_KEY
#     MODEL_NAME = "gpt-4o"
# elif GEMINI_API_KEY:
#     # Set defaults for Gemini (which uses an OpenAI-compatible endpoint)
#     API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
#     API_KEY = GEMINI_API_KEY
#     MODEL_NAME = "gemini-2.5-flash"
# else:
#     # Fall back to Hugging Face router
#     API_BASE_URL = "https://router.huggingface.co/v1"
#     API_KEY = HF_TOKEN or os.getenv("API_KEY")
#     MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct:novita"


API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct:novita"

TASK_NAME = os.getenv("RTL_DEBUGGER_TASK_NAME", "unknown-task")
IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

MAX_STEPS = 8
TEMPERATURE = 0.3
MAX_TOKENS = 8192

SUCCESS_SCORE_THRESHOLD = 0.1

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")


# --- Prompts -------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an expert RTL hardware engineer. Your goal is to debug Verilog modules by making targeted edits."
    "\n\nRules:"
    "\n1. Analyse the numbered source code and simulator feedback to identify bugs."
    "\n2. Respond ONLY with a JSON array of edit operations."
    "\n3. Operations:"
    '\n   {"op": "replace"|"insert_after"|"delete", "line_number": <int>, "end_line": <int|null>, "new_content": "<string>"}'
    "\n   - replace: replaces lines line_number through end_line (inclusive). Use \\n for multi-line replacement."
    "\n   - insert_after: inserts new_content after line_number. Use \\n for multi-line."
    "\n   - delete: removes lines line_number through end_line."
    "\n\nEXAMPLE (Replace lines 5-7 with a fixed 2-line block):"
    '\n[{"op": "replace", "line_number": 5, "end_line": 7, "new_content": "  always @(posedge clk)\\n    q <= d;"}]'
    "\n\n4. Line numbers refer to the CURRENT design shown to you. Output ONLY the JSON array."
).strip()


def _load_file(path: str) -> str:
    """Read a file, returning its contents or a placeholder if missing."""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"(file not found: {path})"


def _build_user_prompt(
    step: int,
    numbered_code: str,
    task_context: str,
    history: List[Tuple[str, str, float]],
    latest_feedback: str,
) -> str:
    """
    Build the user prompt for the current step.
    Args:
        step: Current step number (1-indexed).
        numbered_code: The current design_active.v with line numbers.
        task_context: Instructions or specifications for the task.
        history: List of (edits_json, feedback_received, reward) from previous steps.
        latest_feedback: The most recent feedback from the environment.
    """
    # 1. HISTORY SECTION (Last 3 attempts)
    history_section = ""
    if history:
        history_lines = []
        start_idx = max(0, len(history) - 3)
        for i, (edits_str, hist_feedback, hist_reward) in enumerate(history[start_idx:], start=start_idx + 1):
            history_lines.append(
                f"### Attempt {i} ###\n"
                f"--- Edits Applied ---\n{edits_str}\n"
                f"--- Result ---\n{hist_feedback.strip() or '(no output)'}\n"
                f"--- Reward ---\n{hist_reward:0.2f}"
            )
        history_section = "\n\n" + "\n\n".join(history_lines)

    context_section = f"### Task Context ###\n{task_context.strip()}\n" if task_context else ""

    if history:
        progress_info = history_section
    else:
        progress_info = f"--- Initial Feedback ---\n{latest_feedback.strip()}"

    return textwrap.dedent(
        f"""
        --- INSTRUCTIONS ---
        You are an expert RTL engineer. Fix the Verilog design by making targeted edits.
        
        APPROACH:
        1. Read the 'Task Context' carefully to understand the INTENDED behavior.
        2. Look at 'Failed Test Cases': the inputs, expected outputs, and actual outputs tell you exactly which logic path is wrong.
        3. Make the MINIMUM edits needed to fix the bug. 
        
        Respond ONLY with a JSON array of edit operations. NO explanation.

        {context_section}
        ### Current Design (with line numbers) ###
        {numbered_code.strip()}

        {progress_info}

        --- Respond with a JSON array of edits ---
        """
    ).strip()


def _extract_edits(response_text: str) -> list[dict]:
    """
    Extract a JSON array of edit operations from the LLM response.
    Handles optional markdown fences and leading/trailing text.
    """
    cleaned = response_text.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Try to find the JSON array directly
        match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

    try:
        edits = json.loads(cleaned)
        if isinstance(edits, list):
            return edits
    except json.JSONDecodeError:
        pass

    # Last resort: return empty edits (no-op)
    return []


def _get_llm_response(llm: OpenAI, messages: List[dict], max_retries: int = 6) -> str:
    """Gets LLM response with basic retry logic for rate limits and temporary failures."""
    for attempt in range(max_retries):
        try:
            completion = llm.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            # Check for rate limit or retryable errors
            err_msg = str(exc).lower()
            if "rate limit" in err_msg or "too many requests" in err_msg or "temporary" in err_msg or "quota" in err_msg or attempt < max_retries - 1:
                # Default exponential backoff
                wait_time = (2 ** attempt) * 2
                
                # Check if the API explicitly tells us how long to wait
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg)
                if match:
                    # add a small buffer of 2s to the requested retry time
                    wait_time = float(match.group(1)) + 2.0
                
                print(f"[RETRY] Attempt {attempt + 1} failed: {exc}. Retrying in {wait_time:.2f}s...", flush=True)
                time.sleep(wait_time)
            else:
                raise exc
    return ""


def run_task(env: RtlDebuggerEnv, llm: OpenAI, task_id: str) -> None:
    """Run the inference loop for a single task."""
    history: List[Tuple[str, str, float]] = []  # (code, feedback, reward) triples
    rewards: List[float] = []
    num_steps = 0
    final_score = 0.0

    # Pass task_id to select the specific task
    reset_options = {"TASK_NAME": task_id}
    result = env.reset(options=reset_options)
    obs = result.observation
    task_context = obs.task_context
    latest_feedback = obs.feedback
    numbered_code = obs.numbered_code

    # Emit the START line using the actual task_id from the observation
    actual_task = obs.task_id
    print(f"[START] task={actual_task} env=rtl-debugger model={MODEL_NAME}", flush=True)

    if not numbered_code:
        print(f"[END] success=false steps=0 score=0.01 rewards=[]", flush=True)
        return

    for step in range(1, MAX_STEPS + 1):
        if result.done:
            break

        num_steps = step
        user_prompt = _build_user_prompt(
            step=step,
            numbered_code=numbered_code,
            task_context=task_context,
            history=history,
            latest_feedback=latest_feedback,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Initialize log variables for this step
        action_log = "null"
        last_error = "null"

        try:
            response_text = _get_llm_response(llm, messages)
            raw_edits = _extract_edits(response_text)
            edit_ops = [EditOp(**e) for e in raw_edits]
            action_log = json.dumps(raw_edits)

            result = env.step(RtlDebuggerAction(edits=edit_ops))
            obs = result.observation

            latest_feedback = obs.feedback
            numbered_code = obs.numbered_code  # refresh with post-edit version
            rewards.append(result.reward)
            history.append((action_log, obs.feedback, result.reward))
            final_score = obs.score

            # If not everything passed, feedback is considered the current error
            if not result.done:
                if obs.compiled:
                    # Simplified message for successful compiles that failed tests
                    last_error = json.dumps(f"Compiled, Pass ratio: {obs.pass_rate:.2f}")
                else:
                    # Show full feedback for compile errors
                    last_error = json.dumps(obs.feedback)
        except Exception as exc:
            last_error = json.dumps(str(exc))
            done_str = "false"
            print(f"[STEP] step={step} action={action_log} reward=0.00 done={done_str} error={last_error}", flush=True)
            break

        # Emit the STEP line per spec
        done_str = "true" if result.done else "false"
        print(f"[STEP] step={step} action={action_log} reward={result.reward:0.2f} done={done_str} error={last_error}", flush=True)

    # Emit the END line (always)
    rewards_str = ",".join([f"{r:0.2f}" for r in rewards])
    final_score = max(0.01, min(0.99, final_score))
    success = final_score >= SUCCESS_SCORE_THRESHOLD
    success_str = "true" if success else "false"
    print(f"[END] success={success_str} steps={num_steps} score={final_score:.2f} rewards={rewards_str}", flush=True)


def main() -> None:
    # 1. Initialize LLM client
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # 2. Determine which tasks to run
    # Check both TASK_NAME and RTL_DEBUGGER_TASK_NAME for flexibility
    target_task = os.getenv("TASK_NAME") or os.getenv("RTL_DEBUGGER_TASK_NAME")
    if target_task and target_task != "unknown-task":
        tasks_to_run = [target_task]
    else:
        tasks_to_run = ["task1", "task2", "task3"]

    # 3. Connect to the environment and iterate
    try:
        with RtlDebuggerEnv(base_url=ENV_BASE_URL ).sync() as env:
            for task_id in tasks_to_run:
                run_task(env, llm_client, task_id)
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to connect to RTL server or run tasks: {e}", flush=True)


if __name__ == "__main__":
    main()

