
# Changelog

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
