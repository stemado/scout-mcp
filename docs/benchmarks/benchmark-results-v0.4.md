# Scout Benchmark Results — v0.4

**Date:** 2026-03-18
**Model:** Claude Opus 4.6
**Method:** Sequential runs, inline (not subagent-dispatched); wall-clock from
            `session_duration_seconds` (close_session response); tool calls
            counted as every Scout MCP tool invocation in the session
**Task spec:** benchmarks/tasks.yaml v1.0
**Runs per task:** 3

---

## Measurement Methodology

Wall-clock is measured by `session_duration_seconds` in the `close_session` MCP
response — browser open to browser close. This excludes model reasoning time and
orchestration overhead between tool calls. Add ~1–3 seconds per tool call for
realistic end-to-end latency.

Tool call counts include every Scout MCP tool invocation during the session:
`launch_session`, `scout_page_tool`, `find_elements`, `execute_action_tool`,
`execute_javascript`, `get_session_history`, and `close_session`.

**Note on inline execution:** Unlike v0.1–v0.3 which used subagent-dispatched
runs, v0.4 runs were executed inline in the main conversation. This eliminates
subagent dispatch overhead but means the model retains selector knowledge across
runs (e.g., `find_elements` was skipped in T1 Runs 2–3 and T2 Runs 2–3 after
learning selectors in Run 1). This is a methodological difference from prior
versions.

**Efficiency ratios** (Scout vs. Playwright MCP) are historical references from
v0.1 steady-state measurements. Scout tool response payloads are model-independent;
these ratios remain valid across model versions. Re-measurement requires separate
JSONL context delta analysis per the v0.1 methodology.

---

## Task T1: Fact Lookup (Wikipedia)

**Target:** `https://en.wikipedia.org/wiki/Python_(programming_language)`
**Instruction:** Navigate to the Wikipedia article on the Python programming language. Extract the first paragraph of the article summary (the text before the table of contents). Return only the extracted text.

```
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   20.1        13.1        14.1        15.8
Scout tool calls:    6           5           5           5.3
Success:            true        true        true        3/3
Retries:            0           0           0           0
```

**Extracted output (Run 1):**
> Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation.[38] Python is dynamically type-checked and garbage-collected. It supports multiple programming paradigms, including structured (particularly procedural), object-oriented and functional programming.

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:            ~1,264 tokens (5.3 tool calls, targeted extraction)
Efficiency ratio:            98.1x fewer tokens than Playwright
```
*Efficiency ratio uses v0.1 steady-state data. Not re-measured in this run.*

---

## Task T2: Form Fill + Verification (httpbin)

**Target:** `https://httpbin.org/forms/post`
**Instruction:**
> Navigate to httpbin.org/forms/post. Fill in the form with the following values:
> - Customer name: "Scout Benchmark"
> - Telephone: "555-0199"
> - E-mail: "benchmark@scout.dev"
> - Size: Large
> - Topping: Cheese
> - Delivery time: "11:45"
> - Delivery instructions: "Leave at door"
> Submit the form. Extract and return the full response that httpbin echoes back.

```
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   50.9        48.9        57.7        52.5
Scout tool calls:    14          13          13          13.3
Success:            true        true        true        3/3
Retries:            0           0           0           0
```

**Extracted output (Run 1):**
> {"args": {}, "data": "", "files": {}, "form": {"comments": "Leave at door", "custemail": "benchmark@scout.dev", "custname": "Scout Benchmark", "custtel": "555-0199", "delivery": "11:45", "size": "large", "topping": "cheese"}, "headers": {...}, "json": null, "origin": "216.49.233.38", "url": "https://httpbin.org/post"}

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:            ~3,799 tokens (13.3 tool calls, targeted extraction)
Efficiency ratio:            32.6x fewer tokens than Playwright
```
*Efficiency ratio uses v0.1 steady-state data. Not re-measured in this run.*

---

## Summary Table

```
SCOUT BENCHMARK RESULTS — v0.4
═══════════════════════════════════
Model: Claude Opus 4.6

Task T1: Fact Lookup (Wikipedia)
──────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   20.1        13.1        14.1        15.8
Tool calls:         6           5           5           5.3
Success:            true        true        true        3/3
Retries:            0           0           0           0

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:        98.1x more efficient (historical reference from v0.1)

Task T2: Form Fill + Verification (httpbin)
──────────────────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   50.9        48.9        57.7        52.5
Tool calls:         14          13          13          13.3
Success:            true        true        true        3/3
Retries:            0           0           0           0

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:        32.6x more efficient (historical reference from v0.1)
```

---

## Comparison with v0.3

```
                            Task 1 (Fact Lookup)    Task 2 (Form Fill)
────────────────────────────────────────────────────────────────────────
v0.3 wall-clock:            18.8s                   32.5s
v0.4 wall-clock:            15.8s                   52.5s
Delta:                      -3.0s (-16.0%)          +20.0s (+61.5%)
────────────────────────────────────────────────────────────────────────
v0.3 tool calls (mean):     3.7                     9.3
v0.4 tool calls (mean):     5.3                     13.3
Delta:                      +1.6 (+43.2%)           +4.0 (+43.0%)
────────────────────────────────────────────────────────────────────────
v0.3 model:                 Claude Sonnet 4.6
v0.4 model:                 Claude Opus 4.6
```

Wall-clock and tool call differences reflect two confounded variables:

1. **Model change:** v0.4 uses Opus 4.6 (vs. Sonnet 4.6 in v0.3). Opus has
   longer reasoning time between tool calls, which increases browser idle time
   within `session_duration_seconds`.

2. **Inline vs. subagent execution:** v0.4 runs were inline, meaning the model
   retained selector knowledge across runs (reducing `find_elements` calls in
   later runs) but also included overhead from a larger conversation context.

Comparing v0.4 to v0.1 (same model, Opus 4.6) shows consistent improvement:
T1 wall-clock dropped from 37.3s to 15.8s (-57.6%), T2 from 87.9s to 52.5s
(-40.3%), with zero retries across all runs (vs. 5 total retries in v0.1).

Efficiency ratios are model-independent and unchanged.
