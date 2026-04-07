import cocotb
from cocotb.triggers import Timer, ReadOnly
from cocotb.utils import get_sim_time
import json


def get_expected_xor(a, b):
    """Golden Model: Returns expected XOR output."""
    return a ^ b


@cocotb.test()
async def test_xor_gate_simple(dut):
    """Test XOR gate with semantic error feedback for RL agent."""

    test_cases = [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]

    results = []
    passed = True
    first_error_cycle = None

    for i, (a_val, b_val) in enumerate(test_cases):
        dut.a.value = a_val
        dut.b.value = b_val

        await Timer(1, units="ns")

        actual_out = int(dut.y.value)
        gold_out = get_expected_xor(a_val, b_val)

        ok = (actual_out == gold_out)

        if not ok and first_error_cycle is None:
            first_error_cycle = i
            passed = False

        results.append({
            "test_id": i,
            "input": {"a": a_val, "b": b_val},
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