---
description: Connect to a remote scout-engine server
argument-hint: "[url]"
---

Set up the connection to a remote scout-engine server. This saves the URL and API key so that `/sync`, `/run`, `/status`, and `/schedule` can talk to the engine.

## Steps

1. **Get the engine URL.**
   If the user provided a URL as an argument, use it. Otherwise, ask: "What is the URL of your scout-engine server? (e.g., https://178.104.0.194)"

2. **Get the API key.**
   Ask: "What is the API key? (find it on the server with `cat /root/scout-credentials.txt`)"

3. **Test the connection.**
   Use `httpx` to call `GET {url}/api/health` with the header `Authorization: Bearer {api_key}`. If the URL is an IP address, skip TLS verification (`verify=False`).

   - If the health check succeeds: continue to step 4.
   - If connection refused: "Cannot reach scout-engine at {url}. Is the server running?"
   - If 401/403: "API key rejected. Double-check the key and try again."

4. **Save the configuration.**
   Write to `.claude/scout.local.md` in the current working directory:
   ```yaml
   ---
   engine_url: {url}
   engine_api_key: {api_key}
   ---
   ```
   Create the `.claude/` directory if it doesn't exist.

5. **Confirm.**
   Report: "Connected to scout-engine at {url} (v{version}). You can now use `/sync`, `/run`, `/status`, and `/schedule`."
   Include the version from the health check response.

Use `httpx` for the HTTP call. Do not use the `EngineClient` class — this command creates the config that `EngineClient` reads.
