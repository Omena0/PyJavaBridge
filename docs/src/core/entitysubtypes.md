---
title: Entity Subtypes
subtitle: ArmorStand, Villager, ItemFrame, FallingBlock, AreaEffectCloud
---

# Entity Subtypes

These classes extend `Entity` with type-specific properties. They are returned automatically when the bridge detects the entity type, or can be used to wrap an existing entity handle.

## ArmorStand

ArmorStand entity with pose and equipment properties.

```python
stand = ArmorStand(handle=some_handle)
stand.small = True
stand.arms = True
stand.visible = False
stand.head_pose = {"x": 0.0, "y": 45.0, "z": 0.0}
```

### Properties

All properties support both get and set.

| Property | Type | Description |
| -------- | ---- | ----------- |
| `small` | `bool` | Whether armor stand is small |
| `visible` | `bool` | Visibility (inverted from `isInvisible`) |
| `arms` | `bool` | Whether armor stand has arms |
| `base_plate` | `bool` | Whether armor stand has a base plate |
| `marker` | `bool` | Whether armor stand is a marker (no hitbox) |
| `head_pose` | `EulerAngle` | Head rotation |
| `body_pose` | `EulerAngle` | Body rotation |
| `left_arm_pose` | `EulerAngle` | Left arm rotation |
| `right_arm_pose` | `EulerAngle` | Right arm rotation |
| `left_leg_pose` | `EulerAngle` | Left leg rotation |
| `right_leg_pose` | `EulerAngle` | Right leg rotation |

---

## Villager

Villager entity with profession, trade properties, and merchant recipes.

```python
villager = Villager(handle=some_handle)
villager.profession = "LIBRARIAN"
villager.villager_type = "PLAINS"
villager.villager_level = 3

# Add a trade: 10 emeralds for a diamond
villager.add_recipe(
    result={"type": "DIAMOND", "amount": 1},
    ingredients=[{"type": "EMERALD", "amount": 10}],
    max_uses=16,
    experience_reward=True,
    villager_experience=5,
)

# Read all trades
for recipe in villager.recipes:
    print(recipe["result"], recipe["ingredients"])

# Clear all trades
villager.clear_recipes()
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `profession` | `str` | Villager profession (get/set) |
| `villager_type` | `str` | Biome type (get/set) |
| `villager_level` | `int` | Trade level (get/set) |
| `villager_experience` | `int` | Experience points (get/set) |
| `recipes` | `list[dict]` | Merchant trade recipes (get/set) |
| `recipe_count` | `int` | Number of trade recipes (get) |

### Methods

| Method | Return | Description |
| ------ | ------ | ----------- |
| `add_recipe(result, ingredients, max_uses=1, experience_reward=True, villager_experience=0, price_multiplier=0.0, demand=0, special_price=0)` | `None` | Add a trade recipe |
| `clear_recipes()` | `None` | Remove all trade recipes |

### Recipe Dict Format

Each recipe is a dict with these keys:

| Key | Type | Description |
| --- | ---- | ----------- |
| `result` | `dict` | Serialized ItemStack for the result |
| `ingredients` | `list[dict]` | List of serialized ItemStack dicts (1-2) |
| `maxUses` | `int` | Max uses before trade locks |
| `uses` | `int` | Current number of uses |
| `experienceReward` | `bool` | Whether trade gives XP |
| `villagerExperience` | `int` | XP given to the villager |
| `priceMultiplier` | `float` | Demand-based price multiplier |
| `demand` | `int` | Current demand |
| `specialPrice` | `int` | Special price adjustment |

---

## ItemFrame

ItemFrame entity with item and rotation.

```python
frame = ItemFrame(handle=some_handle)
frame.item = some_item
frame.rotation = "CLOCKWISE_45"
frame.fixed = True

# Remove item
del frame.item
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `item` | `Item` | Item in frame (get/set/delete) |
| `rotation` | `str` | Item rotation (get/set) |
| `fixed` | `bool` | Whether frame is fixed/immovable (get/set) |
| `item_drop_chance` | `float` | Drop chance when broken (get/set) |

---

## FallingBlock

FallingBlock entity (a block affected by gravity).

```python
fb = FallingBlock(handle=some_handle)
mat = fb.material
fb.drop_item = False
fb.can_hurt_entities = True
fb.damage_per_block = 2.0
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `material` | `Any` | Block material (read-only) |
| `drop_item` | `bool` | Drop item on landing (get/set) |
| `can_hurt_entities` | `bool` | Whether it damages entities (get/set) |
| `damage_per_block` | `float` | Damage per block fallen (get/set) |
| `max_damage` | `int` | Maximum damage (get/set) |

---

## AreaEffectCloud

Lingering potion cloud entity.

```python
cloud = AreaEffectCloud(handle=some_handle)
cloud.radius = 5.0
cloud.duration = 200
cloud.particle = "SPELL_MOB"
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `radius` | `float` | Cloud radius (get/set) |
| `color` | `Any` | Particle color (get/set) |
| `duration` | `int` | Duration in ticks (get/set) |
| `wait_time` | `int` | Ticks before affecting entities (get/set) |
| `radius_on_use` | `float` | Radius reduction on use (get/set) |
| `radius_per_tick` | `float` | Radius change per tick (get/set) |
| `particle` | `Any` | Particle type (get/set) |
