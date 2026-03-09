# Scout Benchmark Results — v0.1

**Date:** 2026-02-27
**Model:** Claude Opus 4.6
**Method:** Sequential runs; wall-clock from `session_duration_seconds` (close_session
            response); tool calls from `get_session_history`
**Task spec:** benchmarks/tasks.yaml v1.0
**Runs per task:** 3

---

## Measurement Methodology

Wall-clock is measured by `session_duration_seconds` in the `close_session` MCP
response — browser open to browser close. This excludes model reasoning time and
orchestration overhead between tool calls. Add ~1–3 seconds per tool call for
realistic end-to-end latency.

Tool call counts are derived from `get_session_history` before session close,
counting every Scout MCP tool invocation in the session record.

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
Wall-clock (sec):   32.8        49.4        29.7        37.3
Scout tool calls:    9           13          9           10.3
Success:            true        true        true        3/3
Retries:            0           0           4           4
```

**Extracted output (Run 1):**
> Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation. Python is dynamically type-checked and garbage-collected. It supports multiple programming paradigms, including structured (particularly procedural), object-oriented and functional programming.

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:           ~1,264 tokens (10.3 tool calls, targeted extraction)
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
Wall-clock (sec):   56.3        69.3        138.2       87.9
Scout tool calls:    20          25          35          26.7
Success:            true        true        true        3/3
Retries:            0           0           1           1
```

**Extracted output (Run 1):**
> {"args": {}, "data": "", "files": {}, "form": {"comments": "Leave at door", "custemail": "benchmark@scout.dev", "custname": "Scout Benchmark", "custtel": "555-0199", "delivery": "11:45", "size": "large", "topping": "cheese"}, "headers": {...}, "json": null, "origin": "216.49.233.104", "url": "https://httpbin.org/post"}

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~124,000 tokens (1 tool call, full page snapshot)
Scout steady-state:           ~3,799 tokens (26.7 tool calls, targeted extraction)
Efficiency ratio:            32.6x fewer tokens than Playwright
```
*Efficiency ratio uses v0.1 steady-state data. Not re-measured in this run.*

---

## Summary Table

```
SCOUT BENCHMARK RESULTS — v0.1
═══════════════════════════════════
Model: Claude Opus 4.6

Task T1: Fact Lookup (Wikipedia)
──────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   32.8        49.4        29.7        37.3
Tool calls:         9           13          9           10.3
Success:            true        true        true        3/3
Retries:            0           0           4           4

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:       98.1x more efficient (historical reference from v0.1)

Task T2: Form Fill + Verification (httpbin)
──────────────────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   56.3        69.3        138.2       87.9
Tool calls:         20          25          35          26.7
Success:            true        true        true        3/3
Retries:            0           0           1           1

Playwright MCP baseline: ~124,000 tokens (1 tool call)
Scout vs. baseline:       32.6x more efficient (historical reference from v0.1)
```

---

## Comparison with Prior Versions

First benchmark run — no prior version to compare.
