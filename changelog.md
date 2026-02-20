
# Changelog

## 2A

Feature update

### Changes

#### Networking

- Optimized for single request latency
- Use batching to speed up multiple requests

#### New APIs

- Tab list API on Player
- Region utils on World
- Particle shapes on World
- Entity spawn helpers on World
- Support for command execution on Server
- world.entities property
- RaycastResult.distance and .hit_face

#### New helpers

- Sidebar: Scoreboard helper
- Config: YAML config helper
- Cooldown: Automatically manage cooldowns
- Hologram: Show floating text
- Menu / MenuItem: Create easy chest GUIs
- ActionBarDisplay: Manage action bars easily
- BossBarDisplay: Manage boss bars easily
- BlockDisplay: Show fake blocks
- ItemDisplay: Show floating items
- ImageDisplay: Show images in the world
- ItemBuilder: Easily create items

#### API improvements

- Fixed type errors regarding EnumValue not matching its child classes
- EntityGoneException now extends BridgeError
- @task decorator: Run tasks on an interval
- Added event priority and throttle_ms parameters
- Added command description parameter
- Location: .add, .clone, .distance, .distance_squared are now sync
- Scoreboard, Team, Objective, and BossBar creation methods are now sync

#### Cleanup

- Entity class moved before Player
- Moved most of the code from a single file to multiple

#### Misc

- Added dev versioning for non-release commits

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
