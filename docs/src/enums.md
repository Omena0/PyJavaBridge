---
title: Enums
subtitle: Enum types reference
---

# Enums

PyJavaBridge wraps Minecraft's Java enums as [`EnumValue`](enumvalue.md) subclasses. Each enum type supports attribute-style access (`EnumType.VALUE_NAME`) and `from_name("VALUE_NAME")`.

---

## How Enums Work

All enum types inherit from [`EnumValue`](enumvalue.md):

```python
# Attribute-style access
material = Material.DIAMOND_SWORD
sound = Sound.ENTITY_EXPERIENCE_ORB_PICKUP

# from_name (useful for dynamic values)
material = Material.from_name("DIAMOND_SWORD")
```

See the [`EnumValue`](enumvalue.md) page for full details.

---

## Material

```python
from bridge import Material
```

Block and item types. Minecraft has hundreds of materials.

**Common materials:**

| Category | Examples |
|----------|----------|
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
|----------|----------|
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
|------|-------------|
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
|------|---------|-------------|
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
|------|-------------|
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
|------|-------------|
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
|------|-------------|
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
|------|
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
|------|
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
|------|-------------|
| `SOLID` | No segments |
| `SEGMENTED_6` | 6 segments |
| `SEGMENTED_10` | 10 segments |
| `SEGMENTED_12` | 12 segments |
| `SEGMENTED_20` | 20 segments |
