---
title: Datapack (runtime)
subtitle: Register datapack-like definitions at runtime from Python
---

# Datapack (runtime)

The `Datapack` runtime proxy lets Python code register the same kinds of JSON definitions datapacks provide (models, advancements, predicates, worldgen, tags, registries, damage/chat types) without writing datapack files. Instead these definitions are sent to the Java side where they are collected and applied to the running server.

## Usage

```python
from bridge import Datapack

# create a runtime proxy (no files created)
dp = Datapack()

# register a model (namespace, path, model-json)
dp.register_model("myns", "item/custom_sword", {
    "parent": "item/generated",
    "textures": {"layer0": "myns:item/custom_sword"}
})

# register an advancement
adv = {
    "display": {"title": "First Step", "description": "Do a thing", "icon": {"item": "minecraft:stone"}},
    "criteria": {"do_thing": {"trigger": "minecraft:impossible"}}
}
dp.register_advancement("myns", "root/first", adv)

# register a predicate
pred = {"condition": "minecraft:entity_properties", "entity": {"type": "minecraft:player"}}
dp.register_predicate("myns", "preds/is_player", pred)

# when ready, ask Java to attempt to apply all registered entries
dp.apply_all()
```

## API reference

- `Datapack().register_model(namespace, path, model_json)` — Register an item/block model JSON.
- `Datapack().register_advancement(namespace, path, advancement_json)` — Register an advancement definition.
- `Datapack().register_predicate(namespace, path, predicate_json)` — Register a predicate definition.
- `Datapack().register_worldgen(namespace, category, path, json_obj)` — Register worldgen entries (dimensions, noise, carvers, structures).
- `Datapack().register_tag(namespace, tag_type, tag_id, values, replace=False)` — Register a datapack tag.
- `Datapack().register_registry_entry(namespace, registry, path, entry_json)` — Register an entry for a datapack registry.
- `Datapack().register_damage_type(namespace, id, json_obj)` — Register a damage type (vends to registry API).
- `Datapack().register_chat_type(namespace, id, json_obj)` — Register a chat type.
- `Datapack().apply_all()` — Ask Java to apply the collected entries to the running server.
