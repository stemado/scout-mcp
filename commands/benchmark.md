---
description: Run Scout performance benchmarks and produce a versioned results file
argument-hint: "[version e.g. v0.3]"
allowed-tools:
  - "Read"
  - "Write"
  - "Glob"
  - "Bash"
  - "Task"
  - "AskUserQuestion"
  - "TodoWrite"
---

Run Scout's standardized performance benchmarks. Reads task definitions from
`benchmarks/tasks.yaml`, executes each task sequentially via subagents using
Scout MCP tools, and writes a versioned results file to `docs/benchmarks/`.

## Step 1: Read task spec

Read `benchmarks/tasks.yaml`. Parse:
- `version` — spec version string
- `runs_per_task` (default 3 if not present)
- `tasks[]` — each entry has: id, name, target_url, instruction,
  expected_output_contains, playwright_baseline_tokens

## Step 2: Detect model

Look in the injected system prompt context for a phrase like
"You are powered by the model named..." or "The model named..." and extract
the model name (e.g., "Claude Sonnet 4.6").

If not detectable from context, use AskUserQuestion:
- Question: "Which model is this session running on?"
- Options: "Claude Sonnet 4.6", "Claude Opus 4.6", "Claude Haiku 4.5", "Other"

## Step 3: Determine version

1. Glob `docs/plans/benchmarks/benchmark-results-v*.md` to find existing results files
2. Parse the version numbers (e.g., `v0.1`, `v0.2`) from the filenames
3. Increment the highest minor version by 0.1 (v0.2 -> v0.3)
   Version numbers use a single decimal digit for the minor part (v0.1 through v0.9).
   At v0.9, increment to v1.0. Always format the version as `vMAJOR.MINOR` with exactly
   one decimal digit (e.g., `v0.3`, `v1.0`, never `v0.10`).
4. If the user provided a version argument to the command, use that instead

If no existing results files are found, default to `v0.1`.

## Step 4: Confirm before running

Use AskUserQuestion with a single confirmation:
- Question: "About to run [N tasks] × [runs_per_task runs] on [model]. Results -> benchmark-results-[version].md. Proceed?"
- Options: "Proceed", "Cancel"

If "Cancel", stop immediately with: "Benchmark cancelled."

## Step 5: Create progress checklist

Use TodoWrite to create a todo item for each individual run, e.g.:
- "T1 Run 1 — Fact Lookup (Wikipedia)" (pending)
- "T1 Run 2 — Fact Lookup (Wikipedia)" (pending)
- "T1 Run 3 — Fact Lookup (Wikipedia)" (pending)
- "T2 Run 1 — Form Fill (httpbin)" (pending)
- etc.

## Step 6: Execute all runs sequentially

**IMPORTANT: Runs are sequential, not parallel.** Sequential execution preserves
the cold-start / cache-warm measurement pattern that matches the v0.1 and v0.2
benchmark methodology. Do not dispatch multiple subagents simultaneously.

For each task in `tasks[]`, then for each run from 1 to `runs_per_task`:

Mark the current run's todo as in_progress, then dispatch a Task subagent with
this exact prompt structure (substitute values from tasks.yaml):

---
SUBAGENT PROMPT:

You are running Scout benchmark [TASK_ID] Run [RUN_NUMBER]: [TASK_NAME]

Target URL: [target_url]

TASK INSTRUCTION (canonical text — reproduce exactly, do not paraphrase):
[instruction]

METHODOLOGY — follow in exact order:

1. Call `launch_session` with the target URL (use headless=true).

2. Use Scout MCP tools to complete the task as efficiently as possible.

3. Apply these known workarounds UPFRONT — do not attempt alternatives first:
   - For `input[type="time"]` fields: set value via `execute_javascript`
     (`el.value = "HH:MM"; el.dispatchEvent(new Event("input", {bubbles:true}));
     el.dispatchEvent(new Event("change", {bubbles:true}));`). Never use CDP
     keystroke injection for time inputs.
   - For httpbin form submission: use `execute_javascript` with
     `document.querySelector("form").submit()`. The submit button click does
     not trigger navigation via CDP.

4. Before calling `close_session`, call `get_session_history`. Count the total
   number of Scout MCP tool calls in the returned history. Count every call:
   launch_session, scout_page_tool, find_elements, execute_action_tool,
   execute_javascript, get_session_history itself, etc.

5. Call `close_session`. Record the exact value of `session_duration_seconds`
   from the response JSON — this is what goes into the `wall_clock_seconds` field
   of your JSON return below.

6. Check: does your extracted output contain this exact substring?
   [expected_output_contains]
   Set success=true if yes, false if no.

Return ONLY a raw JSON object — no markdown fences, no explanation, no preamble:
{"wall_clock_seconds":<number>,"tool_calls":<integer>,"success":<boolean>,"retries":<integer>,"extracted_output":"<string>"}

The "retries" field is the number of times you had to retry a step that failed
on the first attempt (e.g., a click that needed a workaround, a JS execution
that needed correction).
---

After the subagent responds:
- Parse the JSON from the response (strip any accidental markdown fences)
- If parsing fails or the response is not valid JSON, store:
  `{"wall_clock_seconds": null, "tool_calls": null, "success": false, "retries": 0, "extracted_output": "ERROR: could not parse subagent response"}`
- Mark the run's todo item as completed
- Store the result in memory for Step 7

## Step 7: Compute means

For each task, from the array of run results:
- `mean_wall_clock`: average of non-null wall_clock_seconds values, rounded to 1 decimal
- `mean_tool_calls`: average of non-null tool_calls values, rounded to 1 decimal
- `success_count`: count of runs where success=true (format as "N/runs_per_task")
- `total_retries`: sum of retries across all runs

If any run has null values (subagent error), note how many were skipped in the
methodology section of the results file.

## Step 8: Compute efficiency ratios

For each task, retrieve the historical steady-state tool response token counts
from the v0.1 results file (if it exists at `docs/plans/benchmarks/benchmark-results-v0.1.md`).
These are the authoritative model-independent baseline figures:
- T1 steady-state: ~1,264 tokens (Run 2/3 mean from v0.1)
- T2 steady-state: ~3,799 tokens (Run 2/3 mean from v0.1)

Efficiency ratio = playwright_baseline_tokens / Scout_steady_state_tokens.

These ratios are NOT re-measured in this run. They are historical references.

## Step 9: Load prior version for comparison

If a prior results file exists (the version before the current run), read it and
extract the wall-clock means for each task. If models differ between versions,
note that in the comparison section.

## Step 10: Write results file

Write `docs/plans/benchmarks/benchmark-results-[version].md` using this template.
Fill in all bracketed values from the data collected above.

**Note on run count:** The template below shows 3 run columns. If `runs_per_task`
differs from 3, adjust the table headers and data columns to match the actual
run count — add or remove "Run N" columns as needed. The Mean column is always last.

```
# Scout Benchmark Results — [VERSION]

**Date:** [YYYY-MM-DD — today's date]
**Model:** [model name]
**Method:** Sequential runs; wall-clock from `session_duration_seconds` (close_session
            response); tool calls from `get_session_history`
**Task spec:** benchmarks/tasks.yaml v[spec version]
**Runs per task:** [runs_per_task]

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

## Task [ID]: [Name]

**Target:** `[target_url]`
**Instruction:** [If single-line: write inline. If multi-line (like T2's bulleted list),
write as a markdown blockquote — prefix each line with `> `. Example:
> Navigate to httpbin.org/forms/post. Fill in the form with the following values:
> - Customer name: "Scout Benchmark"
> ...]

```
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   [r1_wall]   [r2_wall]   [r3_wall]   [mean_wall]
Scout tool calls:    [r1_tools]  [r2_tools]  [r3_tools]  [mean_tools]
Success:            [r1_ok]     [r2_ok]     [r3_ok]     [success_count]
Retries:            [r1_retry]  [r2_retry]  [r3_retry]  [total_retries]
```

**Extracted output (Run 1):**
> [run1_extracted_output]

**Efficiency ratio (historical reference from v0.1 steady-state):**
```
Playwright MCP baseline:  ~[playwright_baseline_tokens] tokens (1 tool call, full page snapshot)
Scout steady-state:           ~[Scout_steady_state] tokens ([mean_tools] tool calls, targeted extraction)
Efficiency ratio:            [ratio]x fewer tokens than Playwright
```
*Efficiency ratio uses v0.1 steady-state data. Not re-measured in this run.*

[Repeat Task section for each task]

---

## Summary Table

```
SCOUT BENCHMARK RESULTS — [VERSION]
═══════════════════════════════════
Model: [model]

Task [ID]: [Name]
──────────────────────────────────
                    Run 1       Run 2       Run 3       Mean
Wall-clock (sec):   [r1]        [r2]        [r3]        [mean]
Tool calls:         [r1]        [r2]        [r3]        [mean]
Success:            [r1]        [r2]        [r3]        [N/runs]
Retries:            [r1]        [r2]        [r3]        [total]

Playwright MCP baseline: ~[playwright_baseline_tokens] tokens ([N] tool call[s])
Scout vs. baseline:       [ratio]x more efficient (historical reference from v0.1)

[Repeat for each task]
```

---

## Comparison with [PRIOR_VERSION]

```
                            Task 1 ([Name])     Task 2 ([Name])
────────────────────────────────────────────────────────────────
[PRIOR_VERSION] wall-clock: [prior_t1]s          [prior_t2]s
[CURRENT_VERSION] wall-clock:[curr_t1]s           [curr_t2]s
Delta:                      [delta_t1]s ([%])     [delta_t2]s ([%])
────────────────────────────────────────────────────────────────
[PRIOR_VERSION] model:      [prior_model]
[CURRENT_VERSION] model:    [curr_model]
```

[If models differ: "Wall-clock delta reflects both model and implementation changes.
Efficiency ratios are model-independent and unchanged."]
[If no prior version: "First benchmark run — no prior version to compare."]

```

## Step 11: Confirm completion

Tell the user:
- The full path of the results file written
- One-line summary per task: "[Task Name]: mean [X]s wall-clock, [N/runs] success"
- Any runs that returned errors or null values
- Suggest: "Run `git diff docs/plans/benchmarks/` to review before committing."
