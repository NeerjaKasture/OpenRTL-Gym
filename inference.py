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
    from .models import RtlDebuggerAction
except ImportError:
    from client import RtlDebuggerEnv  # type: ignore
    from models import RtlDebuggerAction  # type: ignore

# --- Configuration -------------------------------------------------------------
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HF_TOKEN = os.getenv("HF_TOKEN")

# if OPENAI_API_KEY:
#     # Use OpenAI directly
#     API_BASE_URL = os.getenv("API_BASE_URL") # use default (None) for OpenAI
#     API_KEY = OPENAI_API_KEY
#     MODEL_NAME = os.getenv("MODEL_NAME") or "gpt-4o"
# elif GEMINI_API_KEY:
#     # Set defaults for Gemini (which uses an OpenAI-compatible endpoint)
#     API_BASE_URL = os.getenv("API_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
#     API_KEY = GEMINI_API_KEY
#     MODEL_NAME = os.getenv("MODEL_NAME") or "gemini-2.5-flash"
# else:
#     # Fall back to Hugging Face router
#     API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
#     API_KEY = HF_TOKEN or os.getenv("API_KEY")
#     MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct:novita"


API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

TASK_NAME = os.getenv("RTL_DEBUGGER_TASK_NAME", "unknown-task")
IMAGE_NAME = os.getenv("IMAGE_NAME")

MAX_STEPS = 8
TEMPERATURE = 0.3
MAX_TOKENS = 8192




# --- Prompts -------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an expert RTL hardware engineer specialist. Your goal is to debug and fix buggy Verilog modules."
    "\n\nRules:"
    "\n1. Analyze the provided Verilog code, the task context, and the simulator feedback."
    "\n2. Identify the logical or syntax errors."
    "\n3. Provide the CORRECTED Verilog module in a ```verilog ... ``` block."
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
    initial_design: str,
    task_context: str,
    history: List[Tuple[str, str]],
    latest_feedback: str,
) -> str:
    """
    Build the user prompt for the current step.
    Args:
        step: Current step number (1-indexed).
        initial_design: The original buggy Verilog design.
        task_context: Instructions or specifications for the task.
        history: List of (code_submitted, feedback_received) from previous steps.
        latest_feedback: The most recent feedback from the environment (before this step's submission).
    """
    # 1. HISTORY SECTION (Last 3-4 attempts)
    history_section = ""
    if history:
        history_lines = []
        # Calculate exactly which attempts to show
        start_idx = max(0, len(history) - 3) 
        for i, (code, hist_feedback) in enumerate(history[start_idx:], start=start_idx + 1):
            history_lines.append(
                f"### Attempt {i} ###\n"
                f"--- Submittal ---\n```verilog\n{code.strip()}\n```\n"
                f"--- Result ---\n{hist_feedback.strip() or '(no output)'}"
            )
        history_section = "\n\n" + "\n\n".join(history_lines)

    # 2. CURRENT INSTRUCTION
    current_feedback = latest_feedback if not history else "" # latest_feedback is in history[-1]
    
    context_section = f"### Task Context ###\n{task_context.strip()}\n" if task_context else ""

    # 3. BUILD FEEDBACK SECTION
    # Move \n out of f-string expression for Python < 3.12 compatibility
    if history:
        progress_info = history_section
    else:
        progress_info = f"--- Initial Feedback ---\n{latest_feedback.strip()}"

    return textwrap.dedent(
        f"""
        --- INSTRUCTIONS ---
        You are an expert RTL engineer. Your goal is to fix the provided Verilog design.
        1. Examine the 'Task Context' and 'Original Design' to understand the intended behavior.
        2. Study your 'Previous Attempts' and the 'Latest Result' to pinpoint where the logic is failing.
        3. Provide the FULL corrected Verilog module in a ```verilog block.
        
        {context_section}
        ### Original (buggy) starting point ###
        ```verilog
        {initial_design.strip()}
        ```

        {progress_info}

        --- Current Objective ---
        Based on the feedback above, provide your NEXT corrected attempt. 
        Focus on fixing the first error cycle reported. 
        Reply with the corrected design module in a ```verilog block.
        """
    ).strip()


def _extract_verilog(response_text: str) -> str:
    """
    Extract the Verilog code block from the LLM response.
    More robustly strips fences even when the response is truncated.
    """
    cleaned = response_text.strip()

    # Case 1: Standard fenced block (most common)
    match = re.search(r"```(?:verilog)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Case 2: Opening fence exists but closing fence is missing (likely truncation)
    match = re.search(r"```(?:verilog)?\s*(.*)", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Case 3: No fences at all
    # Still strip any occasional leading/trailing code-block markers if they leak through
    lines = cleaned.splitlines()
    if lines and (lines[0].startswith("```") or lines[-1].startswith("```")):
        return "\n".join([line for line in lines if not line.strip().startswith("```")]).strip()

    return cleaned


def _get_llm_response(llm: OpenAI, messages: List[dict], max_retries: int = 4) -> str:
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
            if "rate limit" in err_msg or "too many requests" in err_msg or "temporary" in err_msg or attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2  # Exponential backoff: 2, 4, 8, 16...
                print(f"[Retry] Attempt {attempt + 1} failed: {exc}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise exc
    return ""


SERVER_URL = os.getenv("RTL_SERVER_URL", "http://localhost:8000")


def main() -> None:
    llm = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    history: List[Tuple[str, str]] = []  # (code, feedback) pairs
    rewards: List[float] = []
    success = False
    num_steps = 0
    final_score = 0.0

    # final_score is tracked to report at end
    final_score = 0.0

    try:
        with RtlDebuggerEnv(base_url=SERVER_URL).sync() as env:
            # Pass TASK_NAME if specified to select a specific task
            reset_options = {"TASK_NAME": TASK_NAME} if TASK_NAME and TASK_NAME != "unknown-task" else None
            result = env.reset(options=reset_options)
            obs = result.observation
            initial_design = obs.design_code
            task_context = obs.task_context
            latest_feedback = obs.feedback

            # Emit the START line using the actual task_id from the observation
            # (this handles random task selection correctly)
            actual_task = obs.task_id
            print(f"[START] task={actual_task} env=rtl-debugger model={MODEL_NAME}")

            if not initial_design:
                return

            for step in range(1, MAX_STEPS + 1):
                if result.done:
                    break

                num_steps = step
                user_prompt = _build_user_prompt(
                    step=step,
                    initial_design=initial_design,
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
                    code = _extract_verilog(response_text)
                    action_log = json.dumps(code)
                    
                    result = env.step(RtlDebuggerAction(fixed_code=code))
                    obs = result.observation
                    
                    latest_feedback = obs.feedback
                    rewards.append(result.reward)
                    history.append((code, obs.feedback))
                    success = result.done
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
                    print(f"[STEP] step={step} action={action_log} reward=0.00 done={done_str} error={last_error}")
                    break

                # Emit the STEP line per spec
                done_str = "true" if result.done else "false"
                print(f"[STEP] step={step} action={action_log} reward={result.reward:0.2f} done={done_str} error={last_error}")

    finally:
        # Emit the END line (always)
        success_str = "true" if success else "false"
        rewards_str = ",".join([f"{r:0.2f}" for r in rewards])
        print(f"[END] success={success_str} steps={num_steps} rewards={rewards_str}")
        final_score = max(0.01, min(0.99, final_score))
        print(f"Grader Score for {TASK_NAME} : {final_score:.3f}")


if __name__ == "__main__":
    main()

