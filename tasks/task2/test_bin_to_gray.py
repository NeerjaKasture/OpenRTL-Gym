import cocotb
from cocotb.triggers import Timer
from cocotb.utils import get_sim_time
import json


def get_expected_gray(binary_val, N):
    """Golden Model: Convert binary to Gray code."""
    gray = 0
    gray |= (binary_val >> (N - 1)) << (N - 1)  # MSB same

    for i in range(N - 1):
        bit1 = (binary_val >> (i + 1)) & 1
        bit0 = (binary_val >> i) & 1
        gray |= (bit1 ^ bit0) << i

    return gray


@cocotb.test()
async def test_bin_to_gray(dut):
    """Test binary to gray converter with semantic error feedback for RL agent."""

    N = len(dut.binary)

    # 10–15 carefully chosen test cases
    max_val = (1 << N) - 1
    test_cases = [
        0,
        1,
        2,
        3,
        max_val >> 1,
        max_val,
        max_val - 1,
        5,
        10,
        15,
        (1 << (N-1)),   # MSB only
        (1 << (N-1)) - 1
    ]

    results = []
    passed = True
    first_error_cycle = None

    for i, binary_val in enumerate(test_cases):
        dut.binary.value = binary_val

        await Timer(1, units="ns")

        actual_out = int(dut.gray.value)
        gold_out = get_expected_gray(binary_val, N)

        ok = (actual_out == gold_out)

        if not ok and first_error_cycle is None:
            first_error_cycle = i
            passed = False

        results.append({
            "test_id": i,
            "input": {"binary": binary_val},
            "expected_output": gold_out,
            "actual_output": actual_out,
            "pass": ok
        })

    summary = {
        "passed": passed,
        "num_tests": len(test_cases),
        "num_passed": sum(r["pass"] for r in results),
        "simulation_time": get_sim_time("ns"),
        "results": results
    }

    with open("result.json", "w") as f:
        json.dump(summary, f, indent=2)

    assert passed, "Some test cases failed"