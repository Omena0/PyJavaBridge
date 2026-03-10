---
title: Player
subtitle: Player API — extends Entity
---

# Player

`Player` extends [`Entity`](entity.md) with player-specific functionality: health, hunger, experience, permissions, inventory, tab list, game mode, and more.

---

## Constructor

```python
Player(uuid: str | None = None, name: str | None = None)
```

Resolve a player by UUID or name. At least one must be provided. The player must be online.

- **Parameters:**
  - `uuid` (`str | None`) — The player's UUID.
  - `name` (`str | None`) — The player's name (case-insensitive lookup).

```python
p = Player(name="Steve")
p = Player(uuid="550e8400-e29b-41d4-a716-446655440000")
```

---

## Attributes

### name

- **Type:** `str`

The player's display name.

### uuid

- **Type:** `str`

The player's UUID.

### location

- **Type:** [`Location`](location.md)

Current player location.

### world

- **Type:** [`World`](world.md)

The world the player is in.

### health

- **Type:** `float`

Current health (0–20 by default, 0 = dead).

### food_level

- **Type:** `int`

Hunger level (0–20, 20 = full).

### game_mode

- **Type:** [`GameMode`](enums.md)

Current game mode (e.g. `GameMode.SURVIVAL`, `GameMode.CREATIVE`).

### inventory

- **Type:** [`Inventory`](inventory.md)

The player's inventory (36 slots + armor + offhand).

### held_item

- **Type:** [`Item`](item.md)

The item currently in the player's main hand. Returns an `Item` proxy (may be air if the hand is empty).

### selected_slot

- **Type:** `int`

The player's currently selected hotbar slot (0–8).

```python
@event
async def player_item_held(e):
    slot = e.player.selected_slot
    await e.player.send_message(f"Switched to slot {slot}")
```

### level

- **Type:** `int`
- **Settable:** `player.level = 5`

Player experience level (the green number).

### exp

- **Type:** `float`
- **Settable:** `player.exp = 0.5`

Experience progress within the current level (0.0 to 1.0).

### is_op

- **Type:** `bool`

Whether the player is a server operator.

### is_flying

- **Type:** `bool`
- **Settable:** `player.is_flying = True`

Whether the player is currently flying.

### is_sneaking

- **Type:** `bool`
- **Settable:** `player.is_sneaking = True`

Whether the player is sneaking (shift held).

### is_sprinting

- **Type:** `bool`
- **Settable:** `player.is_sprinting = True`

Whether the player is sprinting.

### scoreboard

- **Type:** [`Scoreboard`](scoreboard.md)

The player's current scoreboard.

### permission_groups

- **Type:** `list[str]`

The player's permission groups. LuckPerms-aware — returns LuckPerms groups if available, otherwise falls back to the basic permission system.

### primary_group

- **Type:** `str | None`

The player's primary permission group (LuckPerms). `None` if LuckPerms is not installed.

### tab_list_header

- **Type:** `str`
- **Settable:** `player.tab_list_header = "§6My Server"`

The player's tab list header text.

### tab_list_footer

- **Type:** `str`
- **Settable:** `player.tab_list_footer = "§7play.example.com"`

The player's tab list footer text.

### tab_list_name

- **Type:** `str`
- **Settable:** `player.tab_list_name = "§c[Admin]§r Steve"`

The player's display name in the tab list.

### absorption

- **Type:** `float`
- **Settable:** `player.absorption = 4.0`

Absorption hearts amount (golden hearts).

### saturation

- **Type:** `float`
- **Settable:** `player.saturation = 5.0`

Food saturation level. Higher saturation prevents hunger drain.

### exhaustion

- **Type:** `float`
- **Settable:** `player.exhaustion = 0.0`

Food exhaustion level. When exhaustion exceeds 4.0, saturation decreases.

### attack_cooldown

- **Type:** `float`

Attack cooldown progress (0.0 to 1.0). Read-only.

### allow_flight

- **Type:** `bool`
- **Settable:** `player.allow_flight = True`

Whether the player is allowed to fly.

### locale

- **Type:** `str`

The player's client locale string (e.g. `"en_US"`).

### ping

- **Type:** `int`

The player's ping in milliseconds.

### client_brand

- **Type:** `str`

The player's client brand (e.g. `"vanilla"`, `"fabric"`).

### max_health

- **Type:** `float`
- **Settable:** `player.max_health = 40.0`

The player's maximum health. Default is 20.0 (10 hearts).

### bed_spawn_location

- **Type:** [`Location`](location.md) `| None`
- **Settable:** `player.bed_spawn_location = location`
- **Deletable:** `del player.bed_spawn_location`

The player's bed/respawn location. `None` if not set.

### compass_target

- **Type:** [`Location`](location.md)
- **Settable:** `player.compass_target = location`

The location the player's compass points to.

---

## Methods

### send_message

```python
await player.send_message(message)
```

Send a chat message to the player.

- **Parameters:**
  - `message` (`str`) — The message. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await player.send_message("§aYou found a secret!")
```

### chat

```python
await player.chat(message)
```

Make the player send a chat message (as if they typed it).

- **Parameters:**
  - `message` (`str`) — The message to send.
- **Returns:** `Awaitable[None]`

### kick

```python
await player.kick(reason="")
```

Kick the player from the server.

- **Parameters:**
  - `reason` (`str`) — Kick reason shown to the player. Default empty.
- **Returns:** `Awaitable[None]`

```python
await player.kick("§cYou have been banned!")
```

### teleport

```python
await player.teleport(location)
```

Teleport the player. Inherited from [`Entity`](entity.md).

- **Parameters:**
  - `location` ([`Location`](location.md)) — Destination.
- **Returns:** `Awaitable[None]`

### give_exp

```python
await player.give_exp(amount)
```

Give raw experience points to the player.

- **Parameters:**
  - `amount` (`int`) — XP points to add.
- **Returns:** `Awaitable[None]`

### set_exp

```python
await player.set_exp(exp)
```

Set the experience progress bar within the current level.

- **Parameters:**
  - `exp` (`float`) — Progress from 0.0 to 1.0.
- **Returns:** `Awaitable[None]`

### set_level

```python
await player.set_level(level)
```

Set the player's experience level.

- **Parameters:**
  - `level` (`int`) — The level number.
- **Returns:** `Awaitable[None]`

### set_health

```python
await player.set_health(health)
```

Set the player's health.

- **Parameters:**
  - `health` (`float`) — Health from 0.0 to 20.0 (default max).
- **Returns:** `Awaitable[None]`

### set_food_level

```python
await player.set_food_level(level)
```

Set the player's hunger level.

- **Parameters:**
  - `level` (`int`) — Food level from 0 to 20.
- **Returns:** `Awaitable[None]`

### set_game_mode

```python
await player.set_game_mode(mode)
```

Set the player's game mode.

- **Parameters:**
  - `mode` ([`GameMode`](enums.md)) — The game mode.
- **Returns:** `Awaitable[None]`

```python
await player.set_game_mode(GameMode.CREATIVE)
```

### set_op

```python
await player.set_op(value)
```

Set operator status.

- **Parameters:**
  - `value` (`bool`) — `True` for op, `False` to deop.
- **Returns:** `Awaitable[None]`

### set_flying

```python
await player.set_flying(value)
```

Set flying state. The player must be allowed to fly (creative mode or flight allowed).

- **Parameters:**
  - `value` (`bool`)
- **Returns:** `Awaitable[None]`

### set_sneaking

```python
await player.set_sneaking(value)
```

Force the sneaking state.

- **Parameters:**
  - `value` (`bool`)
- **Returns:** `Awaitable[None]`

### set_sprinting

```python
await player.set_sprinting(value)
```

Force the sprinting state.

- **Parameters:**
  - `value` (`bool`)
- **Returns:** `Awaitable[None]`

### set_walk_speed

```python
await player.set_walk_speed(speed)
```

Set walking speed.

- **Parameters:**
  - `speed` (`float`) — Speed multiplier. Default is 0.2. Range: -1.0 to 1.0.
- **Returns:** `Awaitable[None]`

### set_fly_speed

```python
await player.set_fly_speed(speed)
```

Set flying speed.

- **Parameters:**
  - `speed` (`float`) — Speed multiplier. Default is 0.1. Range: -1.0 to 1.0.
- **Returns:** `Awaitable[None]`

### set_scoreboard

```python
await player.set_scoreboard(scoreboard)
```

Set the player's active scoreboard.

- **Parameters:**
  - `scoreboard` ([`Scoreboard`](scoreboard.md)) — The scoreboard to display.
- **Returns:** `Awaitable[None]`

### hide_player

```python
await player.hide_player(other)
```

Hide another player from this player.

- **Parameters:**
  - `other` ([`Player`](#)) — The player to hide.
- **Returns:** `Awaitable[None]`

### show_player

```python
await player.show_player(other)
```

Show a previously hidden player to this player.

- **Parameters:**
  - `other` ([`Player`](#)) — The player to show.
- **Returns:** `Awaitable[None]`

### can_see

```python
visible = await player.can_see(other)
```

Check if this player can see another player.

- **Parameters:**
  - `other` ([`Player`](#)) — The player to check.
- **Returns:** `Awaitable[bool]`

### open_book

```python
await player.open_book(item)
```

Open a written book for the player.

- **Parameters:**
  - `item` ([`Item`](item.md)) — A written book item.
- **Returns:** `Awaitable[None]`

### send_block_change

```python
await player.send_block_change(location, material)
```

Send a fake block change to the player (client-side only).

- **Parameters:**
  - `location` ([`Location`](location.md)) — The block location.
  - `material` (`str`) — The material to display.
- **Returns:** `Awaitable[None]`

### send_particle

```python
await player.send_particle(particle, location, count=1, offset_x=0, offset_y=0, offset_z=0, extra=0)
```

Send a particle effect to the player.

- **Parameters:**
  - `particle` ([`Particle`](enums.md) `| str`) — The particle type.
  - `location` ([`Location`](location.md)) — Where to spawn the particle.
  - `count` (`int`) — Number of particles. Default `1`.
  - `offset_x` (`float`) — Random offset on X axis.
  - `offset_y` (`float`) — Random offset on Y axis.
  - `offset_z` (`float`) — Random offset on Z axis.
  - `extra` (`float`) — Extra data (usually speed). Default `0`.
- **Returns:** `Awaitable[None]`

---

## Cooldowns

### get_cooldown

```python
ticks = await player.get_cooldown(material)
```

Get the remaining cooldown on a material (item type).

- **Parameters:**
  - `material` (`str`) — The material name.
- **Returns:** `Awaitable[int]` — Remaining ticks.

### set_cooldown

```python
await player.set_cooldown(material, ticks)
```

Set a cooldown on a material.

- **Parameters:**
  - `material` (`str`) — The material name.
  - `ticks` (`int`) — Cooldown duration in ticks.
- **Returns:** `Awaitable[None]`

### has_cooldown

```python
result = await player.has_cooldown(material)
```

Check if a material has an active cooldown.

- **Parameters:**
  - `material` (`str`) — The material name.
- **Returns:** `Awaitable[bool]`

---

## Statistics

### get_statistic

```python
value = await player.get_statistic(stat, material_or_entity=None)
```

Get a player statistic value.

- **Parameters:**
  - `stat` (`str`) — The statistic name (e.g. `"PLAY_ONE_MINUTE"`, `"MINE_BLOCK"`).
  - `material_or_entity` (`str | None`) — Sub-type for material/entity statistics.
- **Returns:** `Awaitable[int]`

```python
playtime = await player.get_statistic("PLAY_ONE_MINUTE")
blocks_mined = await player.get_statistic("MINE_BLOCK", "DIAMOND_ORE")
```

### set_statistic

```python
await player.set_statistic(stat, value, material_or_entity=None)
```

Set a player statistic value.

- **Parameters:**
  - `stat` (`str`) — The statistic name.
  - `value` (`int`) — The value to set.
  - `material_or_entity` (`str | None`) — Sub-type for material/entity statistics.
- **Returns:** `Awaitable[None]`

---

## Persistent Data Container (PDC)

Store custom data on the player that persists across server restarts.

### get_persistent_data

```python
data = await player.get_persistent_data()
```

Get all persistent data as a dictionary.

- **Returns:** `Awaitable[dict]`

### set_persistent_data

```python
await player.set_persistent_data(key, value)
```

Set a persistent data key.

- **Parameters:**
  - `key` (`str`) — The data key.
  - `value` (`str`) — The data value.
- **Returns:** `Awaitable[None]`

### remove_persistent_data

```python
await player.remove_persistent_data(key)
```

Remove a persistent data key.

- **Parameters:**
  - `key` (`str`) — The key to remove.
- **Returns:** `Awaitable[None]`

### has_persistent_data

```python
result = await player.has_persistent_data(key)
```

Check if a persistent data key exists.

- **Parameters:**
  - `key` (`str`) — The key to check.
- **Returns:** `Awaitable[bool]`

```python
await player.set_persistent_data("quest_stage", "3")
if await player.has_persistent_data("quest_stage"):
    stage = (await player.get_persistent_data())["quest_stage"]
```

---

## Effects

### effects

```python
effects = player.effects
```

Get a list of the player's active potion effects.

- **Type:** `list[`[`Effect`](effect.md)`]`

```python
for effect in player.effects:
    print(f"{effect.type}: amplifier {effect.amplifier}, {effect.duration} ticks left")
```

### add_effect

```python
await player.add_effect(effect)
```

Apply a potion effect to the player.

- **Parameters:**
  - `effect` ([`Effect`](effect.md)) — The effect to apply.
- **Returns:** `Awaitable[None]`

```python
await player.add_effect(Effect(EffectType.SPEED, duration=200, amplifier=1))
```

### remove_effect

```python
await player.remove_effect(effect_type)
```

Remove an active potion effect.

- **Parameters:**
  - `effect_type` ([`EffectType`](enums.md)) — The effect type to remove.
- **Returns:** `Awaitable[None]`

---

## Sounds & UI

### play_sound

```python
await player.play_sound(sound, volume=1.0, pitch=1.0)
```

Play a sound to the player at their location.

- **Parameters:**
  - `sound` ([`Sound`](enums.md)) — The sound to play.
  - `volume` (`float`) — Volume. Default 1.0.
  - `pitch` (`float`) — Pitch. Default 1.0.
- **Returns:** `Awaitable[None]`

```python
await player.play_sound(Sound.ENTITY_EXPERIENCE_ORB_PICKUP)
await player.play_sound('block_note_block_bass', volume=0.5, pitch=2.0)
```

### set_resource_pack

```python
await player.set_resource_pack(url, hash="", prompt=None, required=False)
```

Send a resource pack to the player.

- **Parameters:**
  - `url` (`str`) — URL of the resource pack.
  - `hash` (`str`) — SHA-1 hash of the pack as a hex string (optional but recommended).
  - `prompt` (`str | None`) — Custom prompt message shown to the player.
  - `required` (`bool`) — Whether the pack is required to stay on the server (default `False`).
- **Returns:** `Awaitable[None]`

```python
await player.set_resource_pack(
    "https://example.com/pack.zip",
    hash="a1b2c3d4e5f6...",
    prompt="Download our custom textures!",
    required=True
)
```

### send_action_bar

```python
await player.send_action_bar(message)
```

Display a message in the action bar (above the hotbar).

- **Parameters:**
  - `message` (`str`) — The message. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

### send_title

```python
await player.send_title(title, subtitle="", fade_in=10, stay=70, fade_out=20)
```

Display a title and subtitle on the player's screen.

- **Parameters:**
  - `title` (`str`) — The main title text.
  - `subtitle` (`str`) — Subtitle text below the title.
  - `fade_in` (`int`) — Fade-in time in ticks. Default 10 (0.5s).
  - `stay` (`int`) — Display time in ticks. Default 70 (3.5s).
  - `fade_out` (`int`) — Fade-out time in ticks. Default 20 (1s).
- **Returns:** `Awaitable[None]`

```python
await player.send_title("§6Victory!", "§eYou won the game", fade_in=5, stay=40, fade_out=10)
```

---

## Tab List

### set_tab_list_header

```python
await player.set_tab_list_header(header)
```

Set the header text shown above the player list in the tab screen.

- **Parameters:**
  - `header` (`str`) — Header text. Supports `§` color codes and `\n` for multiple lines.
- **Returns:** `Awaitable[None]`

### set_tab_list_footer

```python
await player.set_tab_list_footer(footer)
```

Set the footer text shown below the player list.

- **Parameters:**
  - `footer` (`str`) — Footer text.
- **Returns:** `Awaitable[None]`

### set_tab_list_header_footer

```python
await player.set_tab_list_header_footer(header="", footer="")
```

Set both header and footer in a single call.

- **Parameters:**
  - `header` (`str`) — Header text.
  - `footer` (`str`) — Footer text.
- **Returns:** `Awaitable[None]`

### set_tab_list_name

```python
await player.set_tab_list_name(name)
```

Set the player's display name in the tab list.

- **Parameters:**
  - `name` (`str`) — Display name. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await player.set_tab_list_name("§c[Admin]§r Steve")
```

---

## Permissions

### has_permission

```python
result = await player.has_permission(permission)
```

Check if the player has a permission node.

- **Parameters:**
  - `permission` (`str`) — The permission node (e.g. `"myplugin.use"`).
- **Returns:** `Awaitable[bool]`

### add_permission

```python
result = await player.add_permission(permission, value=True)
```

Add or set a permission on the player. LuckPerms-aware.

- **Parameters:**
  - `permission` (`str`) — The permission node.
  - `value` (`bool`) — `True` to grant, `False` to negate. Default `True`.
- **Returns:** `Awaitable[bool]`

### remove_permission

```python
result = await player.remove_permission(permission)
```

Remove a permission from the player. LuckPerms-aware.

- **Parameters:**
  - `permission` (`str`) — The permission node to remove.
- **Returns:** `Awaitable[bool]`

### has_group

```python
result = await player.has_group(group)
```

Check if the player belongs to a permission group. **LuckPerms only.**

- **Parameters:**
  - `group` (`str`) — The group name.
- **Returns:** `Awaitable[bool]`

### add_group

```python
result = await player.add_group(group)
```

Add the player to a permission group. **LuckPerms only.**

- **Parameters:**
  - `group` (`str`) — The group name.
- **Returns:** `Awaitable[bool]`

### remove_group

```python
result = await player.remove_group(group)
```

Remove the player from a permission group. **LuckPerms only.**

- **Parameters:**
  - `group` (`str`) — The group name.
- **Returns:** `Awaitable[bool]`

---

## Freeze & Vanish

Utility helpers for freezing and hiding players.

### freeze

```python
player.freeze()
```

Lock the player's position. The player is teleported back to their frozen location every tick until unfrozen. **Synchronous.**

### unfreeze

```python
player.unfreeze()
```

Release the player, allowing movement again. **Synchronous.**

### is_frozen

- **Type:** `bool`

Whether the player is currently frozen.

### vanish

```python
player.vanish()
```

Hide this player from all other players. **Synchronous.**

### unvanish

```python
player.unvanish()
```

Make the player visible again. **Synchronous.**

### is_vanished

- **Type:** `bool`

Whether the player is currently vanished.

---

## Extension Shortcuts

These properties require a default extension instance to be assigned on the `Player` class. They provide convenient syntax for accessing extension data.

### balance / deposit / withdraw

```python
Player._default_bank = my_bank  # Set once at startup

bal = player.balance
player.deposit(100)
player.withdraw(50)
```

Requires `Player._default_bank` to be set to a [`Bank`](bank.md) instance.

### mana

```python
Player._default_mana_store = my_mana  # Set once at startup

current = player.mana
player.mana = 50
```

Requires `Player._default_mana_store` to be set to a [`ManaStore`](mana.md) instance.

### xp / player_level

```python
Player._default_level_system = my_levels  # Set once at startup

xp = player.xp
lvl = player.player_level
```

Requires `Player._default_level_system` to be set to a [`LevelSystem`](levels.md) instance.
