# Scout Scenario Catalog

Real-world demonstrations of Claude Code + Scout MCP working together. Each scenario
uses a real website — no sandboxed test environments. Paste the prompt into Claude Code
and watch it work.

---

## Category 1: "Claude Code Just Does This Now"

These scenarios demonstrate Scout as a native extension of Claude Code — tasks where
Claude reaches for the browser naturally, like reading a file or running a command.

### S1: Check the Docs

**Site:** https://react.dev/reference/react/useEffect
**Prompt:**
> Check the React docs — what's the full type signature for useEffect? Include all
> overloads and the cleanup function return type.

**What it demonstrates:** Claude Code verifying documentation instead of guessing from
training data. The React docs use client-side rendering, tabbed code blocks, and
expandable sections — Scout handles all of these via the scout/find/act cycle.

**Success criteria:** Returns the accurate, current useEffect signature with all parameters.

---

### S2: Is This Package Maintained?

**Site:** https://github.com/lodash/lodash (or any public repo)
**Prompt:**
> Check if lodash is still actively maintained. Look at the GitHub repo — last commit
> date, open issues count, and whether there's been a release in the last year.

**What it demonstrates:** Claude Code doing due diligence on a dependency before
recommending it. Navigates GitHub, extracts structured data from a complex UI.

**Success criteria:** Returns last commit date, open issue count, latest release date — all
verifiable against the live repo.

---

### S3: Look Up This Error

**Site:** Stack Overflow / GitHub Issues (varies by error)
**Prompt:**
> I'm getting "ECONNREFUSED 127.0.0.1:5432" when running my tests. Search for this
> error and tell me the most common cause and fix.

**What it demonstrates:** Claude Code researching solutions on the web instead of
relying purely on training data. Searches, follows links, synthesizes across multiple
sources.

**Success criteria:** Returns the actual fix (PostgreSQL not running / wrong port) with
source attribution.

---

### S4: Verify My Deploy

**Site:** Any user-provided URL
**Prompt:**
> I just deployed to https://example.com — can you check if it's up and tell me
> what the page title and main heading say?

**What it demonstrates:** Claude Code verifying a deployment works by actually visiting
it. A task that currently requires the user to open a browser tab — Scout makes it
one sentence.

**Success criteria:** Reports page title, heading, and load status accurately.

---

### S5: What's the Current Pricing?

**Site:** https://openai.com/api/pricing/ (or any pricing page)
**Prompt:**
> What's the current per-token pricing for GPT-4o on the OpenAI API? Check their
> pricing page — don't guess from training data.

**What it demonstrates:** Retrieving time-sensitive information that changes frequently.
Training data is unreliable for pricing — Scout gets the live answer.

**Success criteria:** Returns accurate, current pricing that matches the live page.

---

## Category 2: "And Everything Else Too"

Standard browser automation scenarios that prove Scout handles the full range of
web interactions.

### S6: Fill a Complex Form

**Site:** https://httpbin.org/forms/post
**Prompt:**
> Go to httpbin.org/forms/post and fill in the form: Customer name "Scout Demo",
> Telephone "555-0199", Email "demo@scout.dev", Size Large, Topping Cheese,
> Delivery time "11:45", Instructions "Ring the bell". Submit and show me the response.

**What it demonstrates:** Form filling with multiple input types (text, radio, select,
textarea). The httpbin echo confirms every field was set correctly.

**Success criteria:** httpbin response shows all form values exactly as specified.

---

### S7: Download and Convert a File

**Site:** https://catalog.data.gov/dataset
**Prompt:**
> Go to data.gov's dataset catalog, search for "climate normals", find a dataset
> with a downloadable CSV, download it, and put it in my project's data/ directory.

**What it demonstrates:** File download from a real government data portal — navigating
search results, finding download links, and delivering files to the local filesystem.

**Success criteria:** CSV file appears in the specified directory with valid tabular content.

---

### S8: Capture API Traffic

**Site:** https://wttr.in/London
**Prompt:**
> Open wttr.in/London and capture the network requests it makes when loading. I want
> to see what API endpoints it calls and what the response structure looks like.

**What it demonstrates:** Network monitoring via CDP. Claude Code discovers the
underlying API of a web application without documentation. wttr.in is a public weather
service with a clean API that makes this observable.

**Success criteria:** Returns captured URLs, methods, and response body structure.

---

### S9: Log In to a Portal

**Site:** Wikipedia (account creation/login) or similar
**Prompt:**
> Log into Wikipedia with the credentials in my .env file and check my watchlist.

**What it demonstrates:** Authenticated browsing with secret isolation. The password
never appears in the conversation. The `fill_secret` tool types it server-side.

**Success criteria:** Successfully logged in, watchlist data returned, no credentials
visible in the session.

---

### S10: Record What You're Doing

**Site:** Any scenario above
**Prompt:**
> Record a GIF of yourself checking the React docs for the useEffect API.

**What it demonstrates:** Self-documenting automation. Scout records its own browser
session as a GIF that can be embedded in a README or shared with a team.

**Success criteria:** GIF file produced showing the browser navigating and extracting data.

---

## Recording Demos

Each scenario should be recorded as a GIF using Scout's `record_video` tool with
`output_format="gif"`. The resulting GIFs can be embedded directly in the README.

**Recording workflow:**
1. Start recording: `record_video(session_id, "start")`
2. Execute the scenario
3. Stop recording: `record_video(session_id, "stop", output_format="gif")`
4. GIF saved to `~/.scout/downloads/recording_YYYYMMDD_HHMMSS.gif`

**Recommended settings for README GIFs:**
- Resolution: 800px wide (auto-height)
- FPS: 10 (good balance of smoothness and file size)
- Duration: 10-20 seconds per scenario
- Target file size: 2-5 MB
