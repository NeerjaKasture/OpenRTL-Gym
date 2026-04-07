---
title: RTL Debugger Environment
emoji: 🛠️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
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
The environment runs in a Docker container to ensure all hardware tools (`iverilog`, `make`, `python-cocotb`) are correctly installed.

```bash
# Build the image locally
docker build -t rtl_debugger-env:latest .
```

### 2. Run the Server
```bash
# Start the environment server on port 8000
docker run -p 8000:8000 --rm rtl_debugger-env:latest
```
Access the web UI at [http://localhost:8000/web](http://localhost:8000/web).

### 3. Run the Inference Agent
We provide a reference inference script that uses LLM to play the environment:

```bash
# Install dependencies
uv sync

# Run the agent 
uv run python inference.py
```

## Environment Details

### Action Model (`RtlDebuggerAction`)
Agents submit their corrected Verilog module:
- `fixed_code` (str): The full Verilog module source.

### Observation Model (`RtlDebuggerObservation`)
The environment returns detailed hardware-centric feedback:
- `design_code` (str): The initial (buggy) design for reference.
- `feedback` (str): Raw output from `iverilog` errors or `cocotb` testbench logs.
- `compiled` (bool): Whether the code successfully compiled.
- `passed_tests` (bool): Whether all functional testcases passed.
- `pass_rate` (float): Ratio of passed tests [0.0 - 1.0].
- `levenshtein_distance` (int): Number of lines modified compared to the previous step.

---
*Built with [OpenEnv](https://github.com/meta-pytorch/openenv-core)*.
