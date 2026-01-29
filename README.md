
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

## Docs

See [The documentation](docs/index.md)

## Examples

See [examples](examples/index.md)

## Changelog

See [changelog.md](changelog.md)
