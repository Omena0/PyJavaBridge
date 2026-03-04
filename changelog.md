
# Changelog

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
