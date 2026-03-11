---
title: Lifecycle
subtitle: Startup, shutdown, and hot reload
---

# Lifecycle

How scripts are started, stopped, and reloaded — including the Python process launch and file watcher.

---

## Startup Sequence

When the plugin enables (server start or `/reload`):

### 1. Plugin initialization (`onEnable`)

```tree
PyJavaBridgePlugin.onEnable()
├── Register /bridge command
├── Register event listeners
├── Copy runtime resources (bridge.py, runner.py → plugins/PyJavaBridge/)
├── Detect Python virtual environments
└── startScripts()
```

### 2. Virtual environment detection

The plugin searches for Python virtual environments in the scripts directory:

1. Check for `venv/bin/python3` (Linux/macOS)
2. Check for `venv/Scripts/python.exe` (Windows)
3. Check for `.venv/bin/python3` or `.venv/Scripts/python.exe`
4. Fall back to system `python3` / `python`

### 3. Script discovery

`startScripts()` scans `plugins/PyJavaBridge/scripts/` for `.py` files (non-recursive). Each file gets its own `BridgeInstance`.

### 4. Python process launch

For each script, a `ProcessBuilder` starts:

```command
{python_path} runner.py {script_path}
```

With:

- **Working directory:** `plugins/PyJavaBridge/`
- **stdin/stdout:** Piped (bridge protocol)
- **stderr:** Inherited (goes to server console)

### 5. Python bootstrap (`runner.py`)

The runner script:

1. Imports `bridge.py` from the runtime directory
2. Calls `_bootstrap(script_path)` in bridge.py

### 6. Bridge bootstrap (`_bootstrap`)

```python
def _bootstrap(script_path):
    global _connection, _script_module
    _connection = BridgeConnection()     # Sets up stdin/stdout protocol
    _connection.start()                  # Starts reader daemon thread
    _script_module = load_module(script_path)  # exec() the user script
    loop.run_forever()                   # asyncio event loop (blocks)
```

The `run_forever()` call blocks until shutdown — all user code runs via asyncio tasks scheduled on this loop.

### 7. Format handshake

During `BridgeConnection.__init__()`, Python sends a handshake message (always as JSON) declaring its preferred serialization format:

```json
{"type": "handshake", "format": "msgpack"}
```

- If Python has `msgpack` installed, the format is `"msgpack"` — both sides switch to binary msgpack for all subsequent messages
- Otherwise, the format is `"json"` and nothing changes
- The handshake is always sent as JSON since Java starts in JSON mode and hasn't switched yet

### 8. Java reader thread

`BridgeInstance` creates a dedicated reader thread per script that continuously reads length-prefixed messages from the process stdout. The first message (the handshake) is always JSON; after processing it, subsequent messages use the negotiated format. This thread dispatches responses to the bridge thread queue.

---

## Shutdown Sequence

Shutdown can be triggered by: server stop, `/bridge reload`, or `/bridge stop <script>`.

### 1. Send shutdown event

Java sends a shutdown message to Python:

```json
{"type": "event", "event": "shutdown"}
```

### 2. Python handles shutdown

```python
async def _handle_shutdown(args):
    # Fire user @event("shutdown") handlers
    await _fire_event("shutdown", args)
    
    # Send acknowledgment
    _connection._send({"type": "shutdown_ack"})
    
    # Unblock reader thread
    sys.stdin.close()
    
    # Stop event loop
    loop = asyncio.get_event_loop()
    loop.stop()
```

### 3. Java waits for process exit

```java
void shutdown() {
    sendMessage(shutdownEvent);
    
    // Wait up to 2 seconds for clean exit
    if (!process.waitFor(2, TimeUnit.SECONDS)) {
        process.destroyForcibly();
    }
    
    objectRegistry.clear();
}
```

### 4. Cleanup

- All object handles are cleared from the registry
- The reader thread exits (stdin/stdout closed)
- Event subscriptions are discarded
- Registered commands are unregistered from the command map

---

## Hot Reload

### File watcher

The plugin uses Java's `WatchService` to monitor the scripts directory:

```tree
WatchService (NIO)
├── Poll interval: 200ms
├── Debounce: 1000ms after last change
├── Events: ENTRY_CREATE, ENTRY_MODIFY, ENTRY_DELETE
└── Scope: plugins/PyJavaBridge/scripts/
```

### Debounce logic

When a file change is detected:

1. Record the timestamp
2. Wait 1000ms from the *last* change (debounce)
3. If no further changes, trigger reload

This prevents rapid-fire restarts when saving files (editors sometimes write multiple times).

### Restart flow

```tree
File changed → debounce → restartScript(scriptName)
  ├── shutdown() existing BridgeInstance
  ├── Wait for process exit
  ├── Create new BridgeInstance
  └── Start new Python process
```

The restart is atomic per-script — other scripts continue running during the reload.

### Manual reload

- `/bridge reload` — Reloads all scripts
- `/bridge reload <script>` — Reloads a specific script
- `/bridge stop <script>` — Stops without restart
- `/bridge start <script>` — Starts a stopped script

---

## Script Management

### Script states

Each script (BridgeInstance) can be in one of:

| State | Description |
| ----- | ----------- |
| **Running** | Process alive, bridge active |
| **Stopped** | Cleanly shut down |
| **Crashed** | Process exited unexpectedly |

### Crash detection

The reader thread monitors the process. If it exits unexpectedly (non-zero exit code or broken pipe), the script is marked as crashed and a warning is logged.

### The `/bridge` command

```syntax
/bridge                  — List running scripts and status
/bridge reload           — Reload all scripts
/bridge reload <script>  — Reload specific script
/bridge stop <script>    — Stop a script
/bridge start <script>   — Start a stopped script
/bridge debug            — Toggle debug logging
```

All `/bridge` commands require the `pyjavabridge.admin` permission (default: op).
