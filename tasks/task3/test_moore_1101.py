import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.utils import get_sim_time
import json

# Define the semantic meaning of states for the agent
STATE_MAP = {
    0: "S0: Seen nothing (Reset/Idle)",
    1: "S1: Seen '1'",
    2: "S2: Seen '11'",
    3: "S3: Seen '110'",
    4: "S4: Seen '1101' (Pattern Detected)"
}

def get_expected_fsm_step(current_state, bit):
    """
    Golden Model: Returns (next_state, output).

    FIX: In a Moore FSM the output is a function of present_state.
    After the clock edge, present_state == next_state, so the output
    that will be readable AFTER the edge is the output of next_state,
    NOT of current_state.  Only S4 asserts out=1.
    """
    if current_state == 0:
        ns = 1 if bit else 0
    elif current_state == 1:
        ns = 2 if bit else 0
    elif current_state == 2:
        ns = 2 if bit else 3   # '11' overlap
    elif current_state == 3:
        ns = 4 if bit else 0
    elif current_state == 4:
        ns = 2 if bit else 0
    else:
        ns = 0

    # Moore output belongs to the state we are NOW IN (next_state after edge)
    gold_out = 1 if ns == 4 else 0
    return (ns, gold_out)

@cocotb.test()
async def test_moore_1101(dut):
    """Test sequence detector with semantic error feedback for RL agent."""

    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut.reset.value = 1
    dut.inp.value = 0
    await RisingEdge(dut.clk)

    await Timer(1, units="ns")
    

    test_seq = [0, 1, 1, 0, 1, 1, 0, 1, 0, 1]  # slightly extended sequence to heavily test overlaps
    results = []
    passed = True
    first_error_cycle = None
    expected_state = 0  # Track golden state in parallel

    for i, bit in enumerate(test_seq):
        # Capture state BEFORE clock edge (signals are settled here)
        actual_current_state = int(dut.present_state.value)

        # Determine expected next state and output from Golden Model
        gold_next_state, gold_out = get_expected_fsm_step(expected_state, bit)

        dut.inp.value = bit
        await RisingEdge(dut.clk)

        # FIX: wait 1 ns (non-zero real time) so the nonblocking assignment
        # present_state <= next_state propagates past its delta cycle and the
        # combinatorial 'out' re-evaluates against the updated present_state.
        # Timer(0) / ReadOnly() stall inside the same delta and see stale values.
        await Timer(1, units="ns")

        actual_out = int(dut.out.value)
        actual_next_state = int(dut.present_state.value)

        # Check for mismatches
        out_ok   = (actual_out        == gold_out)
        state_ok = (actual_next_state == gold_next_state)

        if (not out_ok or not state_ok) and first_error_cycle is None:
            first_error_cycle = i
            passed = False

        results.append({
            "test_id": i,
            "input": bit,
            "actual_state": actual_current_state,
            "actual_state_meaning": STATE_MAP.get(actual_current_state, f"S{actual_current_state}"),
            "actual_output": actual_out,
            "expected_output": gold_out,
            "transition_to": actual_next_state,
            "transition_to_meaning": STATE_MAP.get(actual_next_state, f"S{actual_next_state}"),
            "expected_next_state": gold_next_state,
            "expected_next_state_meaning": STATE_MAP.get(gold_next_state, f"S{gold_next_state}"),
            "pass": out_ok and state_ok
        })

        # Update golden state for next cycle
        expected_state = gold_next_state

    # Construct smart summary for the Agent
    # error_msg = ""
    # if not passed:
    #     err = results[first_error_cycle]
    #     error_msg = (
    #         f"Divergence at Cycle {first_error_cycle}: "
    #         f"When in {err['actual_state_meaning']} and receiving Input {err['input']}, "
    #         f"the RTL moved to State {err['transition_to']}, but it should have moved to "
    #         f"State {err['expected_next_state']} ({STATE_MAP.get(err['expected_next_state'])})."
    #     )

    # Calculate new detailed grading metrics based on tracking arrays
    
    seq_correct = sum(1 for r in results if r["actual_output"] == r["expected_output"])
    trans_correct = sum(1 for r in results if r["transition_to"] == r["expected_next_state"])

    summary = {
        "passed": passed,
        "num_tests": len(test_seq),
        "num_passed": sum(1 for r in results if r["pass"]),
        "results": results,
        "sequence_correctness": seq_correct,
        "transition_correctness": trans_correct,
        "simulation_time": get_sim_time("ns")
    }

    with open("result.json", "w") as f:
        json.dump(summary, f, indent=2)

    assert passed  # f"FSM Error: {error_msg}"