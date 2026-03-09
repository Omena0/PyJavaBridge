# Implementation Plan

## Scope

Implementing ~85 features across existing classes and new modules.

**Excluded** (already exist): Hologram, Menu/MenuItem, Sidebar, ActionBar, Cooldown, Config, Paginator, shorthand event decorators.

**New extensions to add**: TabList, State Machine, Scheduler, Placeholder, Loot Table.

---

## Group 1: Python-Only Property Additions (wrappers.py)

*All use reflection fallback — no Java changes needed.*

### Group 1A: Entity Properties

Add to Entity class in wrappers.py:

- `gravity` (get/set) — `hasGravity()`/`setGravity()`
- `glowing` (get/set) — `isGlowing()`/`setGlowing()`
- `invisible` (get/set) — `isInvisible()`/`setInvisible()`
- `invulnerable` (get/set) — `isInvulnerable()`/`setInvulnerable()`
- `silent` (get/set) — `isSilent()`/`setSilent()`
- `persistent` (get/set) — `isPersistent()`/`setPersistent()`
- `collidable` (get/set) — `isCollidable()`/`setCollidable()`
- `portal_cooldown` (get/set) — `getPortalCooldown()`/`setPortalCooldown()`
- `max_fire_ticks` (get) — `getMaxFireTicks()`
- `freeze_ticks` (get/set) — `getFreezeTicks()`/`setFreezeTicks()`
- `height` / `width` (get) — `getHeight()`/`getWidth()`
- `bounding_box` (get) — `getBoundingBox()` (returns dict)

### Group 1B: Player Properties

Add to Player class in wrappers.py:

- `absorption` (get/set) — `getAbsorptionAmount()`/`setAbsorptionAmount()`
- `saturation` (get/set) — `getSaturation()`/`setSaturation()`
- `exhaustion` (get/set) — `getExhaustion()`/`setExhaustion()`
- `max_health` (get/set) — uses getAttribute(GENERIC_MAX_HEALTH)
- `attack_cooldown` (get) — `getAttackCooldown()`
- `allow_flight` (get/set) — `getAllowFlight()`/`setAllowFlight()`
- `locale` (get) — `getLocale()`
- `ping` (get) — `getPing()`
- `client_brand` (get) — `getClientBrandName()`

### Group 1C: World Properties

Add to World class in wrappers.py:

- `seed` (get) — `getSeed()`
- `pvp` (get/set) — `getPVP()`/`setPVP()`

### Group 1D: Block Properties

Add to Block class:

- `hardness` (get) — reflection: `getType().getHardness()`
- `blast_resistance` (get) — reflection: `getType().getBlastResistance()`
- `is_passable` (get) — `isPassable()`
- `is_liquid` (get) — `isLiquid()`

### Group 1E: Inventory Properties

Add to Inventory class:

- `viewers` (get) — `getViewers()`
- `type` (get) — `getType()`

---

## Group 2: Python Properties Needing Java Handlers

### Group 2A: Player Methods Needing Java

Add Java handlers in invokePlayerMethod + Python wrappers:

- `bed_spawn_location` (get/set) — needs Location serialization
- `compass_target` (get/set) — needs Location serialization
- `get_cooldown(material)` / `set_cooldown(material, ticks)` — needs Material enum resolution
- `get_statistic(stat, material?, entity_type?)` / `set_statistic(...)` — needs Statistic enum + overloads
- `send_block_change(location, material)` — needs Location + Material
- `hide_player(other)` / `show_player(other)` — needs plugin reference
- `send_particle(particle, location, count, ...)` — needs Location construction
- `open_book(item)` — needs ItemStack handle

### Group 2B: World Methods Needing Java

Add Java handlers in invokeWorldMethod + Python wrappers:

- `get_game_rule(rule)` / `set_game_rule(rule, value)` — needs GameRule enum resolution + typed values
- `world_border` — needs new WorldBorder wrapper class + Java serialization
- `get_highest_block_at(x, z)` — needs Block serialization
- `generate_tree(location, tree_type)` — needs Location + TreeType
- `nearby_entities(location, dx, dy, dz)` — needs Location construction
- `get_chunk_at_async(x, z)` — needs async callback pattern

### Group 2C: Block Methods Needing Java

- `get_drops(tool=None)` — needs optional ItemStack + returns List\<ItemStack>

### Group 2D: Item Properties Needing Java

Add to invokeItemStackMethod + Item wrapper:

- `durability` (get/set) — needs Damageable meta cast
- `max_durability` (get) — needs Material lookup
- `enchantments` (get) — needs enchantment map serialization
- `item_flags` (get/set) — needs ItemFlag enum handling
- `is_unbreakable` (get/set) — needs ItemMeta cast

---

## Group 3: New Wrapper Classes (Python + Java)

### Group 3A: WorldBorder

- Python: WorldBorder class in wrappers.py with properties (center, size, damage_amount, damage_buffer, warning_distance, warning_time) and methods (set_size, set_center, lerp)
- Java: Serialize WorldBorder in BridgeSerializer, add handler in invokeWorldMethod for getWorldBorder()

### Group 3B: Entity Subtypes

- Python: ArmorStand, Villager, ItemFrame, FallingBlock, AreaEffectCloud classes in wrappers.py
- Mostly reflection-based, some Java handler additions for complex operations

### Group 3C: Supporting Classes

- Python: Painting class, Boat/Minecart classes (via Entity subtype detection)
- GameRule enum in enums.py
- Enchantment query class

### Group 3D: PersistentDataContainer

- Java: New handler for PDC get/set/has/remove on entities and blocks
- Python: `entity.data` / `block.data` dict-like wrapper

### Group 3E: StructureManager + WorldCreator

- Java: Handler for structure loading/saving, world creation
- Python: StructureManager and WorldCreator classes

### Group 3F: Map Renderer

- Java: Handler for map creation, pixel setting
- Python: Map class with draw methods

---

## Group 4: New Core Capabilities

### Group 4A: Custom Events

- Python: `custom_event(name, data)` function + decorator registration
- Java: CustomEvent dispatcher in EventDispatcher

### Group 4B: Component Text (Adventure API)

- Python: TextComponent builder class with click/hover/gradient
- Java: Handler to convert component JSON to Adventure

### Group 4C: Book Builder

- Python: BookBuilder class with pages, open_book()
- Java: Handler for book ItemStack creation + player.openBook()

### Group 4D: Entity AI Goals (Paper MobGoals)

- Java: Handler to add/remove/list AI goals
- Python: AIGoal wrapper class

### Group 4E: Async World Edit

- Python: async_fill(), async_replace() that chunk operations across ticks
- Uses existing region facade with tick-spread batching

### Group 4F: Batch Entity Spawn

- Java: Handler for batch spawn with single round-trip
- Python: world.batch_spawn() method

### Group 4G: Block Snapshot/Restore

- Python: BlockSnapshot class that saves/restores regions to memory
- Java: Region facade extension for capture + paste

### Group 4H: Entity Metadata (Transient)

- Python: entity.metadata dict-like storage (Python-side, not PDC)
- No Java needed — stored in Python dict keyed by UUID

### Group 4I: Predicate Entity Queries

- Python: world.find_entities(type, radius, predicate) that filters client-side
- Builds on existing entities_near

### Group 4J: NBT Compound Access

- Java: Handler for structured NBT read/write
- Python: NBTCompound dict-like class

### Group 4K: World Ray Trace

- Java: Extend raycast facade with world-level traces
- Python: world.ray_trace() method

---

## Group 5: Quality of Life (Python-only)

- Inventory `__getitem__`/`__setitem__`/`__iter__`/`__len__`
- Player/Entity `__bool__` truthiness
- World `__contains__` for entity check
- Location `__mul__`, `__truediv__`, `normalize()`, `midpoint()`
- Context manager for inventories
- Hot reload `@preserve` decorator
- Type-safe event fields (typed dataclass events)

---

## Group 6: New Extensions

### Group 6A: TabList Extension

- Full tab list customization with templates, fake entries, groups

### Group 6B: State Machine Extension

- Per-entity/player state machines for game phases

### Group 6C: Scheduler Extension

- Cron-like real-world-time scheduling, named tasks

### Group 6D: Placeholder System

- Register `%placeholder%` expansions for messages

### Group 6E: Loot Table Extension

- Custom loot tables with weights, conditions, rolls

---

## Group 7: Documentation & Type Stubs

- Update `__init__.pyi` with all new classes/methods
- Update/create docs/src/*.md for all new features
- Update docs/src/index.md with new content

---

## Execution Order

**Phase 1 (parallel):**

- Group 1A-1E (Python-only properties — all independent)
- Group 5 (QoL — Python-only, independent)

**Phase 2 (parallel):**

- Group 2A (Player Java handlers)
- Group 2B (World Java handlers)
- Group 2C-2D (Block + Item Java handlers)
- Group 3A (WorldBorder)
- Group 3D (PDC)

**Phase 3 (parallel):**

- Group 3B (Entity subtypes)
- Group 3C (Supporting classes)
- Group 4A (Custom events)
- Group 4B (Component text)
- Group 4E (Async world edit)
- Group 4H (Entity metadata)
- Group 4I (Predicate queries)

**Phase 4 (parallel):**

- Group 3E (StructureManager + WorldCreator)
- Group 3F (Map renderer)
- Group 4C (Book builder)
- Group 4D (AI Goals)
- Group 4F (Batch spawn)
- Group 4G (Block snapshot)
- Group 4J (NBT)
- Group 4K (World ray trace)

**Phase 5 (parallel):**

- Group 6A-6E (New extensions)

**Phase 6:**

- Group 7 (Documentation + type stubs)

Total: ~85 features across 6 phases.
