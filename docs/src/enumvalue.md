---
title: EnumValue
subtitle: Base class for all enum-like types
---

# EnumValue

`EnumValue` is the base class for all Minecraft enum types exposed by the bridge: `Material`, `EntityType`, `Biome`, `EffectType`, `GameMode`, `Sound`, `Particle`, `Difficulty`, `BarColor`, `BarStyle`, and `AttributeType`.

---

## Constructor

```python
EnumValue(type: str, name: str)
```

Create an enum value with a specific type and name. You rarely need this directly — use the subclass attribute syntax instead.

### Parameters

#### type

- **Type:** `str`

The enum type name (e.g. `"Material"`, `"EntityType"`).

#### name

- **Type:** `str`

The enum value name (e.g. `"DIAMOND"`, `"ZOMBIE"`).

---

## Class Methods

### from_name

```python
@classmethod
EnumValue.from_name(name: str) -> EnumValue
```

Create an enum value from a name string. The type is inferred from the subclass.

```python
mat = Material.from_name("DIAMOND")
```

---

## Attributes

### type

- **Type:** `str`

The enum type name.

```python
m = Material.DIAMOND
print(m.type)  # "Material"
```

### name

- **Type:** `str`

The enum value name.

```python
m = Material.DIAMOND
print(m.name)  # "DIAMOND"
```

---

## Attribute Access

All `EnumValue` subclasses support attribute-style access to create values:

```python
Material.DIAMOND          # EnumValue("Material", "DIAMOND")
EntityType.ZOMBIE         # EnumValue("EntityType", "ZOMBIE")
GameMode.CREATIVE         # EnumValue("GameMode", "CREATIVE")
Sound.ENTITY_EXPERIENCE_ORB_PICKUP
Particle.FLAME
Difficulty.HARD
BarColor.RED
BarStyle.SEGMENTED_6
AttributeType.GENERIC_MAX_HEALTH
EffectType.POISON
Biome.PLAINS
```

Name lookup is case-insensitive on the Java side, but by convention use `UPPER_SNAKE_CASE`.

---

## Subclasses

| Class | Description | Example |
|-------|-------------|---------|
| `Material` | Block/item materials | `Material.DIAMOND` |
| `EntityType` | Entity types | `EntityType.ZOMBIE` |
| `Biome` | World biomes | `Biome.PLAINS` |
| `EffectType` | Potion effect types | `EffectType.POISON` |
| `GameMode` | Player game modes | `GameMode.CREATIVE` |
| `Sound` | Minecraft sounds | `Sound.ENTITY_EXPERIENCE_ORB_PICKUP` |
| `Particle` | Particle types | `Particle.FLAME` |
| `Difficulty` | World difficulties | `Difficulty.HARD` |
| `BarColor` | Boss bar colors | `BarColor.RED` |
| `BarStyle` | Boss bar styles | `BarStyle.SEGMENTED_6` |
| `AttributeType` | Entity attribute types | `AttributeType.GENERIC_MAX_HEALTH` |
