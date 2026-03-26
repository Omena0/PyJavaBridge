---
title: Enums
subtitle: Enum types reference
---

# Enums

PyJavaBridge wraps Minecraft's Java enums as `EnumValue` subclasses. Each enum type supports attribute-style access (`EnumType.VALUE_NAME`) and `from_name("VALUE_NAME")`.

---

## How Enums Work

All enum types inherit from `EnumValue`:

```python
# Attribute-style access
material = Material.DIAMOND_SWORD
sound = Sound.ENTITY_EXPERIENCE_ORB_PICKUP

# from_name (useful for dynamic values)
material = Material.from_name("DIAMOND_SWORD")
```

See the `EnumValue` page for full details.

---

## Material

```python
from bridge import Material
```

Block and item types. Minecraft has hundreds of materials.

**Common materials:**

| Category | Examples |
| -------- | -------- |
| Ores | `DIAMOND_ORE`, `IRON_ORE`, `GOLD_ORE`, `COAL_ORE` |
| Blocks | `STONE`, `DIRT`, `GRASS_BLOCK`, `OAK_PLANKS`, `COBBLESTONE` |
| Items | `DIAMOND_SWORD`, `IRON_PICKAXE`, `BOW`, `ARROW`, `STICK` |
| Food | `GOLDEN_APPLE`, `COOKED_BEEF`, `BREAD`, `CAKE` |
| Armor | `DIAMOND_HELMET`, `IRON_CHESTPLATE`, `LEATHER_BOOTS` |
| Glass | `GLASS`, `RED_STAINED_GLASS`, `GLASS_PANE` |
| Wool | `WHITE_WOOL`, `RED_WOOL`, `BLUE_WOOL` |
| Misc | `BEACON`, `ENDER_PEARL`, `NETHER_STAR`, `TOTEM_OF_UNDYING` |

```python
sword = Item(Material.DIAMOND_SWORD)
await world.set_block(0, 60, 0, Material.STONE)
```

---

## EntityType

```python
from bridge import EntityType
```

Mob and entity types.

| Category | Examples |
| -------- | -------- |
| Hostile | `ZOMBIE`, `SKELETON`, `CREEPER`, `SPIDER`, `ENDERMAN`, `WITCH` |
| Passive | `COW`, `PIG`, `SHEEP`, `CHICKEN`, `VILLAGER`, `HORSE` |
| Projectiles | `ARROW`, `FIREBALL`, `SNOWBALL`, `ENDER_PEARL`, `TRIDENT` |
| Misc | `ITEM`, `EXPERIENCE_ORB`, `ARMOR_STAND`, `LIGHTNING_BOLT` |

```python
await Entity.spawn(EntityType.ZOMBIE, location)
await world.spawn_projectile(player, EntityType.FIREBALL)
```

---

## EffectType

```python
from bridge import EffectType
```

Potion effect types.

| Name | Description |
| ---- | ----------- |
| `SPEED` | Increases movement speed |
| `SLOWNESS` | Decreases movement speed |
| `HASTE` | Increases mining speed |
| `MINING_FATIGUE` | Decreases mining speed |
| `STRENGTH` | Increases attack damage |
| `INSTANT_HEALTH` | Heals instantly |
| `INSTANT_DAMAGE` | Damages instantly |
| `JUMP_BOOST` | Increases jump height |
| `REGENERATION` | Restores health over time |
| `RESISTANCE` | Reduces damage taken |
| `FIRE_RESISTANCE` | Immunity to fire damage |
| `WATER_BREATHING` | Breathe underwater |
| `INVISIBILITY` | Invisible to other players |
| `BLINDNESS` | Restricts vision |
| `NIGHT_VISION` | See in the dark |
| `POISON` | Deals damage over time |
| `WITHER` | Deals wither damage over time |
| `ABSORPTION` | Adds absorption hearts |
| `SATURATION` | Restores hunger |
| `GLOWING` | Glowing outline |
| `LEVITATION` | Float upward |
| `SLOW_FALLING` | Fall slowly |

```python
await Effect.apply(player, EffectType.SPEED, duration=600, amplifier=1)
```

---

## AttributeType

```python
from bridge import AttributeType
```

Entity attribute types for stat modification.

| Name | Default | Description |
| ---- | ------- | ----------- |
| `GENERIC_MAX_HEALTH` | 20.0 | Maximum health |
| `GENERIC_MOVEMENT_SPEED` | 0.1 | Walking speed |
| `GENERIC_ATTACK_DAMAGE` | 1.0 | Melee damage |
| `GENERIC_ATTACK_SPEED` | 4.0 | Attack cooldown |
| `GENERIC_ARMOR` | 0.0 | Armor points |
| `GENERIC_ARMOR_TOUGHNESS` | 0.0 | Armor toughness |
| `GENERIC_KNOCKBACK_RESISTANCE` | 0.0 | Knockback resistance |
| `GENERIC_LUCK` | 0.0 | Loot table luck |
| `GENERIC_FLYING_SPEED` | 0.4 | Creative fly speed |

---

## GameMode

```python
from bridge import GameMode
```

| Name | Description |
| ---- | ----------- |
| `SURVIVAL` | Normal survival |
| `CREATIVE` | Creative mode |
| `ADVENTURE` | Adventure mode |
| `SPECTATOR` | Spectator mode |

```python
await player.set_game_mode(GameMode.CREATIVE)
```

---

## Sound

```python
from bridge import Sound
```

Minecraft sound effects. Examples:

| Name | Description |
| ---- | ----------- |
| `ENTITY_EXPERIENCE_ORB_PICKUP` | XP orb |
| `BLOCK_NOTE_BLOCK_BASS` | Note block bass |
| `BLOCK_NOTE_BLOCK_PLING` | Note block pling |
| `ENTITY_PLAYER_LEVELUP` | Level up |
| `ITEM_TOTEM_USE` | Totem activation |
| `ENTITY_ENDER_DRAGON_GROWL` | Dragon growl |
| `UI_BUTTON_CLICK` | Button click |

```python
await player.play_sound(Sound.ENTITY_EXPERIENCE_ORB_PICKUP)
await world.play_sound(location, Sound.ENTITY_ENDER_DRAGON_GROWL, volume=2.0)
```

---

## Particle

```python
from bridge import Particle
```

Particle effects.

| Name | Description |
| ---- | ----------- |
| `FLAME` | Fire particles |
| `HEART` | Heart particles |
| `VILLAGER_HAPPY` | Green sparkles |
| `EXPLOSION_LARGE` | Large explosion |
| `REDSTONE` | Redstone dust |
| `SMOKE_NORMAL` | Normal smoke |
| `CRIT` | Critical hit sparkles |
| `SPELL_MOB` | Potion effect swirls |
| `END_ROD` | End rod particles |
| `TOTEM` | Totem of Undying particles |

```python
await world.spawn_particle(Particle.FLAME, location, count=50)
await world.particle_sphere(location, 3.0, Particle.END_ROD)
```

---

## Difficulty

```python
from bridge import Difficulty
```

| Name |
| ---- |
| `PEACEFUL` |
| `EASY` |
| `NORMAL` |
| `HARD` |

---

## Biome

```python
from bridge import Biome
```

World biomes. Examples: `PLAINS`, `FOREST`, `DESERT`, `OCEAN`, `MOUNTAINS`, `SWAMP`, `JUNGLE`, `TAIGA`, `SAVANNA`, `BADLANDS`, `THE_NETHER`, `THE_END`.

```python
await block.set_biome(Biome.DESERT)
```

---

## BarColor

```python
from bridge import BarColor
```

| Name |
| ---- |
| `PINK` |
| `BLUE` |
| `RED` |
| `GREEN` |
| `YELLOW` |
| `PURPLE` |
| `WHITE` |

---

## BarStyle

```python
from bridge import BarStyle
```

| Name | Description |
| ---- | ----------- |
| `SOLID` | No segments |
| `SEGMENTED_6` | 6 segments |
| `SEGMENTED_10` | 10 segments |
| `SEGMENTED_12` | 12 segments |
| `SEGMENTED_20` | 20 segments |

---

## DamageCause

```python
from bridge import DamageCause
```

Why an entity took damage.

| Name | Description |
| ---- | ----------- |
| `CONTACT` | Touching a cactus or berry bush |
| `ENTITY_ATTACK` | Melee attack by entity |
| `ENTITY_SWEEP_ATTACK` | Sweep attack |
| `PROJECTILE` | Hit by a projectile |
| `SUFFOCATION` | Stuck inside a block |
| `FALL` | Falling |
| `FIRE` | Standing in fire |
| `FIRE_TICK` | Burning (on fire) |
| `LAVA` | In lava |
| `DROWNING` | Out of air underwater |
| `BLOCK_EXPLOSION` | Block explosion (TNT, bed) |
| `ENTITY_EXPLOSION` | Entity explosion (creeper) |
| `VOID` | Falling into the void |
| `LIGHTNING` | Struck by lightning |
| `STARVATION` | No food |
| `POISON` | Poison effect |
| `MAGIC` | Instant damage potion |
| `WITHER` | Wither effect |
| `FALLING_BLOCK` | Hit by falling block |
| `FLY_INTO_WALL` | Elytra into wall |
| `HOT_FLOOR` | Standing on magma |
| `CRAMMING` | Too many entities |
| `FREEZE` | Powder snow |

```python
@event
async def entity_damage(e):
    if e.damage_cause == DamageCause.FALL.name:
        return 0  # No fall damage
```

---

## Enchantment

```python
from bridge import Enchantment
```

Item enchantment types.

| Name | Description |
| ---- | ----------- |
| `SHARPNESS` | Increased melee damage |
| `SMITE` | Extra damage to undead |
| `PROTECTION` | Reduced damage |
| `FIRE_PROTECTION` | Reduced fire damage |
| `EFFICIENCY` | Faster mining |
| `SILK_TOUCH` | Mine blocks as-is |
| `FORTUNE` | More drops |
| `UNBREAKING` | Increased durability |
| `MENDING` | Repair with XP |
| `INFINITY` | Infinite arrows |
| `POWER` | Stronger arrows |
| `PUNCH` | Arrow knockback |
| `FLAME` | Fire arrows |
| `LOOTING` | More mob drops |
| `THORNS` | Damage attackers |
| `DEPTH_STRIDER` | Faster underwater movement |
| `FROST_WALKER` | Freeze water |
| `FEATHER_FALLING` | Reduced fall damage |

```python
item = ItemBuilder(Material.DIAMOND_SWORD).enchant(Enchantment.SHARPNESS, 5).build()
```

---

## ItemFlag

```python
from bridge import ItemFlag
```

Flags to hide item tooltip sections.

| Name | Description |
| ---- | ----------- |
| `HIDE_ENCHANTS` | Hide enchantments |
| `HIDE_ATTRIBUTES` | Hide attribute modifiers |
| `HIDE_UNBREAKABLE` | Hide "Unbreakable" tag |
| `HIDE_DESTROYS` | Hide "Can destroy" list |
| `HIDE_PLACED_ON` | Hide "Can be placed on" list |
| `HIDE_DYE` | Hide leather armor color |
| `HIDE_ARMOR_TRIM` | Hide armor trim |

---

## EquipmentSlot

```python
from bridge import EquipmentSlot
```

| Name |
| ---- |
| `HAND` |
| `OFF_HAND` |
| `HEAD` |
| `CHEST` |
| `LEGS` |
| `FEET` |

---

## DyeColor

```python
from bridge import DyeColor
```

| Name |
| ---- |
| `WHITE` |
| `ORANGE` |
| `MAGENTA` |
| `LIGHT_BLUE` |
| `YELLOW` |
| `LIME` |
| `PINK` |
| `GRAY` |
| `LIGHT_GRAY` |
| `CYAN` |
| `PURPLE` |
| `BLUE` |
| `BROWN` |
| `GREEN` |
| `RED` |
| `BLACK` |

---

## SpawnReason

```python
from bridge import SpawnReason
```

Why a creature spawned.

| Name | Description |
| ---- | ----------- |
| `NATURAL` | Natural world spawning |
| `SPAWNER` | Monster spawner |
| `EGG` | Spawn egg |
| `BREEDING` | Animal breeding |
| `COMMAND` | /summon command |
| `CUSTOM` | Plugin/API spawning |
| `LIGHTNING` | Lightning strike (skeleton horse) |
| `VILLAGE_DEFENSE` | Iron golem defense |
| `BUILD_IRONGOLEM` | Built iron golem |
| `BUILD_SNOWMAN` | Built snow golem |
| `CURED` | Cured zombie villager |
| `DROWNED` | Zombie became drowned |
| `JOCKEY` | Spider jockey |
| `REINFORCEMENTS` | Zombie reinforcements |

---

## EntityCategory

```python
from bridge import EntityCategory
```

| Name |
| ---- |
| `NONE` |
| `UNDEAD` |
| `ARTHROPOD` |
| `ILLAGER` |
| `WATER` |

---

## EntityPose

```python
from bridge import EntityPose
```

| Name |
| ---- |
| `STANDING` |
| `FALL_FLYING` |
| `SLEEPING` |
| `SWIMMING` |
| `SPIN_ATTACK` |
| `SNEAKING` |
| `DYING` |
| `SITTING` |

---

## BlockFace

```python
from bridge import BlockFace
```

| Name |
| ---- |
| `NORTH` |
| `SOUTH` |
| `EAST` |
| `WEST` |
| `UP` |
| `DOWN` |
| `NORTH_EAST` |
| `NORTH_WEST` |
| `SOUTH_EAST` |
| `SOUTH_WEST` |
| `SELF` |

---

## TreeType

```python
from bridge import TreeType
```

| Name |
| ---- |
| `TREE` |
| `BIG_TREE` |
| `BIRCH` |
| `REDWOOD` |
| `TALL_REDWOOD` |
| `JUNGLE` |
| `SMALL_JUNGLE` |
| `JUNGLE_BUSH` |
| `SWAMP` |
| `ACACIA` |
| `DARK_OAK` |
| `CHERRY` |

---

## WeatherType

```python
from bridge import WeatherType
```

| Name |
| ---- |
| `CLEAR` |
| `DOWNFALL` |

---

## WorldType

```python
from bridge import WorldType
```

| Name |
| ---- |
| `NORMAL` |
| `FLAT` |
| `LARGE_BIOMES` |
| `AMPLIFIED` |

---

## Action

```python
from bridge import Action
```

Player block interaction type.

| Name | Description |
| ---- | ----------- |
| `LEFT_CLICK_BLOCK` | Left-clicked a block |
| `RIGHT_CLICK_BLOCK` | Right-clicked a block |
| `LEFT_CLICK_AIR` | Left-clicked air |
| `RIGHT_CLICK_AIR` | Right-clicked air |
| `PHYSICAL` | Stepped on pressure plate, etc. |

---

## ChatColor

```python
from bridge import ChatColor
```

Legacy Minecraft color codes. Prefer `§` codes in strings for simplicity.

| Name | Code |
| ---- | ---- |
| `BLACK` | §0 |
| `DARK_BLUE` | §1 |
| `DARK_GREEN` | §2 |
| `DARK_AQUA` | §3 |
| `DARK_RED` | §4 |
| `DARK_PURPLE` | §5 |
| `GOLD` | §6 |
| `GRAY` | §7 |
| `DARK_GRAY` | §8 |
| `BLUE` | §9 |
| `GREEN` | §a |
| `AQUA` | §b |
| `RED` | §c |
| `LIGHT_PURPLE` | §d |
| `YELLOW` | §e |
| `WHITE` | §f |
| `BOLD` | §l |
| `ITALIC` | §o |
| `UNDERLINE` | §n |
| `STRIKETHROUGH` | §m |
| `RESET` | §r |

---

## EventPriority

```python
from bridge import EventPriority
```

| Name | Description |
| ---- | ----------- |
| `LOWEST` | First to run |
| `LOW` | Early |
| `NORMAL` | Default |
| `HIGH` | Late |
| `HIGHEST` | Last before monitor |
| `MONITOR` | Read-only observation |

---

## TeleportCause

```python
from bridge import TeleportCause
```

| Name | Description |
| ---- | ----------- |
| `ENDER_PEARL` | Ender pearl throw |
| `COMMAND` | /tp command |
| `PLUGIN` | Plugin teleport |
| `NETHER_PORTAL` | Nether portal |
| `END_PORTAL` | End portal |
| `CHORUS_FRUIT` | Ate chorus fruit |
| `SPECTATE` | Spectator teleport |
| `UNKNOWN` | Unknown cause |

---

## InventoryType

```python
from bridge import InventoryType
```

| Name | Description |
| ---- | ----------- |
| `CHEST` | Chest / double chest |
| `CRAFTING` | Player crafting grid |
| `DISPENSER` | Dispenser |
| `DROPPER` | Dropper |
| `FURNACE` | Furnace |
| `HOPPER` | Hopper |
| `PLAYER` | Player inventory |
| `WORKBENCH` | Crafting table |
| `ENCHANTING` | Enchanting table |
| `BREWING` | Brewing stand |
| `ANVIL` | Anvil |
| `BEACON` | Beacon |
| `SHULKER_BOX` | Shulker box |
| `BARREL` | Barrel |
| `BLAST_FURNACE` | Blast furnace |
| `SMOKER` | Smoker |
| `MERCHANT` | Villager trading |

---

## Billboard

```python
from bridge import Billboard
```

Display entity billboard mode (how it faces the player).

| Name | Description |
| ---- | ----------- |
| `FIXED` | No rotation |
| `VERTICAL` | Rotate on Y axis only |
| `HORIZONTAL` | Rotate on X axis only |
| `CENTER` | Always face the camera |

---

## BarFlag

```python
from bridge import BarFlag
```

Boss bar display flags.

| Name | Description |
| ---- | ----------- |
| `DARKEN_SKY` | Darken the sky |
| `PLAY_BOSS_MUSIC` | Play boss music |
| `CREATE_FOG` | Create world fog |
