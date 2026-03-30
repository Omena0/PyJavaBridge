
# Changelog

## 4A

Major release: first-class client-side integration, an experimental datapack runtime, improved bridge reliability and player-data handling, documentation and configuration enhancements, and packaging updates.

### Highlights

- Client-mod integration: optional, bidirectional server↔client protocol with session management and permission negotiation enabling richer client-side features.
- Datapack runtime (experimental): in-memory datapack registration for models, advancements, predicates and registry entries without writing resource files.
- Player-data & reliability: more reliable UUID/name resolution, safer lifecycle/reconnect handling, and improved field caching.
- Documentation & examples: new clientmod and datapack guides, updated examples, and improved docs site.
- Configuration & deployment: new options for timeouts, message size limits, and Python runtime path.
- Packaging & tooling: build and packaging updates to support client features.
- Stability fixes: targeted crash and edge-case fixes, and cleanup of lifecycle races.

### User-facing changes (summary)

- Client mod support
  - Adds an optional client-side bridge allowing server scripts and plugins to send commands and structured data to a cooperating client mod and receive responses/events.
  - Permission negotiation occurs at session start; scripts must handle availability, denials, and timeouts gracefully.

- Datapack runtime (experimental)
  - API to register datapack content (models, advancements, predicates, registry entries) at runtime; best-effort and intended for dynamic/testing scenarios.

- Configuration
  - New configuration keys for message size, timeouts, and Python runtime; review settings for production deployment.

## 3D

Performance overhaul — fire-and-forget calls, msgpack wire protocol, field cache invalidation, and reduced serialization payload.

### Changes

#### Fire-and-Forget Calls

- Added `call_fire_forget()` to `BridgeConnection` — sends calls with `no_response: true`, skipping Future creation and await
- Added `_call_ff()` to `ProxyBase` — convenience wrapper for fire-and-forget bridge calls
- Java `handleCall()` checks `no_response` flag and skips result serialization + response sending
- Java `executeBatchCalls()` supports `no_response` per-call in both atomic and non-atomic batch paths
- Converted ~80+ void/setter methods on Entity and Player to fire-and-forget:
  - Entity: `teleport`, `remove`, velocity setter, `fire_ticks` setter, `add_passenger`/`remove_passenger`, `custom_name` setter, gravity/glowing/invisible/invulnerable/silent/persistent/collidable setters, `portal_cooldown`/`freeze_ticks` setters, `eject`, `leave_vehicle`, `set_rotation`
  - Entity (Mob): `target` setter, `is_aware` setter, `stop_pathfinding`, `remove_all_goals`
  - Player: `damage`, `send_message`, `chat`, `kick`, `give_exp`, `add_effect`/`remove_effect`, `set_game_mode`, `set_scoreboard`, `set_op`, `play_sound`, `send_action_bar`, `send_title`, tab list setters, health/food/level/exp setters, flying/sneaking/sprinting setters, walk/fly speed setters, `send_resource_pack`, absorption/saturation/exhaustion setters, `allow_flight` setter, `hide_player`/`show_player`, `open_book`, `send_block_change`, `send_particle`, `set_cooldown`, `set_statistic`, `max_health` setter, `bed_spawn_location`/`compass_target` setters, `set_persistent_data`

#### Field Cache Invalidation

- Added `_invalidate_field()` to `ProxyBase` — removes cached field values so next access fetches fresh data from Java
- Setters that modify cached values call `_invalidate_field()` before sending the fire-and-forget call, preventing desync:
  - `teleport` → invalidates `location`, `world`
  - `give_exp` → invalidates `exp`, `level`
  - `set_game_mode` → invalidates `gameMode`, `game_mode`
  - `set_health` → invalidates `health`
  - `set_food_level` → invalidates `foodLevel`, `food_level`
  - `level` setter → invalidates `level`
  - `exp` setter → invalidates `exp`
  - `max_health` setter → invalidates `health`

#### Reduced Serialization Payload

- Removed `inventory` from Player auto-serialization in `BridgeSerializer` — inventory is now fetched on demand instead of included in every Player object

#### Msgpack Wire Protocol

- Python: 3-tier serialization import chain — msgpack → orjson → stdlib json
- Python: handshake message sent as JSON on connect to negotiate format with Java
- Java: `handleHandshake()` switches `useMsgpack` flag on format negotiation
- Java: `serializePayload()`/`deserializePayload()` helper methods convert JsonObject ↔ msgpack at IPC boundaries
- Java: full msgpack ↔ Gson `JsonElement` tree conversion (`unpackValue`, `packJsonElement`) handling all types (nil, bool, int, float, string, binary, array, map)
- Java: `bridgeLoop()`, `send()`, `sendAll()`, `sendWithTiming()` all route through format-aware helpers
- Build: added `com.gradleup.shadow` plugin, `org.msgpack:msgpack-core:0.9.8` shaded and relocated to `com.pyjavabridge.libs.msgpack`
- `copyPluginJar` and `copyReleaseJar` tasks updated to depend on `shadowJar`

#### Bug Fixes

- Fixed stray `return self._call_sync(method)` in `_invalidate_field` that would have crashed on every call

## 3C

Plugging some old holes in the API. Full codebase cleanup. New extensions.

### Changes

#### New Extensions

- LootTable: weighted loot pools with conditional entries, rolls, bonus rolls, and stacked item generation
- PlaceholderRegistry: register `%placeholder%` expansions with per-player context and batch `resolve_many()`
- TabList: full tab-list customization with header/footer templates, fake entries, groups with prefix/priority sorting
- Scheduler: cron-like real-world-time scheduling with `@every()` / `@after()` decorators and cancellation
- StateMachine: per-entity/player state machines with `on_enter`/`on_exit`/`on_tick` callbacks and event-driven transitions
- Schematic: extracted from Dungeon into standalone module (SchematicCapture.java + schematic.py)

#### New APIs

- `@preserve` decorator: hot-reload state persistence — caches return value to JSON and restores across `/pjb reload`
- Custom events: `fire_event(event_name, data)` — scripts can fire and listen to custom events across scripts
- Villager trade API: `Villager.recipes` (get/set), `recipe_count`, `add_recipe()`, `clear_recipes()`
- Entity subtypes: ArmorStand, Villager, ItemFrame, FallingBlock, AreaEffectCloud proxy classes
- Entity properties: `velocity`, `fire_ticks`, `custom_name`, `gravity`, `glowing`, `invisible`, `invulnerable`, `silent`, `persistent`, `collidable`, `bounding_box`, `metadata`
- Entity AI goals: `goal_types`, `remove_goal()`, `remove_all_goals()`
- Player: `hidePlayer`/`showPlayer`/`canSee`, `openBook`, `sendBlockChange`, `sendParticle`, cooldown management, statistics, `getMaxHealth`/`setMaxHealth`, bed spawn, compass target, PersistentDataContainer access
- Block: `getDrops`, `getHardness`, `getBlastResistance`, PersistentDataContainer for tile entities
- Item: durability, enchantments, item flags, `isUnbreakable`/`setUnbreakable`
- World: game rules, world border, `getHighestBlockAt`, `generateTree`, `getNearbyEntities`, `batchSpawn`, structure API (`save`/`load`/`delete`/`list`), `createWorld`/`deleteWorld`
- `Entity.__bool__()` via `isValid()`

#### Refactoring & Code Quality

- Comprehensive docstrings added across all Python modules and extensions
- Whitespace normalization and consistent spacing across Python source
- Type annotations tightened: lazy imports, Optional callables, assertion guards
- `str.removeprefix()` modernization replacing `startswith()` + slice
- `server.players` de-awaited in guild, leaderboard, npc, region (was incorrectly `await`ed)
- `@preserve` event handlers fixed: lambdas replaced with proper async def functions
- Gradle deprecation linting enabled: `-Xlint:deprecation`
- Gradle wrapper (8.5) added and committed

#### Optimizations — Java

- BridgeInstance: 24 pre-sized ArrayList/HashMap allocations (completions, handles, release ids, batch calls, responses, args, tab complete results, merchant recipe ingredients, sign lines, goal types, recipes, lore, item flags, structures, enchantments, spawn batches, tab list setter, process command)
- BridgeInstance: `getDrops` → `List.copyOf()`, `clearRecipes` → `List.of()`
- BridgeSerializer: stream→manual loop for list serialization, 6 pre-sized ArrayList/HashMap allocations, early `List.of()` return for null modifiers
- SchematicCapture: 11 pre-sized collections (HashMap, LinkedHashMap, ArrayList, HashSet), 3 stream→manual loop conversions (sum, sort)
- EventDispatcher: simplified `getCachedMethod()`, pre-sized lists in `dispatchBlockMulti()`
- ScriptCommand, PermissionsFacade, RaycastFacade, RegionFacade, EntitySpawner: pre-sized result collections

#### Optimizations — Python

- `_ENUM_TYPE_MAPPING` moved to module-level constant (was recreated on every enum deserialization)
- `_JSON_SEPARATORS`, `_RESERVED_KWARGS` frozenset, `_MINECRAFT_PREFIXES` tuple: module-level constants
- `event_batch` handler inlined: avoids temp dict creation and full re-dispatch per payload
- XYZ key check: direct `"x" in d` instead of `frozenset.issubset(d.keys())`
- `import math` / `import logging` moved to module-level
- `__slots__` added to 27 classes across helpers and extensions
- NPC: squared distance comparison, cached NPC coords outside player loop
- Region: batch-fetch all player locations once per tick, inline bounds check
- Mana: cached instance attributes as locals in regen loop
- Bank: inlined `transfer()` to avoid double `_save()`
- Levels: eliminated double xp lookup in `add_xp`, `xp_to_next`/`progress` avoid redundant bridge call
- Ability: inlined `remaining_cooldown` to avoid double `time.time()` + double dict lookup
- Leaderboard: tuple-based medal lookup
- Quest: cached locals in async task loops
- Guild: cached member set reference and pre-formatted message
- Cooldown: single `.get()` lookup instead of `in` + `[]`
- `_toml_write_table()`: single-pass scalar/sub-table separation
- UUID cache eviction: indexed deletion instead of slice allocation

#### Bug Fixes

- Fixed `server.players` incorrectly awaited in guild, leaderboard, npc, region
- Fixed `@preserve` event handler signature (lambda → async def)
- Fixed `setLore` NPE when argument is not a list (added else branch with `List.of()`)

#### Documentation & Tooling

- Docs updated for all new extensions (LootTable, Placeholder, TabList, Scheduler, StateMachine)
- Villager trade API documented
- Type stubs updated for all new APIs and extensions
- Gradle wrapper committed

## 3B

Performance optimization pass — caching, data structures, and hot-path improvements across Java and Python.

### Changes

#### Java — Reflection & Caching

- Cache `getMethods()` per class in `BridgeInstance` and `RefFacade` — avoids repeated reflection on every reflective invoke
- Cache NMS reflection handles (`parseTag`, `getHandle`, `spawnNonLivingNms` helpers) in `EntitySpawner` static fields
- Cache LuckPerms API instance and `Node`/`InheritanceNode` class objects in `PermissionsFacade`
- Cache resolved event classes across 13 Bukkit packages in `EventSubscription` — avoids repeated `Class.forName()` for known events
- Build static `Map<String, PacketType>` lookup tables in `PacketBridge` — O(1) packet type resolution
- Merge dual method+miss cache into single `ConcurrentHashMap<String, Optional<Method>>` in `EventDispatcher` and `BridgeSerializer`
- Cache `getLogicalTypeName()` per concrete class in `BridgeSerializer` — avoids repeated instanceof chains on every serialize

#### Java — Serialization & I/O

- ThreadLocal `ByteArrayOutputStream` for `send()` — avoids allocation per outgoing message
- ThreadLocal identity-hash set for cyclic reference detection in `serialize()` — reused across calls
- New `sendAll()` method batches multiple responses under a single lock + flush for batch/frame calls
- ItemStack meta: call `displayName()`/`lore()` once with null check instead of `has*()`+`get*()` pairs
- Shallow top-level entry copy instead of `deepCopy()` for per-block event payloads in `EventDispatcher`
- Reduce per-pixel overhead in `spawnImagePixels` — single `get()` + null check replaces `has()`+`get()` pairs

#### Java — Data Structures & Dispatch

- `BridgeInstance.invoke()`: else-if dispatch chain replaces sequential instanceof checks — first match wins
- `ObjectRegistry`: `StampedLock` replaces `synchronized` block — lock-free reads via `ConcurrentHashMap`, write lock only for register/release
- `DebugManager`: `CopyOnWriteArraySet` replaces `synchronizedSet` — writes are rare (toggle), reads (broadcast) are frequent
- `PlayerUuidResolver`: static `HttpClient` singleton, LRU eviction via `LinkedHashMap`, cached `usercache.json` parse with timestamp
- `ScriptCommand`: pre-lowercase tab completions at registration — avoids `toLowerCase()` on every keystroke
- `EventSubscription.lastDispatchNano` marked `volatile` for safe cross-thread reads
- Expanded thread-safe method sets for `Server`, `OfflinePlayer`, and `Entity` — more calls skip main-thread dispatch
- Static empty `JsonObject` sentinel for missing `args` in `invoke()`

#### Python — Connection & Dispatch

- Lazy module-level imports in `connection.py` — `_ensure_lazy_imports()` populates references once, avoids per-call `import`/`from` overhead
- Single-handler fast path in `_dispatch_event` — when only 1 handler, directly call+await without list/gather overhead
- `_build_call_message()` extracted — shared between `call()` and `call_sync()`, eliminates duplicated message construction
- Release queue changed from `list` to `set` — O(1) `discard()` replaces O(n) `list.remove()`
- `_maybe_flush_releases()` avoids unnecessary flushes on every call — only flushes when queue ≥ 16
- `_read_exact()` optimistic fast path — single `os.read()` often returns full message, skips `bytearray` accumulation
- `send()` writes header+data in one `write()` call instead of two

#### Python — Proxy & Types

- Lazy module-level dispatch table for `_proxy_from()` — suffix/contains lookup tables built once, avoids per-call dict literal and import
- Handle-first fast path in `ProxyBase.__eq__` — same handle means same Java object, skip field comparison
- `EnumValue.from_name()` dict cache — returns cached instances for repeated enum lookups
- Bounded `_player_uuid_cache` (max 1000, evict oldest quarter) in both `wrappers.py` and `utils.py`
- Consolidated `isinstance` checks in `decorators.py` command wrapper — merged two separate branches into one

#### Python — Helpers

- `State._instances` uses `weakref.ref` — allows garbage collection of unreferenced State objects
- Shutdown handler updated to dereference weakrefs

## 3A

Major expansion — extensions, tooling, networking overhaul.
Many internal changes, cleanup and optimization.

### Changes

#### Networking

- Switched from TCP sockets to stdin/stdout pipes for faster IPC
- Java-side method resolution now supports snake_case → camelCase fallback
- Version compatibility improvements and removed slow regex

#### New APIs

- Entity AI: targeting, pathfinding, awareness, line of sight, look_at
- Entity tags: add_tag, remove_tag, tags, is_tagged (Python-side, UUID-keyed)
- Entity attributes: yaw, pitch, look_direction, equipment
- Player: selected_slot, freeze/unfreeze (tick-based position lock), vanish/unvanish
- Player extension shortcuts: balance, deposit, withdraw, mana, xp, player_level
- Block/tile entity API: signs, furnaces, containers
- Recipe API: shaped, shapeless, furnace recipes as a class
- Firework effects API with builder pattern
- Resource pack API on Player
- Enchantment discovery: Enchantment.all() and Enchantment.for_item()
- Packet API via ProtocolLib: on_packet_send, on_packet_receive, send_packet
- Inter-script messaging: script_send, on_script_message, get_scripts
- WorldTime class and @world.at_time() decorator for time-based events
- World: create_explosion, entities_near, blocks_near
- Location: + and - operators (with Location and Vector)
- Vector: +, -, * operators (scalar, component-wise, and reverse)
- 18 new enum types (DamageCause, Enchantment, ItemFlag, etc)
- Respawn location override (return Location from player_respawn)
- entity_target event return value handling: override target by returning Entity
- @event .unregister() method to remove event handlers at runtime

#### New extensions

- Paginator: multi-page menu with nav buttons
- Quest / QuestTree: objectives, bossbar timers, branching quest lines
- Dialog: branching conversations with timeouts and NPC linking
- Bank: persistent balances with transaction events
- Shop: paginated GUI with bank integration
- TradeWindow: confirm/cancel with anti-dupe delay
- Ability / ManaStore / CombatSystem / LevelSystem
- Region / Party / Guild / CustomItem
- Leaderboard / VisualEffect / PlayerDataStore
- Dungeon: procedural room generation with WFC algorithm

#### Decorators & commands

- @command: cmd\_ prefix auto-stripping (def cmd_greet → /greet)
- @command: dynamic tab completions via @my_command.tab_complete
- @command: static tab_complete parameter with wildcard support
- Persistent State class with auto-save on shutdown

#### Event system

- Extended event payload: action, hand, from, to, cause, velocity, reason, message, new_slot, previous_slot, amount, slot, etc
- Event.world and Event.location now auto-derive from entity/player when not directly available
- snake_case field access auto-resolves to Java getters (getNewSlot, isPreviousSlot, etc)

#### Error handling

- Java stack traces included in Python exceptions
- 18 typed error subclasses (EntityGoneException, MethodNotFoundException, etc)

#### Helpers

- Menu: race condition fix when opening a new menu from a click handler
- ActionBarDisplay: immediate refresh on creation (no longer waits for server_boot)
- BossBarDisplay: renamed link_cooldown to linked_to (old name kept as compat alias)
- ManaStore: auto-cleanup on player disconnect, regen loop crash protection
- NPC: dialog linking, player linking, range enter/exit callbacks

#### Tooling

- `pjb` CLI tool: `pjb search <query>` and `pjb events [filter]`
- Doc site full-text search bar with Ctrl+K shortcut
- Gradle copyBridgePython task: auto-deploys bridge to server on build

#### Internals

- Restructured bridge.py into proper Python module (connection, wrappers, helpers, types, utils, decorators)
- Documentation for events, execution, lifecycle, and serialization internals
- Type stubs for all extensions
- Comprehensive Event stubs with all event-specific fields

#### Misc

- MeshDisplay helper (WIP)
- Updated wiki/docs site with all new pages

## 2A

Feature update

### Changes

#### Networking

- Optimized for single request latency
- Use batching to speed up multiple requests
- Now uses orjson for faster parsing
- Automatic handle management

#### New APIs

- Tab list API on Player
- Region utils on World: .set_block, .fill, .replace, .fill_sphere, .fill_cylinder, .fill_line
- Particle shapes on World
- Entity spawn helpers on World: spawn_at_player, spawn_projectile, spawn_with_nbt.
- Support for command execution on Server
- world.entities property
- RaycastResult.distance and .hit_face

#### New helpers

- Sidebar: Scoreboard helper
- Config: TOML config helper
- Cooldown: Automatically manage cooldowns
- Hologram: Show floating text
- Menu / MenuItem: Create easy chest GUIs
- ActionBarDisplay: Manage action bars easily
- BossBarDisplay: Manage boss bars easily
- BlockDisplay: Show fake blocks
- ItemDisplay: Show floating items
- ImageDisplay: Show images in the world
- ItemBuilder: Easily create items
- Shutdown event

#### API improvements

- Fixed type errors regarding EnumValue not matching its child classes
- EntityGoneException now extends BridgeError
- @task decorator: Run tasks on an interval
- Added event priority and throttle_ms parameters
- Added command description parameter
- Location: .add, .clone, .distance, .distance_squared are now sync
- Scoreboard, Team, Objective, and BossBar creation methods are now sync
- Config: Added support for multiple formats, toml (default), json, and properties.
- Commands can be now executes as console

#### Cleanup

- Entity class moved before Player
- Moved most of the code from a single file to multiple
- Improved typing across python bridge

#### Misc

- Added dev versioning for non-release commits
- Added wiki site

## 1D

Damage event

Changes:

- Added damage override to damage events
- Added damage source and damager attributes to damage events
- Added shooter attribute to projectile entities
- Added owner attribute to tamed entities
- Added is_tamed attribute to entities

## 1C

API cleanup

Changes:

- Added call_sync and field_or_call_sync helpers
- Turned most attribute-like methods into attributes
- Made all attributes synchronous
- Added create classmethods to most classes
- Added optional args to world.spawn_entity
- Allowed spawning of non-living entities
- Fixed player UUID lookups
- Chat event return value is now the chat message format for that event
- Bugfixes

## 1B

API expansion

Changes:

- Implemented most missing APIs
- Added proper command argument parsing
- Added docs
- Bugfixes

## 1A

Initial release

Changes:

- Added most common APIs
