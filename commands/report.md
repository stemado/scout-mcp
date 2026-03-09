---
description: Report a bug, request a feature, or flag UX friction as a GitHub issue
argument-hint: "[bug|feature|friction]"
allowed-tools: []
---

Help the user file a GitHub issue against the Scout repository. Follow these steps precisely.

## Step 1: Verify gh CLI

Run `gh auth status` via bash. If it fails, tell the user:
- "The `gh` CLI is required but not authenticated. Run `gh auth login` first."
- Stop here. Do not proceed.

## Step 2: Determine category

Check if the user provided an argument:
- `bug` → Bug
- `feature` → Feature Request
- `friction` → UX Friction
- No argument or unrecognized → Ask the user via AskUserQuestion with these options:
  - **Bug** — "Something is broken or not working as expected"
  - **Feature Request** — "I want Scout to do something new"
  - **UX Friction** — "It works, but the experience is awkward or confusing"

## Step 3: Collect description

Ask the user: "Describe the issue in a few sentences. What happened (or what do you want)?"

If the response is empty or under 10 words, ask ONE follow-up:
- Bug: "Can you describe what you were doing and what went wrong?"
- Feature: "What are you trying to accomplish that Scout can't do today?"
- Friction: "What felt awkward and what would have been better?"

Do NOT ask more than one follow-up. Respect the user's time.

## Step 4: Collect environment diagnostics

Run these bash commands to gather diagnostics (run all in parallel where possible):

```bash
# OS info
uname -s -r -m 2>/dev/null || python -c "import platform; print(platform.platform())"

# Python version
python --version 2>/dev/null || python3 --version

# Scout version
python -c "import scout; print(scout.__version__)" 2>/dev/null || echo "unknown"

# botasaurus-driver version
python -c "import botasaurus_driver; print(botasaurus_driver.__version__)" 2>/dev/null || pip show botasaurus-driver 2>/dev/null | grep Version || echo "unknown"
```

Also note whether a browser session is currently active (check if any scout session tools are in use). If active, note the current URL from the most recent scout or navigation.

## Step 5: Check for duplicates

Extract 2-3 key terms from the user's description. Run:

```bash
gh issue list --repo stemado/scout --search "<key terms>" --state open --limit 5
```

If matches are found, show them to the user:
- "I found these open issues that might be related:"
- List each with number, title, and URL
- Ask: "Does one of these cover your issue, or should we file a new one?"

If the user says an existing issue covers it, stop here.

## Step 6: Assemble the draft issue

### Title
Create a concise title (under 70 characters), prefixed with the category in brackets:
- `[Bug] <description>`
- `[Feature] <description>`
- `[UX] <description>`

### Body

**For Bug:**
```
## Description
<user's description>

## Steps to Reproduce
<numbered steps derived from description and session context>

## Expected Behavior
<what should have happened>

## Actual Behavior
<what actually happened>

## Environment
- **OS**: <os info>
- **Python**: <version>
- **Scout**: <version>
- **botasaurus-driver**: <version>
- **Active session**: <yes (URL) or no>
```

**For Feature Request:**
```
## Description
<user's description>

## Use Case
<what the user is trying to accomplish — synthesize from their description>

## Environment
- **OS**: <os info>
- **Python**: <version>
- **Scout**: <version>
```

**For UX Friction:**
```
## What Happened
<user's description of the awkward experience>

## What Would Be Better
<user's suggestion or your synthesis of what would improve the experience>

## Environment
- **OS**: <os info>
- **Python**: <version>
- **Scout**: <version>
- **Active session**: <yes (URL) or no>
```

### Label
- Bug → `bug`
- Feature Request → `enhancement`
- UX Friction → `ux-friction`

## Step 7: Review with user

Show the complete draft (title + body) to the user.

Include this warning: **"This will be posted publicly to GitHub. Review for internal URLs, selectors, or sensitive information before approving."**

Ask: "Ready to submit, or want to change anything?"

If the user wants changes, incorporate them and show the updated draft.

## Step 8: Ensure label exists and submit

For UX Friction issues, ensure the custom label exists:
```bash
gh label create ux-friction --description "Works but feels awkward" --color "d4c5f9" --repo stemado/scout 2>/dev/null || true
```

Then submit using a heredoc for the body to preserve formatting:
```bash
gh issue create --repo stemado/scout --title "<title>" --label "<label>" --body "$(cat <<'EOF'
<body content>
EOF
)"
```

## Step 9: Confirm

Show the user the issue URL from the gh output. Say: "Issue filed! You can track it here: <url>"
