
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

## Documentation

See [The Docs](https://omena0.github.io/PyJavaBridge/index.html)

## Changelog

See [changelog.md](changelog.md)
