
# PyJavaBridge

**Expose bukkit APIs to python scripts via easy-to-use wrappers.**

```py
from bridge import *

# Use via /helloworld
@command("Hello world command")
async def helloworld(event: Event):
    event.player.send_message("Hello, World!")
```

The entire API is, at core, asynchronous.
Though you do not need to await any methods unless you want to wait for the call to complete.

## Documentation

See [The Docs](https://omena0.github.io/PyJavaBridge/index.html)

For quick searches use the pjb cli script.

## Performance

Currently the performance is suboptimal, the current bottleneck is the bridge itself.
You should avoid doing anything that sends many requests over the bridge.
If possible you should always use `server.frame()` to batch requests.

## Changelog

See [changelog.md](changelog.md)
