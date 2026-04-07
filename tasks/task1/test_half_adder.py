import cocotb
from cocotb.triggers import Timer
from cocotb.utils import get_sim_time
import json


def get_expected_half_adder(a, b):
    """Golden Model: Returns expected sum and carry."""
    return (a ^ b, a & b)


@cocotb.test()
async def test_half_adder(dut):
    """Test Half Adder with semantic error feedback for RL agent."""

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

        actual_sum = int(dut.sum.value)
        actual_carry = int(dut.carry.value)

        gold_sum, gold_carry = get_expected_half_adder(a_val, b_val)

        ok = (actual_sum == gold_sum) and (actual_carry == gold_carry)

        if not ok and first_error_cycle is None:
            first_error_cycle = i
            passed = False

        results.append({
            "test_id": i,
            "input": {"a": a_val, "b": b_val},
            "expected_output": {
                "sum": gold_sum,
                "carry": gold_carry
            },
            "actual_output": {
                "sum": actual_sum,
                "carry": actual_carry
            },
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