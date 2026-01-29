# PyJavaBridge docs

PyJavaBridge is a java plugin that manages and exposes APIs to python scripts via wrappers.

## Table of contents

- [Event](#event)
- [Server](#server)
- [Entity](#entity)
- [Player](#player)
- [World](#world)
- [Dimension](#dimension)
- [Location](#location)
- [Block](#block)
- [Item](#item)
- [Chunk](#chunk)
- [Biome](#biome)
- [Particle](#particle)
- [Vector](#vector)
- [Potion](#potion)
- [Effect](#effect)
- [Inventory](#inventory)
- [Material](#material)
- [Sound](#sound)
- [Attribute](#attribute)
- [GameMode](#gamemode)
- [BossBar](#bossbar)
- [Scoreboard](#scoreboard)
- [Team](#team)
- [Advancement](#advancement)
- [AdvancementProgress](#advancementprogress)
- [Difficulty](#difficulty)
- [Objective](#objective)
- [Chat](#chat)
- [Raycast](#raycast)
- [RaycastResult](#raycastresult)
- [Enums](#enums)
  - [EntityType](#entitytype)
  - [EffectType](#effecttype)
  - [AttributeType](#attributetype)
  - [BarColor](#barcolor)
  - [BarStyle](#barstyle)

## Event

Base event proxy. Event payloads may expose additional fields depending on event type.

### Attributes

- `block`: [`Block`](#block) — The block involved in the event, if any.
- `chunk`: [`Chunk`](#chunk) — The chunk involved in the event, if any.
- `entity`: [`Entity`](#entity) — The entity involved in the event, if any.
- `inventory`: [`Inventory`](#inventory) — The inventory involved in the event, if any.
- `item`: [`Item`](#item) — The item involved in the event, if any.
- `location`: [`Location`](#location) — The location involved in the event, if any.
- `player`: [`Player`](#player) — The player involved in the event, if any.
- `world`: [`World`](#world) — The world involved in the event, if any.
- `slot`: int — Slot index for inventory click events.

### Methods

- `cancel()` — Cancel the event if it is cancellable. Returns an awaitable that resolves to `None`.

### Chat formatting

For `player_chat` handlers, returning a string will cancel the original chat event and broadcast the returned string instead. Returning `None` (or no return value) leaves chat unchanged.

### Event types

Events are resolved dynamically from handler names using snake_case to PascalCase plus `Event` (for example, `player_join` → `PlayerJoinEvent`).

Supported event types include **all** Bukkit/Paper event classes discoverable in these packages:

- `org.bukkit.event.player.*`
- `org.bukkit.event.block.*`
- `org.bukkit.event.entity.*`
- `org.bukkit.event.inventory.*`
- `org.bukkit.event.server.*`
- `org.bukkit.event.world.*`
- `org.bukkit.event.weather.*`
- `org.bukkit.event.vehicle.*`
- `org.bukkit.event.hanging.*`
- `org.bukkit.event.enchantment.*`
- `org.bukkit.event.*`

Special cases:

- `server_boot` maps to `ServerLoadEvent`.
- `block_explode` is dispatched for both `BlockExplodeEvent` and `EntityExplodeEvent`.

Common examples: `server_boot`, `player_join`, `block_break`, `block_place`, `block_explode`, `entity_explode`, `player_move`, `player_quit`, `player_chat`, `player_interact`, `inventory_click`, `inventory_close`, `entity_damage`, `entity_death`, `world_load`, `world_unload`, `weather_change`.

## Item

Item (ItemStack) API.

### Attributes

- `amount`: int — Item amount.
- `type`: [`Material`](#material) — Item material.
- `name`: str | None — Display name.
- `lore`: list[str] — Lore lines.
- `custom_model_data`: int | None — Custom model data.
- `attributes`: list[dict] — Attribute modifiers.
- `nbt`: dict — Serialized NBT map.

### Methods

- `clone()` — Clone this item. Returns an awaitable that resolves to [`Item`](#item).
- `is_similar(other: [`Item`](#item))` — Check if items are similar. Returns an awaitable that resolves to bool.
- `max_stack_size()` — Get max stack size. Returns an awaitable that resolves to int.
- `set_amount(value: int)` — Set item amount. Returns an awaitable that resolves to `None`.
- `set_name(name: str)` — Set display name. Returns an awaitable that resolves to `None`.
- `set_lore(lore: list[str])` — Set lore. Returns an awaitable that resolves to `None`.
- `set_custom_model_data(value: int)` — Set custom model data. Returns an awaitable that resolves to `None`.
- `set_attributes(attributes: list[dict])` — Set attribute modifiers. Returns an awaitable that resolves to `None`.
- `set_nbt(nbt: dict)` — Set NBT map. Returns an awaitable that resolves to `None`.
- `broadcast(message: str)` — Broadcast a message to all players and console. Returns an awaitable that resolves to `None`.
- `create_boss_bar(title: str, color: [`BarColor`](#barcolor), style: [`BarStyle`](#barstyle))` — Create a boss bar. Returns an awaitable that resolves to [`BossBar`](#bossbar).
- `get_advancement(key: str)` — Get an advancement by namespaced key. Returns an awaitable that resolves to [`Advancement`](#advancement).
- `get_boss_bars()` — Get all boss bars. Returns an awaitable that resolves to a list of [`BossBar`](#bossbar).
- `plugin_manager()` — Get the plugin manager. Returns an awaitable that resolves to a server plugin manager object.
- `players()` — Return the online players. Returns an awaitable that resolves to a list of [`Player`](#player).
- `scoreboard_manager()` — Get the scoreboard manager. Returns an awaitable that resolves to a scoreboard manager object.
- `scheduler()` — Get the server scheduler. Returns an awaitable that resolves to a server scheduler object.
- `wait(ticks: int = 1, after: callable | None = None)` — Wait for ticks then optionally run a callback. Returns an awaitable that resolves to `None`.
- `frame()` — Async context manager that batches calls into one send.
- `atomic()` — Async context manager that batches calls as an atomic group.
- `flush()` — Send all pending batched requests immediately. Returns an awaitable that resolves to `None`.
- `world(name: str)` — Get a world by name. Returns an awaitable that resolves to [`World`](#world).
- `worlds()` — Return all loaded worlds. Returns an awaitable that resolves to a list of [`World`](#world).

## Entity

Base entity proxy.

### Attributes

- `location`: [`Location`](#location) — Current location.
- `type`: [`EntityType`](#entitytype) — Entity type.
- `uuid`: str — Unique id.
- `world`: [`World`](#world) — Current world.

### Methods

- `add_passenger(entity: [`Entity`](#entity))` — Add a passenger. Returns an awaitable that resolves to bool.
- `custom_name()` — Get custom name. Returns an awaitable that resolves to any name value.
- `fire_ticks()` — Get fire ticks. Returns an awaitable that resolves to int.
- `is_dead()` — Check if entity is dead. Returns an awaitable that resolves to bool.
- `is_alive()` — Check if entity is alive. Returns an awaitable that resolves to bool.
- `is_valid()` — Check if entity is valid. Returns an awaitable that resolves to bool.
- `passengers()` — Get passengers. Returns an awaitable that resolves to a list of [`Entity`](#entity).
- `remove()` — Remove the entity. Returns an awaitable that resolves to `None`.
- `remove_passenger(entity: [`Entity`](#entity))` — Remove a passenger. Returns an awaitable that resolves to bool.
- `set_custom_name(name: str)` — Set custom name. Returns an awaitable that resolves to `None`.
- `set_custom_name_visible(value: bool)` — Show/hide custom name. Returns an awaitable that resolves to `None`.
- `set_fire_ticks(ticks: int)` — Set fire ticks. Returns an awaitable that resolves to `None`.
- `set_velocity(vector: [`Vector`](#vector))` — Set velocity vector. Returns an awaitable that resolves to `None`.
- `teleport(location: [`Location`](#location))` — Teleport the entity. Returns an awaitable that resolves to `None`.
- `velocity()` — Get velocity vector. Returns an awaitable that resolves to [`Vector`](#vector).

## Player

`Player` API (inherits [`Entity`](#entity)).

### Constructor

- `Player(uuid: str | None = None, name: str | None = None)` — Resolve a player by UUID or name.

### Attributes

- `food_level`: int — Hunger level.
- `game_mode`: [`GameMode`](#gamemode) — Current game mode.
- `health`: float — Current health.
- `inventory`: [`Inventory`](#inventory) — Player inventory.
- `location`: [`Location`](#location) — Current location.
- `name`: str — Player name.
- `uuid`: str — Unique id.
- `world`: [`World`](#world) — Current world.

### Methods

- `add_effect(effect: [`Effect`](#effect))` — Add an active potion effect. Returns an awaitable that resolves to `None`.
- `chat(message: str)` — Make the player chat a message. Returns an awaitable that resolves to `None`.
- `effects()` — Get active potion effects. Returns an awaitable that resolves to a list of [`Effect`](#effect).
- `exp()` — Get experience progress $0..1$. Returns an awaitable that resolves to float.
- `give_exp(amount: int)` — Give raw experience points. Returns an awaitable that resolves to `None`.
- `has_permission(permission: str)` — Check a permission. Returns an awaitable that resolves to bool.
- `is_alive()` — Check if the player is alive. Returns an awaitable that resolves to bool.
- `add_permission(permission: str, value: bool = True)` — Add or set a permission (LuckPerms-aware). Returns an awaitable that resolves to bool.
- `remove_permission(permission: str)` — Remove a permission (LuckPerms-aware). Returns an awaitable that resolves to bool.
- `permission_groups()` — Get permission groups (LuckPerms-aware). Returns an awaitable that resolves to list of str.
- `primary_group()` — Get primary permission group (LuckPerms-aware). Returns an awaitable that resolves to str or `None`.
- `has_group(group: str)` — Check group membership (LuckPerms-only). Returns an awaitable that resolves to bool.
- `add_group(group: str)` — Add a permission group (LuckPerms-only). Returns an awaitable that resolves to bool.
- `remove_group(group: str)` — Remove a permission group (LuckPerms-only). Returns an awaitable that resolves to bool.
- `is_flying()` — Check if the player is flying. Returns an awaitable that resolves to bool.
- `is_op()` — Check if the player is op. Returns an awaitable that resolves to bool.
- `is_sneaking()` — Check if sneaking. Returns an awaitable that resolves to bool.
- `is_sprinting()` — Check if sprinting. Returns an awaitable that resolves to bool.
- `kick(reason: str = "")` — Kick the player with an optional reason. Returns an awaitable that resolves to `None`.
- `level()` — Get player level. Returns an awaitable that resolves to int.
- `play_sound(sound: [`Sound`](#sound), volume: float = 1.0, pitch: float = 1.0)` — Play a sound to the player. Returns an awaitable that resolves to `None`.
- `remove_effect(effect_type: [`EffectType`](#effecttype))` — Remove a potion effect by type. Returns an awaitable that resolves to `None`.
- `scoreboard()` — Get the player's scoreboard. Returns an awaitable that resolves to [`Scoreboard`](#scoreboard).
- `send_action_bar(message: str)` — Send an action bar message. Returns an awaitable that resolves to `None`.
- `send_message(message: str)` — Send a chat message to the player. Returns an awaitable that resolves to `None`.
- `send_title(title: str, subtitle: str = "", fade_in: int = 10, stay: int = 70, fade_out: int = 20)` — Send a title/subtitle to the player. Returns an awaitable that resolves to `None`.
- `set_exp(exp: float)` — Set experience progress $0..1$. Returns an awaitable that resolves to `None`.
- `set_fly_speed(speed: float)` — Set flying speed. Returns an awaitable that resolves to `None`.
- `set_flying(value: bool)` — Set flying state. Returns an awaitable that resolves to `None`.
- `set_food_level(level: int)` — Set hunger level. Returns an awaitable that resolves to `None`.
- `set_game_mode(mode: [`GameMode`](#gamemode))` — Set the player's game mode. Returns an awaitable that resolves to `None`.
- `set_health(health: float)` — Set player health. Returns an awaitable that resolves to `None`.
- `set_level(level: int)` — Set player level. Returns an awaitable that resolves to `None`.
- `set_op(value: bool)` — Set op status. Returns an awaitable that resolves to `None`.
- `set_scoreboard(scoreboard: [`Scoreboard`](#scoreboard))` — Set the player's scoreboard. Returns an awaitable that resolves to `None`.
- `set_sneaking(value: bool)` — Set sneaking state. Returns an awaitable that resolves to `None`.
- `set_sprinting(value: bool)` — Set sprinting state. Returns an awaitable that resolves to `None`.
- `set_walk_speed(speed: float)` — Set walking speed. Returns an awaitable that resolves to `None`.
- `teleport(location: [`Location`](#location))` — Teleport the player to a location. Returns an awaitable that resolves to `None`.

## World

`World` API.

### Attributes

- `environment`: any — World environment value.
- `name`: str — World name.
- `uuid`: str — Unique id.

### Methods

- `block_at(x: int, y: int, z: int)` — Get a block at coordinates. Returns an awaitable that resolves to [`Block`](#block).
- `chunk_at(x: int, z: int)` — Get a chunk by coordinates. Returns an awaitable that resolves to [`Chunk`](#chunk).
- `difficulty()` — Get world difficulty. Returns an awaitable that resolves to [`Difficulty`](#difficulty).
- `full_time()` — Get full world time. Returns an awaitable that resolves to int.
- `has_storm()` — Check if storming. Returns an awaitable that resolves to bool.
- `is_thundering()` — Check if thundering. Returns an awaitable that resolves to bool.
- `play_sound(location: [`Location`](#location), sound: [`Sound`](#sound), volume: float = 1.0, pitch: float = 1.0)` — Play a sound at a location. Returns an awaitable that resolves to `None`.
- `players()` — Get players in this world. Returns an awaitable that resolves to a list of [`Player`](#player).
- `set_difficulty(difficulty: [`Difficulty`](#difficulty))` — Set world difficulty. Returns an awaitable that resolves to `None`.
- `set_full_time(time: int)` — Set full world time. Returns an awaitable that resolves to `None`.
- `set_spawn_location(location: [`Location`](#location))` — Set world spawn location. Returns an awaitable that resolves to `None`.
- `set_storm(value: bool)` — Set storming. Returns an awaitable that resolves to `None`.
- `set_thunder_duration(ticks: int)` — Set thunder duration. Returns an awaitable that resolves to `None`.
- `set_thundering(value: bool)` — Set thundering. Returns an awaitable that resolves to `None`.
- `set_time(time: int)` — Set world time. Returns an awaitable that resolves to `None`.
- `set_weather_duration(ticks: int)` — Set weather duration. Returns an awaitable that resolves to `None`.
- `spawn(location: [`Location`](#location), entity_cls: type)` — Spawn an entity by class. Returns an awaitable that resolves to [`Entity`](#entity).
- `spawn_entity(location: [`Location`](#location), entity_type: [`EntityType`](#entitytype))` — Spawn an entity by type. Returns an awaitable that resolves to [`Entity`](#entity).
- `spawn_location()` — Get world spawn location. Returns an awaitable that resolves to [`Location`](#location).
- `spawn_particle(particle: [`Particle`](#particle), location: [`Location`](#location), count: int = 1, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0)` — Spawn particles in the world. Returns an awaitable that resolves to `None`.
- `strike_lightning(location: [`Location`](#location))` — Strike lightning at a location. Returns an awaitable that resolves to [`Entity`](#entity).
- `strike_lightning_effect(location: [`Location`](#location))` — Strike lightning effect at a location. Returns an awaitable that resolves to `None`.
- `thunder_duration()` — Get thunder duration. Returns an awaitable that resolves to int.
- `time()` — Get world time. Returns an awaitable that resolves to int.
- `weather_duration()` — Get weather duration. Returns an awaitable that resolves to int.

## Dimension

`Dimension` proxy.

### Attributes

- `name`: str — Dimension name.

### Methods

None.

## Location

Location in a world with yaw and pitch.

### Attributes

- `pitch`: float — Pitch angle.
- `world`: [`World`](#world) — World reference.
- `x`: float — X coordinate.
- `y`: float — Y coordinate.
- `yaw`: float — Yaw angle.
- `z`: float — Z coordinate.

### Methods

- `add(x: float, y: float, z: float)` — Add coordinates to this location. Returns an awaitable that resolves to [`Location`](#location).
- `clone()` — Clone this location. Returns an awaitable that resolves to [`Location`](#location).
- `distance(other: [`Location`](#location))` — Distance to another location. Returns an awaitable that resolves to float.
- `distance_squared(other: [`Location`](#location))` — Squared distance to another location. Returns an awaitable that resolves to float.
- `set_world(world: [`World`](#world))` — Set the world reference. Returns an awaitable that resolves to `None`.

## Block

Block in the world.

### Attributes

- `location`: [`Location`](#location) — Block location.
- `type`: [`Material`](#material) — Block material.
- `world`: [`World`](#world) — World reference.
- `x`: int — X coordinate.
- `y`: int — Y coordinate.
- `z`: int — Z coordinate.

### Methods

- `biome()` — Get biome. Returns an awaitable that resolves to [`Biome`](#biome).
- `break_naturally()` — Break the block naturally. Returns an awaitable that resolves to `None`.
- `data()` — Get block data. Returns an awaitable that resolves to any block data value.
- `is_solid()` — Check if block is solid. Returns an awaitable that resolves to bool.
- `light_level()` — Get light level. Returns an awaitable that resolves to int.
- `set_biome(biome: [`Biome`](#biome))` — Set biome. Returns an awaitable that resolves to `None`.
- `set_data(data: any)` — Set block data. Returns an awaitable that resolves to `None`.
- `set_type(material: [`Material`](#material))` — Set the block type. Returns an awaitable that resolves to `None`.

## Item

Item (ItemStack) API.

### Attributes

- `amount`: int — Stack amount.
- `type`: [`Material`](#material) — Item material.
- `name`: str | None — Display name.
- `lore`: list[str] — Lore lines.
- `custom_model_data`: int | None — Custom model data.
- `attributes`: list[dict] — Attribute modifiers.
- `nbt`: dict — Serialized NBT map.

### Methods

- `clone()` — Clone this item. Returns an awaitable that resolves to [`Item`](#item).
- `is_similar(other: [`Item`](#item))` — Check if items are similar. Returns an awaitable that resolves to bool.
- `max_stack_size()` — Get max stack size. Returns an awaitable that resolves to int.
- `set_amount(value: int)` — Set item amount. Returns an awaitable that resolves to `None`.
- `set_name(name: str)` — Set display name. Returns an awaitable that resolves to `None`.
- `set_lore(lore: list[str])` — Set lore. Returns an awaitable that resolves to `None`.
- `set_custom_model_data(value: int)` — Set custom model data. Returns an awaitable that resolves to `None`.
- `set_attributes(attributes: list[dict])` — Set attribute modifiers. Returns an awaitable that resolves to `None`.
- `set_nbt(nbt: dict)` — Set NBT map. Returns an awaitable that resolves to `None`.

## Chunk

Chunk of a world (loadable/unloadable).

### Attributes

- `world`: [`World`](#world) — World reference.
- `x`: int — Chunk X coordinate.
- `z`: int — Chunk Z coordinate.

### Methods

- `is_loaded()` — Check if the chunk is loaded. Returns an awaitable that resolves to bool.
- `load()` — Load the chunk. Returns an awaitable that resolves to bool.
- `unload()` — Unload the chunk. Returns an awaitable that resolves to bool.

## Biome

Minecraft biome enum proxy, such as plains, void, ice_spikes.

### Attributes

None.

### Methods

None.

## Particle

Particle enum proxy.

### Attributes

None.

### Methods

None.

## Vector

Basic Vec3.

### Attributes

- `x`: float — X component.
- `y`: float — Y component.
- `z`: float — Z component.

### Methods

None.

## Potion

Potion API (legacy).

### Attributes

None.

### Methods

- `level()` — Get potion level. Returns an awaitable that resolves to int.
- `type()` — Get potion type. Returns an awaitable that resolves to any potion type value.

## Effect

Active potion effect.

### Constructor

- `Effect(effect_type: EffectType | str, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True)` — Create a value effect.

### Attributes

- `ambient`: bool — Whether the effect is ambient.
- `amplifier`: int — Effect amplifier.
- `duration`: int — Effect duration in ticks.
- `icon`: bool — Whether the effect has an icon.
- `particles`: bool — Whether the effect has particles.
- `type`: [`EffectType`](#effecttype) — Effect type.

### Methods

- `with_amplifier(amplifier: int)` — Return a copy with a different amplifier. Returns an awaitable that resolves to [`Effect`](#effect).
- `with_duration(duration: int)` — Return a copy with a different duration. Returns an awaitable that resolves to [`Effect`](#effect).

## Inventory

Inventory. Can belong to an entity or block entity, or exist as a standalone open inventory screen.

### Constructor

- `Inventory(size: int = 9, title: str = "", contents: list[Item] | None = None)` — Create a value inventory.

### Attributes

- `contents`: list of [`Item`](#item) — Inventory contents.
- `holder`: any — Inventory holder.
- `size`: int — Inventory size.
- `title`: str — Inventory title.

### Methods

- `add_item(item: [`Item`](#item))` — Add an item to the inventory. Returns an awaitable that resolves to any add result.
- `clear()` — Clear inventory contents. Returns an awaitable that resolves to `None`.
- `close(player: [`Player`](#player) | None = None)` — Close this inventory for a player. Returns an awaitable that resolves to `None`.
- `contains(material: [`Material`](#material), amount: int = 1)` — Check if inventory contains a material. Returns an awaitable that resolves to bool.
- `first_empty()` — Get first empty slot index. Returns an awaitable that resolves to int.
- `get_item(slot: int)` — Get item in a slot. Returns an awaitable that resolves to [`Item`](#item).
- `open(player: [`Player`](#player))` — Open this inventory for a player. Returns an awaitable that resolves to any open result.
- `remove_item(item: [`Item`](#item))` — Remove an item from the inventory. Returns an awaitable that resolves to any remove result.
- `set_item(slot: int, item: [`Item`](#item))` — Set item in a slot. Returns an awaitable that resolves to `None`.

## Material

Material enum proxy, such as diamond, netherite, wood.

### Constructor

- `Material(name: str)` — Create a material enum value (case-insensitive).

### Attributes

None.

### Methods

None.

## Sound

Sound enum proxy.

### Attributes

None.

### Methods

None.

## Attribute

Attribute instance for a living entity.

### Attributes

None.

### Methods

- `attribute_type()` — Get the attribute type. Returns an awaitable that resolves to [`AttributeType`](#attributetype).
- `base_value()` — Get base value. Returns an awaitable that resolves to float.
- `set_base_value(value: float)` — Set base value. Returns an awaitable that resolves to `None`.
- `value()` — Get attribute value. Returns an awaitable that resolves to float.

## GameMode

Game mode enum proxy.

### Attributes

None.

### Methods

None.

## BossBar

Boss bar API.

### Attributes

None.

### Methods

- `add_player(player: [`Player`](#player))` — Add a player to the boss bar. Returns an awaitable that resolves to `None`.
- `color()` — Get bar color. Returns an awaitable that resolves to [`BarColor`](#barcolor).
- `progress()` — Get progress $0..1$. Returns an awaitable that resolves to float.
- `remove_player(player: [`Player`](#player))` — Remove a player from the boss bar. Returns an awaitable that resolves to `None`.
- `set_color(color: [`BarColor`](#barcolor))` — Set bar color. Returns an awaitable that resolves to `None`.
- `set_progress(value: float)` — Set progress $0..1$. Returns an awaitable that resolves to `None`.
- `set_style(style: [`BarStyle`](#barstyle))` — Set bar style. Returns an awaitable that resolves to `None`.
- `set_title(title: str)` — Set title. Returns an awaitable that resolves to `None`.
- `set_visible(value: bool)` — Set visibility. Returns an awaitable that resolves to `None`.
- `style()` — Get bar style. Returns an awaitable that resolves to [`BarStyle`](#barstyle).
- `title()` — Get title. Returns an awaitable that resolves to str.
- `visible()` — Check visibility. Returns an awaitable that resolves to bool.

## Scoreboard

Scoreboard API.

### Attributes

None.

### Methods

- `clear_slot(slot: any)` — Clear display slot. Returns an awaitable that resolves to `None`.
- `get_objective(name: str)` — Get an objective by name. Returns an awaitable that resolves to [`Objective`](#objective).
- `get_team(name: str)` — Get a team by name. Returns an awaitable that resolves to [`Team`](#team).
- `objectives()` — Get all objectives. Returns an awaitable that resolves to a list of [`Objective`](#objective).
- `register_objective(name: str, criteria: str, display_name: str = "")` — Register a new objective. Returns an awaitable that resolves to [`Objective`](#objective).
- `register_team(name: str)` — Register a new team. Returns an awaitable that resolves to [`Team`](#team).
- `teams()` — Get all teams. Returns an awaitable that resolves to a list of [`Team`](#team).

## Team

Team API.

### Attributes

None.

### Methods

- `add_entry(entry: str)` — Add an entry to the team. Returns an awaitable that resolves to `None`.
- `color()` — Get team color. Returns an awaitable that resolves to any color value.
- `entries()` — Get team entries. Returns an awaitable that resolves to a set of str.
- `remove_entry(entry: str)` — Remove an entry from the team. Returns an awaitable that resolves to `None`.
- `set_color(color: any)` — Set team color. Returns an awaitable that resolves to `None`.
- `set_prefix(prefix: str)` — Set team prefix. Returns an awaitable that resolves to `None`.
- `set_suffix(suffix: str)` — Set team suffix. Returns an awaitable that resolves to `None`.

## Advancement

Advancement API.

### Attributes

None.

### Methods

- `key()` — Get the advancement key. Returns an awaitable that resolves to any key value.

## AdvancementProgress

Advancement progress API.

### Attributes

None.

### Methods

- `award_criteria(name: str)` — Award a criterion. Returns an awaitable that resolves to bool.
- `awarded_criteria()` — Get awarded criteria. Returns an awaitable that resolves to a set of str.
- `is_done()` — Check if completed. Returns an awaitable that resolves to bool.
- `remaining_criteria()` — Get remaining criteria. Returns an awaitable that resolves to a set of str.
- `revoke_criteria(name: str)` — Revoke a criterion. Returns an awaitable that resolves to bool.


## Difficulty

World difficulty enum proxy.

### Attributes

None.

### Methods

None.

## Objective

Objective API.

### Attributes

None.

### Methods

- `criteria()` — Get objective criteria. Returns an awaitable that resolves to str.
- `display_slot()` — Get display slot. Returns an awaitable that resolves to any slot value.
- `get_score(entry: str)` — Get a score for an entry. Returns an awaitable that resolves to any score object.
- `name()` — Get objective name. Returns an awaitable that resolves to str.
- `set_display_name(name: str)` — Set display name. Returns an awaitable that resolves to `None`.
- `set_display_slot(slot: any)` — Set display slot. Returns an awaitable that resolves to `None`.

## Chat

Chat helper API.

### Methods

- `broadcast(message: str)` — Broadcast a chat message to all players and console. Returns an awaitable that resolves to `None`.

## Raycast

Raycast helpers.

### Methods

- `raycast(world, start, direction, max_distance=64.0, ray_size=0.2, include_entities=True, include_blocks=True, ignore_passable=True)` — Raycast in a world. `world` can be a world object or name. `direction` is a `(yaw, pitch)` tuple. Returns an awaitable that resolves to a [`RaycastResult`](#raycastresult) or `None` when no hit.

## RaycastResult

Raycast result data.

### Attributes

- `x`, `y`, `z`: float — Hit position.
- `entity`: [`Entity`](#entity) | None — Hit entity.
- `block`: [`Block`](#block) | None — Hit block.
- `start_x`, `start_y`, `start_z`: float — Start position.
- `yaw`, `pitch`: float — Direction angles used for the ray.

## Enums

## EntityType

Entity type enum proxy.

## EffectType

Potion effect type enum proxy, such as poison, regeneration, strength.

## AttributeType

Attribute type enum proxy, such as movement speed or base attack damage.

## BarColor

Boss bar color enum proxy.

## BarStyle

Boss bar style enum proxy.
