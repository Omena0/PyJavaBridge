# Client Mod Extension (JS/WASM)

The client mod now executes untrusted server-provided scripts using a JavaScript/WASM sandbox.

## Architecture
- Server sends a minified JavaScript payload or a WASM module via `SCRIPT_REGISTER`
- Client mod spawns a sandbox host process per script (Javet/V8)
- Host and client communicate over length-delimited JSON via stdin/stdout
- TypeScript wrapper runs inside a SES Compartment and exposes the `pjb` API
- All capabilities are permission-checked by the client mod

## Script Registration
`SCRIPT_REGISTER` body:
```json
{
  "name": "example",
  "source": "...js source...",
  "kind": "js",
  "auto_start": true,
  "metadata": {"capabilities": ["logger.info", "event.tick"]}
}
```
For WASM:
```json
{
  "name": "example",
  "kind": "wasm",
  "source": "<base64 wasm>",
  "metadata": {"capabilities": ["logger.info"]}
}
```

## API
The wrapper provides `pjb` (and globals `capability`, `print`, `log`, `request`, `client`, `Player`, `inventory`, `storage`, `menu`, etc.).

## Permissions
Permissions are enforced per capability call. Scripts can declare via `pjb.capabilities([...])`.

## WASM ABI
Standalone WASM modules can import `pjb` functions; see wrapper for details. Host provides controlled imports only.
