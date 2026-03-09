---
name: release
description: Bump version, tag, and push a new release for the Scout plugin. Scout is self-contained — there is no separate marketplace repo. This skill should be used when the user says "release", "/release", "bump version", "publish a new version", "cut a release", or "version bump". Argument should be one of patch, minor, or major.
---

# Release Scout Plugin Version

Bump the Scout plugin version, commit, tag, and push. Scout is **self-contained** — the `stemado/scout` repo IS the distribution. There is no separate marketplace repo. Follow these steps precisely.

**Important:** All git and file commands in this workflow assume the current working directory is the scout project root (`D:\Projects\scout`). Use absolute paths if running from a different directory.

## Step 1: Parse argument

Validate the argument is one of `patch`, `minor`, `major`. If missing or not one of those three values, show usage and stop:

```
Usage: /release <patch|minor|major>

Examples:
  /release patch   — 0.1.0 → 0.1.1
  /release minor   — 0.1.0 → 0.2.0
  /release major   — 0.1.0 → 1.0.0
```

## Step 2: Read current version

Run this via bash to extract the current version:

```bash
grep -m1 'version = ' pyproject.toml
```

Parse the result into three integers: MAJOR, MINOR, PATCH. The format is `version = "X.Y.Z"`.

## Step 3: Compute new version

Apply the bump type to the parsed integers:

- `patch`: PATCH + 1
- `minor`: MINOR + 1, PATCH = 0
- `major`: MAJOR + 1, MINOR = 0, PATCH = 0

Tell the user: "Bumping from {old} to {new}"

## Step 4: Pre-flight: clean working tree

Run via bash:

```bash
git status --porcelain
```

If the output is non-empty, abort with: "Working tree is not clean. Commit or stash your changes first."

Do NOT proceed past this point if the tree is dirty.

## Step 5: Pre-flight: tag doesn't exist

Run both of these via bash:

```bash
git tag -l v{new}
```

```bash
git ls-remote --tags origin refs/tags/v{new}
```

If either command returns any output, abort with: "Tag v{new} already exists."

## Step 6: Pre-flight: first-run baseline tag

Run via bash:

```bash
git tag -l
```

If no tags exist at all (empty output), create a baseline tag on HEAD:

```bash
git tag v{old}
git push origin v{old}
```

Tell the user: "Created baseline tag v{old}."

## Step 7: Update all 4 files in scout repo

Use the Edit tool for each file. Replace the old version with the new version using the exact patterns:

1. `pyproject.toml` — replace `version = "{old}"` with `version = "{new}"`
2. `src/scout/__init__.py` — replace `__version__ = "{old}"` with `__version__ = "{new}"`
3. `.claude-plugin/plugin.json` — replace `"version": "{old}"` with `"version": "{new}"`
4. `.claude-plugin/marketplace.json` — replace `"version": "{old}"` with `"version": "{new}"`

After all 4 edits, verify they took effect by running via bash:

```bash
grep -c "{new}" pyproject.toml src/scout/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Each file should report a count of at least 1. If any file shows 0, the edit failed — stop and investigate.

## Step 8: Commit, tag, and push

Run via bash:

```bash
git add pyproject.toml src/scout/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "release: v{new}"
git tag v{new}
git push origin main --tags
```

**If the push fails:** Tell the user the error, then **show** (do NOT execute) these manual recovery instructions and STOP. Do NOT run these recovery commands yourself — they are destructive and the user must choose to run them.

```
The push failed. To recover:
1. Your local commit and tag are intact. Try again with:
     git push origin main --tags
2. If the issue persists, check your network and GitHub permissions.
3. To undo the local changes entirely:
     git tag -d v{new}
     git reset --soft HEAD~1
     git restore --staged pyproject.toml src/scout/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
     git checkout -- pyproject.toml src/scout/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
   Then re-run /release {bump-type}
```

## Step 9: Create GitHub Release

Claude Code resolves plugin versions from **GitHub Releases**, not raw git tags. Without this step, the tag exists but `plugin update` won't see it.

Run via bash:

```bash
gh release create v{new} --title "v{new}" --generate-notes --target main
```

This creates a GitHub Release object tied to the tag, with auto-generated release notes from the commit log since the previous tag.

**If `gh release create` fails:** The tag and push already succeeded — the code is live. Show the user the error and suggest running the command manually. Do NOT delete the tag or revert the commit.

## Step 10: Report success

Show the user a summary:

```
Release v{new} complete!

Version: {old} → {new}
Git tag: v{new}
GitHub Release: https://github.com/stemado/scout/releases/tag/v{new}

Files updated (4):
  - pyproject.toml
  - src/scout/__init__.py
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json

Claude Code will pick up the new version automatically on next plugin refresh,
or manually via: /plugin update scout@scout

Rollback (if needed):
  gh release delete v{new} --yes
  git tag -d v{new}
  git push origin :refs/tags/v{new}
  git revert HEAD
  git push origin main
```
