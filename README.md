---
title: RTL Debugger Environment
emoji: 🛠️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
base_path: /web
tags:
  - openenv
  - verilog
  - rl
  - rtl
---

# RTL Debugger Environment

The **RTL Debugger** is a Reinforcement Learning environment designed for automated hardware design fixing. It enables LLM-based agents to iteratively debug Verilog code through high-fidelity simulation feedback.

## 🚀 Motivation
Hardware debugging is a high-cost, iterative process. While LLMs are proficient at syntax-level code generation, fixing semantic bugs in RTL (Register Transfer Level) designs requires a deep understanding of timing, cycle-by-cycle logic, and state transitions. This environment provides a standardized sandbox for training and evaluating agents capable of interprets complex simulation logs and autonomously resolving hardware logic flaws.

## 🛠️ Environment Description
The RTL Debugger is an OpenEnv-compliant environment that wraps industry-standard hardware tools:
- **Simulation Engines**: Supports **Icarus Verilog** simulation.
- **Feedback Loop**: For every submitted design, the environment provides a detailed diagnostic report in result.json which is given as feedback to the agent
- **Iterative Debugging**: Agents can build upon their previous attempts, utilizing line-based edit distance (Levenshtein) and pass-rate progress to guide their refinement.

PS. This was somewhat hard to benchmark since the model performance varies wildly based on LLM used. Gemini, for instance did very well, but not so much for Qwen.

## Quick Start

### 1. Build the Environment
The environment runs in a Docker container to ensure all hardware tools are correctly installed.

```bash
# Build the image locally
docker build -t rtl_debugger-env:latest .
```

### 2. Launch the Environment Server
```bash
docker run -p 7860:7860 --rm rtl_debugger-env:latest
```
Access the interactive web-playground at: [http://localhost:7860/web](http://localhost:7860/web)

### 3. Run the Inference Agent
We provide a reference inference script that uses LLM to play the environment:

```bash
# Install dependencies
uv sync

# Configure your API_KEY, MODEL_NAME and  in .env
# Run the evaluation loop
uv run python inference.py
```

## Environment Details

### Action Space (`RtlDebuggerAction`)
The agent submits a list of **line-level edit operations** on the current `design_active.v`:

```json
[
  {
    "op": "replace", 
    "line_number": 5, 
    "end_line": 7, 
    "new_content": "    // Fixed block with multi-line support\n    assign sum = a ^ b;\n    assign carry = a & b;"
  },
  {
    "op": "insert_after", 
    "line_number": 2, 
    "new_content": "    output sum, carry;"
  },
  {
    "op": "delete", 
    "line_number": 10, 
    "end_line": 12
  }
]
```

| Operation | Parameters | Meaning |
|:---|:---|:---|
| `replace` | `line_number`, `end_line`, `new_content` | Replaces lines from `line_number` to `end_line` (inclusive) with `new_content` (supports multiple lines via `\n`). |
| `insert_after` | `line_number`, `new_content` | Inserts `new_content` as one or more new lines after `line_number` (use `0` for top of file). |
| `delete` | `line_number`, `end_line` | Removes lines range `[line_number, end_line]` entirely. |

*Note: `end_line` defaults to `line_number` if null, performing a single-line operation.*

### Observation Space: `RtlDebuggerObservation`
Agents receive a rich observation after every edit, containing both raw technical feedback and normalized metrics:

| Field | Type | Description |
| :--- | :--- | :--- |
| `task_id` | `str` | Name of the selected task (e.g., `task1`). |
| `numbered_code` | `str` | Current `design_active.v` with line numbers (for referencing in edits). |
| `feedback` | `str` | Human-readable diagnostics: compiler logs or a cycle-by-cycle breakdown of test failures. |
| `pass_rate` | `float` | Continuous metric [0.0 - 1.0] representing the percentage of test cases passed. |
| `progress_ratio` | `float` | Percent of the test sequence completed before the first failure (measures sequential depth). |
| `compiled` | `bool` | Boolean flag indicating if the Verilog code is syntactically valid and compilation succeeded. |
| `lev_distance` | `int` | Line-based edit distance from the *previous* attempt, encouraging minimal, targeted fixes. |
| `score` | `float` | The final grading metric [0.0 - 1.0]. High scores reward both correctness and minimal steps. |

## 🎯 Tasks and Difficulty
The environment features curated hardware modules designed to test specific debugging capabilities:

| Task Tier | Name | Description | Grading Focus |
| :--- | :--- | :--- | :--- |
| **Easy** | Task 1 | Syntax & Compilation | Compilation OK, Step Count |
| **Medium** | Task 2 | Combinational Logic | Test Case Pass Rate, Step Count |
| **Hard** | Task 3 | Sequential Logic | Transition Accuracy, Test Case Pass Rate, Step Count |

---

## 📂 Project Structure

```text
.
├── tasks/         
│   ├── task1/    # Syntax & basic logic
│   ├── task2/      # Combinational logic
│   └── task3/    # Sequential logic
├── server/                  
├── models.py                
├── inference.py             
└── client.py                
```
