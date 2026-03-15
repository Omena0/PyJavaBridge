---
title: Datapack (runtime)
subtitle: Register datapack-like definitions at runtime from Python
---

# Datapack (runtime)

The `Datapack` runtime proxy lets Python code register the same kinds of JSON definitions datapacks provide (models, advancements, predicates, worldgen, tags, registries, damage/chat types) without writing datapack files. Instead these definitions are sent to the Java side where they are collected and may be applied to the running server.

> NOTE: The current implementation collects and stores registered definitions in Java (`DatapackFacade`) and exposes an `apply_all()` request. Actual application to all Minecraft registries is best-effort and currently a TODO on the Java side; see "Limitations" below.

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

## Limitations (current implementation)

- The Python API and Java `DatapackFacade` collect and store JSON for all the above features, but the Java side currently logs and holds the data; the actual logic to inject those JSON definitions directly into Paper/Minecraft registries (models, registry entries, worldgen registries) is not yet implemented — `DatapackFacade.applyAll()` currently schedules a task and logs counts.

- Some datapack features (advancements, predicates) are more straightforward to register at runtime via the Bukkit/Paper APIs and can be implemented more quickly. Others (custom registry entries, worldgen/noise/carvers, model asset wiring) require careful use of Paper's registry access API and may be version-specific.

- Model textures/assets: "applying" a model normally requires resource-pack assets (textures, model files) to be available to clients. Registering model JSON server-side without providing the actual asset files on clients will not display custom textures unless a matching resource pack is present. `item_model` in `ItemBuilder` can point to a model; you still need client-side assets for visuals.

## Recommended next steps to fully replace datapacks at runtime

- Implement runtime application in `DatapackFacade.applyAll()` to map stored JSON into server registries using Paper's `RegistryAccess`/`RegistryKey` APIs and server internals.
- For model assets: provide either a resource-pack delivery mechanism or fall back to only registering behaviors that don't rely on client assets.
- Implement safe rollback / validation and ensure operations run on the main server thread.

## Summary

The new `Datapack` wrapper allows Python code to express everything datapacks can describe and sends that data to Java at runtime. Right now it collects and forwards definitions; to fully match datapacks you need the Java-side application logic (server registry injection and asset delivery) implemented as described above.
