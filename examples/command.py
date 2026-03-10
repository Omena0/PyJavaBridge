from bridge import *
from typing import Optional

# Test auto-generated usage
@command("Hello world command")
async def helloworld(event: Event):
    """Send a Hello World message to the player."""
    event.player.send_message("Hello, World!")

# Test command args
@command("Greet command")
async def greet(event: Event, name: Optional[str] = None):
    """Greet a player by name."""
    event.player.send_message(f"Hello, {name or event.player.name}!")

# Test raycast / teleport
@command("Teleport to spawn")
async def spawn(event: Event):
    """Teleport the player to spawn using raycast."""
    ray = await raycast('world', (0.5, 320, 0.5), (0, 90), 384, 0.5, False)
    if ray is not None:
        event.player.teleport(Location(0.5, ray.y+0.5, 0.5, world='world'))

# Test Inventory API
@command("open test gui")
async def gui(event: Event):
    """Open a test inventory GUI."""
    pane = Item('light_gray_stained_glass_pane')
    await pane.set_name(" ")
    inv = Inventory(3*9, title="Test GUI", contents=[pane for _ in range(3*9)])

    totem = Item('totem_of_undying')
    await totem.set_name("Bing chilling")
    inv.set_item(9+4, totem)

    inv.open(event.player)

# Test Inventory Click event
@event
async def inventory_click(event: Event):
    """Handle clicks in the test GUI."""
    if event.inventory.title != 'Test GUI':
        return

    event.cancel()

    if event.slot == 9+4:
        event.player.play_sound(Sound.from_name('ITEM_TOTEM_USE'))
        event.player.send_message('Bing chilling')
        event.inventory.close()

@event
async def inventory_drag(event: Event):
    """Cancel drags in the test GUI."""
    if event.inventory.title == 'Test GUI':
        event.cancel()

@command("Open someones inv")
async def invsee(event: Event, p: str):
    """Open another player's inventory."""
    if p == event.player.name:
        event.player.send_message("You cannot open your own inventory!")
        event.player.play_sound(Sound.from_name('BLOCK_NOTE_BLOCK_BASS'))
        return

    Player(name=p).inventory.open(event.player)
