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
- **Simulation Engines**: Supports both **Icarus Verilog** and **Verilator** for fast, cycle-accurate simulation.
- **Feedback Loop**: For every submitted design, the environment provides a detailed diagnostic report, including compilation errors, failed test cycles, and FSM transition mismatches.
- **Iterative Debugging**: Agents can build upon their previous attempts, utilizing line-based edit distance (Levenshtein) and pass-rate progress to guide their refinement.

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
The action space is **unstructured text** representing the revised hardware design:
- `fixed_code` (str): The full Verilog module source intended to replace the current `design_active.v`.

### Observation Space: `RtlDebuggerObservation`
Agents receive a rich observation after every edit, containing both raw technical feedback and normalized metrics:

| Field | Type | Description |
| :--- | :--- | :--- |
| `task_id` | `str` | Name of the selected task (e.g., `task1`). |
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
| **Medium** | Task 2 | Combinational Logic | Test Case Pass Rate |
| **Hard** | Task 3 | Sequential Logic | Transition Accuracy, Reset Logic |

---

## 📂 Project Structure

```text
.
├── tasks/                   # Curated hardware debugging tasks
│   ├── task0_half_adder/    # Syntax & basic logic
│   ├── task1_xor_gate/      # Combinational logic
│   └── task2_moore_1101/    # Sequential logic
├── server/                  
├── models.py                
├── inference.py             
└── client.py                
```
