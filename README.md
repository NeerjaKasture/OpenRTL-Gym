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

The **RTL Debugger** is a Reinforcement Learning environment designed for automated hardware design fixing. It enables LLM-based agents to iteratively debug Verilog code.

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

### Action Model (`RtlDebuggerAction`)
Agents submit their corrected Verilog module:
- `fixed_code` (str): The full Verilog module source.

### Observation: `RtlDebuggerObservation`
| Field | Type | Description |
| :--- | :--- | :--- |
| `task_id` | `str` | Name of the selected task (e.g., `task0`). |
| `feedback` | `str` | Combined compiler errors and testbench results. |
| `pass_rate` | `float` | Percent of testcases passed [0.0 - 1.0]. |
| `progress_ratio` | `float` | Percent of simulation sequence completed before the first failure. |
| `compiled` | `bool` | Whether the Verilog code is syntactically valid. |
| `lev_distance` | `int` | Number of modified lines compared to the previous attempt. |
| `score` | `float` | Final normalized grader score [0.0 - 1.0]. |

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
