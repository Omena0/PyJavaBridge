from bridge import *

# Test auto-generated usage
@command("Hello world command")
async def helloworld(event: Event):
    event.player.send_message("Hello, World!")

# Test command args
@command("Greet command")
async def greet(event: Event, name: str = None):
    event.player.send_message(f"Hello, {name or event.player.name}!")

# Test raycast / teleport
@command("Teleport to spawn")
async def spawn(event: Event):
    ray:RaycastResult = await raycast('world', (0.5, 320, 0.5), (0, 90), 384, 0.5, False)
    event.player.teleport((0.5, ray.y+0.5, 0.5))

# Test Inventory API
@command("open test gui")
async def gui(event: Event):
    inv = Inventory(3*9, title="Test GUI", contents=[Item('light_gray_stained_glass_pane').set_name(" ") for _ in range(3*9)])

    inv.set_item(9+4, Item('totem_of_undying').set_name("Bing chilling"))

    inv.open(event.player)

# Test Inventory Click event
@event
async def inventory_click(event: Event):
    if event.inventory.title != 'Test GUI':
        return

    event.cancel()

    if event.slot == 9+4:
        event.player.play_sound('item_totem_use')
        event.player.send_message('Bing chilling')
        event.inventory.close()

@event
async def inventory_drag(event: Event):
    if event.inventory.title == 'Test GUI':
        event.cancel()

@command("Open someones inv")
async def invsee(event: Event, p: str):
    if p == event.player.name:
        event.player.send_message("You cannot open your own inventory!")
        event.player.play_sound('block_note_block_bass')
        return

    Player(p).inventory.open(event.player)
