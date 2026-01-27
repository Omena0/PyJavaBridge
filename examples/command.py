from bridge import *

@command("Hello world command")
async def helloworld(event: Event):
    event.player.send_message("Hello, World!")

@command("Greet command")
async def greet(event: Event, name: str = None):
    event.player.send_message(f"Hello, {name or event.player.name}!")

