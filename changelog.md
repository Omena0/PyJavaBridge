
# Changelog

## 4B

Client-mod API consolidation release — high-level Python interface, cleaner extension exports, and client/runtime hardening and readability improvements.

### Changes

#### `ClientMod` Session-First API

- Consolidated extension entrypoints around `client_mod` from `bridge.extensions.client_mod`.
- Standardized per-player calls through `ClientModSession` (`cm = client_mod.session(player)`) and methods like `cm.command(...)`, `cm.register_script(...)`, `cm.raycast(...)`, `cm.stream_audio_file(...)`, and `cm.stream_audio_generator(...)`.
- Exposed singleton decorators/registries for event and payload wiring: `client_mod.on_client_data`, `client_mod.on_permission_change`, `client_mod.register_request_data(...)`, `client_mod.unregister_request_data(...)`.
- Normalized exports in `bridge.extensions` to favor object-based API usage (`ClientMod`, `ClientModSession`, `client_mod`) over flat helper-only usage.

#### `BridgeInstance` and Event Routing Correctness

- Added script-only event bookkeeping via `BridgeInstance.scriptOnlySubscriptions` so `BridgeInstance.hasSubscription(...)`, `BridgeInstance.getSubscriptionNames()`, and dispatch matching include script-local handlers.
- Added `BridgeInstance.resolveInvokeResult(...)` to correctly resolve nested `CompletableFuture` returns with timeout/error propagation into Python responses.
- Corrected broadcast path in `BridgeInstance` to return `server.broadcastMessage(...)` behavior instead of log-only side effects.
- Hardened material handling in `BridgeInstance` (`sendBlockChange`) with explicit `Material.matchMaterial(...)` null checks before `Bukkit.createBlockData(...)`.

#### Serializer/Facade Guard Rails

- Added `BridgeSerializer` inventory validation in `deserialize(...)` (`size` must be `9..54` and a multiple of `9`).
- Removed implicit world mutation from `BridgeSerializer` `Block` deserialization (no hidden `block.setType(...)` side effects).
- Tightened boolean coercion in `BridgeSerializer.coerceArg(...)` to explicitly parse `"true"` / `"false"` string inputs.
- Added operation volume/bounds enforcement in `RegionFacade.pasteOperations(...)` and stronger invalid block-data failure behavior in `RegionFacade.parseBlockData(...)`.
- Enforced protocol-version validation in `ClientModFrameCodec.decodeFrame(...)`.

#### Python Runtime Concurrency and Lifecycle Safety

- Added `BridgeConnection` locking around `_pending_sync` and batching (`_pending_sync_lock`, `_batch_lock`) to avoid races between reader/caller threads.
- Made `BridgeConnection.flush()` atomically snapshot/clear `_batch_messages` and `_batch_futures` before sending `call_batch`.
- Added atomic abort reporting: `server.atomic()` now yields an int-like counter (`with server.atomic() as num_failed:` / `async with ...`) and `server.flush()` returns the aborted-call count for the flushed batch.
- Hardened disconnect/shutdown behavior in `BridgeConnection` so pending sync waits are finalized safely and loop stop is scheduled via `_loop.call_soon(...)`.
- Added proxy handle refcount synchronization in `wrappers.py` (`_handle_refcounts_lock`) and deterministic LRU-like UUID cache helpers (`_cache_get_player_uuid`, `_cache_set_player_uuid`).

#### Extension Correctness and Recovery Paths

- Prevented duplicate updater loops by task dedupe/cancel logic in `ability.py`, `combat.py`, `quest.py`, `leaderboard.py`, `scheduler.py`, and `state_machine.py`.
- Added malformed persistence recovery for JSON-backed extensions (`bank.py`, `levels.py`, `player_data.py`, `guild.py`).
- Fixed transactional currency flow in `trade.py` by checking `bank.withdraw(...)` return values and refunding on partial failure.
- Tightened parsing/validation across build and content tooling (`dungeon.py`, `schematic.py`, `mesh_display.py`, `image_display.py`, `loot_table.py`, `tab_list.py`).
- Improved client audio stream cleanup/failure surfacing in `client_mod.py` (`ffmpeg` stdout checks, producer error propagation, guaranteed stop in `finally`).

#### Docs, CI, and Packaging Follow-Through

- Reworked docs keying in `docs/build.py` to avoid basename collisions in output names, source maps, and search URLs.
- Pinned `.github/workflows/deploy-pages.yml` tool dependencies for reproducible docs deployments.
- Added missing extension files to `src/main/resources/python/bridge/MANIFEST` (`loot_table.py`, `placeholder.py`, `scheduler.py`, `schematic.py`, `state_machine.py`, `tab_list.py`).
- Updated stubs to reflect API/type reality in `bridge/__init__.pyi` and `bridge/extensions/__init__.pyi`.

## 4A

Client integration foundation release — first-class client bridge support, experimental runtime datapack tooling, and broad reliability/configuration improvements.

### Changes

#### Client Bridge Transport Foundation

- Added optional client-mod transport wiring centered on `ClientModChannelBridge`, `ClientModSessionManager`, and `ClientModProtocol`.
- Enabled request/response messaging and event ingress from cooperating client mods through bridge call targets.
- Added session-time permission negotiation so scripts can branch on allowed/denied/unavailable capabilities.

#### Runtime Datapack Registration (Experimental)

- Added runtime registration APIs in `DatapackFacade` for advancements, predicates, model JSON, and registry-scoped entries.
- Implemented best-effort application semantics for dynamic/testing workflows rather than strict static-pack replacement.

#### Reliability and Lifecycle Work

- Improved core runtime behavior in `PyJavaBridgePlugin`, `BridgeInstance`, and event dispatch paths for startup/shutdown and timeout handling.
- Improved failure tolerance around player/session state transitions and partial runtime disconnect scenarios.

#### Configuration and Operational Controls

- Expanded `config.yml` knobs for bridge payload sizing, timeout behavior, and Python runtime settings.
- Updated docs/deploy defaults so production operators can tune bridge throughput and timeout behavior more predictably.

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

#### Reflection & Caching

- Cache `getMethods()` per class in `BridgeInstance` and `RefFacade` — avoids repeated reflection on every reflective invoke
- Cache NMS reflection handles (`parseTag`, `getHandle`, `spawnNonLivingNms` helpers) in `EntitySpawner` static fields
- Cache LuckPerms API instance and `Node`/`InheritanceNode` class objects in `PermissionsFacade`
- Cache resolved event classes across 13 Bukkit packages in `EventSubscription` — avoids repeated `Class.forName()` for known events
- Build static `Map<String, PacketType>` lookup tables in `PacketBridge` — O(1) packet type resolution
- Merge dual method+miss cache into single `ConcurrentHashMap<String, Optional<Method>>` in `EventDispatcher` and `BridgeSerializer`
- Cache `getLogicalTypeName()` per concrete class in `BridgeSerializer` — avoids repeated instanceof chains on every serialize

#### Serialization & I/O

- ThreadLocal `ByteArrayOutputStream` for `send()` — avoids allocation per outgoing message
- ThreadLocal identity-hash set for cyclic reference detection in `serialize()` — reused across calls
- New `sendAll()` method batches multiple responses under a single lock + flush for batch/frame calls
- ItemStack meta: call `displayName()`/`lore()` once with null check instead of `has*()`+`get*()` pairs
- Shallow top-level entry copy instead of `deepCopy()` for per-block event payloads in `EventDispatcher`
- Reduce per-pixel overhead in `spawnImagePixels` — single `get()` + null check replaces `has()`+`get()` pairs

#### Data Structures & Dispatch

- `BridgeInstance.invoke()`: else-if dispatch chain replaces sequential instanceof checks — first match wins
- `ObjectRegistry`: `StampedLock` replaces `synchronized` block — lock-free reads via `ConcurrentHashMap`, write lock only for register/release
- `DebugManager`: `CopyOnWriteArraySet` replaces `synchronizedSet` — writes are rare (toggle), reads (broadcast) are frequent
- `PlayerUuidResolver`: static `HttpClient` singleton, LRU eviction via `LinkedHashMap`, cached `usercache.json` parse with timestamp
- `ScriptCommand`: pre-lowercase tab completions at registration — avoids `toLowerCase()` on every keystroke
- `EventSubscription.lastDispatchNano` marked `volatile` for safe cross-thread reads
- Expanded thread-safe method sets for `Server`, `OfflinePlayer`, and `Entity` — more calls skip main-thread dispatch
- Static empty `JsonObject` sentinel for missing `args` in `invoke()`

#### Connection & Dispatch

- Lazy module-level imports in `connection.py` — `_ensure_lazy_imports()` populates references once, avoids per-call `import`/`from` overhead
- Single-handler fast path in `_dispatch_event` — when only 1 handler, directly call+await without list/gather overhead
- `_build_call_message()` extracted — shared between `call()` and `call_sync()`, eliminates duplicated message construction
- Release queue changed from `list` to `set` — O(1) `discard()` replaces O(n) `list.remove()`
- `_maybe_flush_releases()` avoids unnecessary flushes on every call — only flushes when queue ≥ 16
- `_read_exact()` optimistic fast path — single `os.read()` often returns full message, skips `bytearray` accumulation
- `send()` writes header+data in one `write()` call instead of two

#### Proxy & Types

- Lazy module-level dispatch table for `_proxy_from()` — suffix/contains lookup tables built once, avoids per-call dict literal and import
- Handle-first fast path in `ProxyBase.__eq__` — same handle means same Java object, skip field comparison
- `EnumValue.from_name()` dict cache — returns cached instances for repeated enum lookups
- Bounded `_player_uuid_cache` (max 1000, evict oldest quarter) in both `wrappers.py` and `utils.py`
- Consolidated `isinstance` checks in `decorators.py` command wrapper — merged two separate branches into one

#### Helpers

- `State._instances` uses `weakref.ref` — allows garbage collection of unreferenced State objects
- Shutdown handler updated to dereference weakrefs

## 3A

Major expansion release — extension ecosystem growth, networking overhaul, API breadth increase, and substantial internal cleanup.

### Changes

#### IPC and Call Resolution

- Switched bridge transport from TCP sockets to `stdin`/`stdout` pipes for lower IPC overhead.
- Added snake_case -> camelCase fallback in Java invoke resolution so Python calls map cleanly onto Bukkit-style methods.
- Removed slow regex-heavy compatibility paths from hot invoke routes.

#### Core Wrapper API Expansion

- Expanded `Entity` AI and behavior APIs: targeting, pathing, awareness, line-of-sight, and look-direction controls.
- Added entity tag helpers (`add_tag`, `remove_tag`, `tags`, `is_tagged`) with UUID-keyed Python-side state.
- Added entity orientation/equipment-style fields (`yaw`, `pitch`, `look_direction`, equipment accessors).
- Added player-side controls (`selected_slot`, freeze/unfreeze movement lock, `vanish`/`unvanish`).
- Added convenience extension fields (`balance`, `deposit`, `withdraw`, `mana`, `xp`, `player_level`) on `Player` workflows.
- Expanded block/tile APIs (signs, furnaces, container-style interactions) and recipe APIs (shaped, shapeless, furnace recipe wrappers).
- Added firework builder flows and resource-pack controls on `Player`.
- Added enchantment discovery APIs (`Enchantment.all()`, `Enchantment.for_item(...)`).

#### Packet, Script Bus, and Time APIs

- Added ProtocolLib packet APIs: `on_packet_send(...)`, `on_packet_receive(...)`, `send_packet(...)`.
- Added inter-script messaging APIs: `script_send(...)`, `on_script_message(...)`, `get_scripts()`.
- Added `WorldTime` and `@world.at_time(...)` time-hook decorators.
- Expanded world utility methods (`create_explosion`, `entities_near`, `blocks_near`).

#### Math Types and Event Overrides

- Added operator support for `Location` (`+`, `-`) and `Vector` (`+`, `-`, `*`, reverse multiply patterns).
- Added broad enum coverage (including `DamageCause`, `Enchantment`, `ItemFlag`, and related gameplay enums).
- Added `player_respawn` return override support (return `Location` to redirect respawn).
- Added `entity_target` return override support (return `Entity` to set target).
- Added runtime unregistration support via `@event ... .unregister()`.

#### Extension Ecosystem Drop

- Added helper/feature modules: `Paginator`, `Quest`/`QuestTree`, `Dialog`, `Bank`, `Shop`, `TradeWindow`.
- Added gameplay systems: `Ability`, `ManaStore`, `CombatSystem`, `LevelSystem`.
- Added social/data/world systems: `Region`, `Party`, `Guild`, `CustomItem`, `Leaderboard`, `VisualEffect`, `PlayerDataStore`, `Dungeon`.

#### Command and Decorator Improvements

- Enhanced `@command` with automatic `cmd_` prefix stripping (`def cmd_greet` -> `/greet`).
- Added dynamic completion via `@my_command.tab_complete`.
- Added static completion lists via `tab_complete=` parameter (including wildcard-style matching).
- Added persistent `State` helper with shutdown save behavior.

#### Event and Error Model Upgrades

- Expanded event payload fields (`action`, `hand`, `from`, `to`, `cause`, `velocity`, `reason`, `message`, `new_slot`, `previous_slot`, `amount`, `slot`, etc).
- Added `Event.world` / `Event.location` auto-derivation from related player/entity context.
- Added snake_case event field access fallback to Java getters (`getNewSlot`, `isPreviousSlot`, etc).
- Propagated Java stack traces into Python exceptions and added typed error classes (for example `EntityGoneException`, `MethodNotFoundException`).

#### Helper, Tooling, and Internal Platform Work

- Fixed `Menu` race when opening a second menu from click callbacks.
- Improved display helpers (`ActionBarDisplay` immediate refresh; `BossBarDisplay` rename `link_cooldown` -> `linked_to` with compatibility alias).
- Hardened helper runtime behavior in `ManaStore` and `NPC` loops/callback linkage.
- Added CLI tooling with `pjb search <query>` and `pjb events [filter]`.
- Added docs search UX (`Ctrl+K`) and Gradle `copyBridgePython` auto-deploy task.
- Split monolithic `bridge.py` into modular runtime units (`connection`, `wrappers`, `helpers`, `types`, `utils`, `decorators`) and expanded internals docs/stubs.

## 2A

Feature expansion release — batching and IPC performance work, new world/player APIs, and helper/tooling growth.

### Changes

#### Throughput and IPC Improvements

- Optimized request flow for lower single-call latency.
- Added call batching for multi-operation workloads.
- Added `orjson` fast-path parsing support.
- Added automatic handle lifecycle management to reduce stale-object leaks.

#### New World/Player APIs

- Added tab-list APIs on `Player`.
- Added world region helpers on `World`: `set_block(...)`, `fill(...)`, `replace(...)`, `fill_sphere(...)`, `fill_cylinder(...)`, `fill_line(...)`.
- Added world particle-shape helpers and entity spawn helpers (`spawn_at_player(...)`, `spawn_projectile(...)`, `spawn_with_nbt(...)`).
- Added server command execution support from bridge-side runtime calls.
- Added `world.entities` and expanded raycast results (`RaycastResult.distance`, `RaycastResult.hit_face`).

#### New Helper Modules

- Added UI/state helpers: `Sidebar`, `Menu`, `MenuItem`, `ActionBarDisplay`, `BossBarDisplay`.
- Added config/state helpers: `Config` (TOML-first), `Cooldown`, shutdown event hooks.
- Added display helpers: `Hologram`, `BlockDisplay`, `ItemDisplay`, `ImageDisplay`.
- Added item workflow helper: `ItemBuilder`.

#### API Quality Improvements

- Fixed enum typing mismatches around `EnumValue` and child enum wrappers.
- Made `EntityGoneException` derive from `BridgeError`.
- Added `@task` interval scheduling decorator.
- Added event controls (`priority`, `throttle_ms`) and command metadata (`description`).
- Made attribute-like methods synchronous for core wrappers (`Location.add/clone/distance/distance_squared`, scoreboard/team/objective/bossbar creation).
- Added multi-format `Config` persistence (`toml`, `json`, `properties`).
- Expanded command execution paths to include console execution.

#### Refactor and Documentation Foundation

- Reordered core wrappers to define `Entity` before `Player` for cleaner inheritance flow.
- Split large single-file bridge implementation into multiple modules.
- Improved bridge typing coverage and early wiki/documentation rollout.
- Added dev-version labeling for non-tag builds.

## 1D

Damage and ownership update — expanded combat event payloads and entity ownership metadata.

### Changes

#### Event and Entity Updates

- Added damage override support on damage-event handlers.
- Added damage context fields (`damage source`, `damager`) on event payloads.
- Added projectile ownership access via shooter metadata.
- Added tame/ownership metadata on entities (`owner`, `is_tamed`).

## 1C

API cleanup update — synchronous attribute model improvements and quality-of-life fixes.

### Changes

#### API and Behavior Improvements

- Added sync helper paths (`call_sync(...)`, `field_or_call_sync(...)`).
- Converted method-like fields into direct attributes where appropriate.
- Made wrapper attributes consistently synchronous.
- Added `create(...)` classmethod patterns across major wrappers.
- Expanded `world.spawn_entity(...)` optional argument handling.
- Allowed non-living entity spawn paths.
- Fixed player UUID lookup edge cases.
- Made chat-event return values control outgoing chat format.
- Included additional bug-fix follow-through across wrapper internals.

## 1B

API expansion update — broader API coverage and initial documentation rollout.

### Changes

#### API and Docs

- Implemented most missing core APIs from early bridge targets.
- Added structured command argument parsing behavior.
- Added initial documentation pages for bridge usage.
- Included stabilization bug fixes.

## 1A

Initial release — first bridge implementation with core scripting APIs.

### Changes

#### Initial Scope

- Added the first set of commonly used bridge APIs across server, player, world, and event workflows.
