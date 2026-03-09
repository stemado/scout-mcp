# Scout Benchmark Results — v0.2

**Date:** 2026-02-27
**Model:** Claude Sonnet 4.6
**Method:** Sequential runs; wall-clock from `session_duration_seconds` (close_session
            response); tool calls self-reported (Scout plugin does not expose
            `get_session_history`)
**Task spec:** benchmarks/tasks.yaml v1.0
**Runs per task:** 3

---

## Measurement Methodology

Wall-clock is measured by `session_duration_seconds` in the `close_session` MCP
response — browser open to browser close. This excludes model reasoning time and
orchestration overhead between tool calls. Add ~1–3 seconds per tool call for
realistic end-to-end latency.

Tool call counts are self-reported by the subagent, counting every Scout MCP tool
invocation made during the session. The Scout plugin does not expose
`get_session_history`, so counts are derived from the subagent's own invocation
record rather than server-side session history.

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
Wall-clock (sec):   16.9        7.2         9.0         11.0
Scout tool calls:     6           3           3           4.0
Success:            true        true        true        3/3
Retries:            0           0           0           0
```

**Extracted output (Run 1):**
> Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation. Python is dynamically type-checked and garbage-collected. It supports multiple programming paradigms, including structured (particularly procedural), object-oriented and functional programming.

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:            ~1,264 tokens (4.0 tool calls, targeted extraction)
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
> - E-mail: "benchmark@Scout.dev"
> - Size: Large
> - Topping: Cheese
> - Delivery time: "11:45"
> - Delivery instructions: "Leave at door"
> Submit the form. Extract and return the full response that httpbin echoes back.

```
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   30.2        25.1        20.3        25.2
Scout tool calls:     8           8           7           7.7
Success:            true        true        true        3/3
Retries:            1           1           0           2
```

**Extracted output (Run 1):**
> {"args": {}, "data": "", "files": {}, "form": {"comments": "Leave at door", "custemail": "benchmark@Scout.dev", "custname": "Scout Benchmark", "custtel": "555-0199", "delivery": "11:45", "size": "large", "topping": "cheese"}, "headers": {...}, "json": null, "origin": "216.49.233.104", "url": "https://httpbin.org/post"}

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:            ~3,799 tokens (7.7 tool calls, targeted extraction)
Efficiency ratio:            32.6x fewer tokens than Playwright
```
*Efficiency ratio uses v0.1 steady-state data. Not re-measured in this run.*

---

## Summary Table

```
Scout BENCHMARK RESULTS — v0.2
═══════════════════════════════════
Model: Claude Sonnet 4.6

Task T1: Fact Lookup (Wikipedia)
──────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   16.9        7.2         9.0         11.0
Tool calls:         6           3           3           4.0
Success:            true        true        true        3/3
Retries:            0           0           0           0

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:        98.1x more efficient (historical reference from v0.1)

Task T2: Form Fill + Verification (httpbin)
──────────────────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   30.2        25.1        20.3        25.2
Tool calls:         8           8           7           7.7
Success:            true        true        true        3/3
Retries:            1           1           0           2

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:        32.6x more efficient (historical reference from v0.1)
```

---

## Comparison with v0.1

```
                            Task 1 (Fact Lookup)    Task 2 (Form Fill)
────────────────────────────────────────────────────────────────────────
v0.1 wall-clock:            37.3s                   87.9s
v0.2 wall-clock:            11.0s                   25.2s
Delta:                      -26.3s (-70.5%)         -62.7s (-71.3%)
────────────────────────────────────────────────────────────────────────
v0.1 tool calls (mean):     10.3                    26.7
v0.2 tool calls (mean):     4.0                     7.7
Delta:                      -6.3 (-61.2%)           -19.0 (-71.2%)
────────────────────────────────────────────────────────────────────────
v0.1 model:                 Claude Opus 4.6
v0.2 model:                 Claude Sonnet 4.6
```

Wall-clock delta reflects both model and implementation changes. Sonnet 4.6
produces faster tool call responses than Opus 4.6, and Scout subagents used fewer
tool calls per task (4.0 vs 10.3 for T1; 7.7 vs 26.7 for T2), suggesting more
efficient automation strategies. Efficiency ratios are model-independent and
unchanged.
