---
description: Read these instructions to get to know the codebase better.
---

# Codebase instructions

The project is a bridge between Minecraft Java (Paper 1.21.x) and Python. It allows access to all bukkit APIs with easy, pythonic wrappers.

## Quickstart

Read `docs/src/index.md`. Then read other documentation if necessary.

## Documentation usage

Please do rely on the documentation in `docs/src/*`, and use the pjb python script to search quickly.
Examples:

Search for symbol

```example
./pjb search Player

  # Player

  Player extends Entity with player-specific functionality: health, hunger, experience, permissions, inventory, tab list, game mode, and more.

  Player(uuid: str | None = None, name: str | None = None)

  Resolve a player by UUID or name. At least one must be provided. The player must be online.

  - Parameters:
    - uuid (str | None) — The player's UUID.
    - name (str | None) — The player's name (case-insensitive lookup).

  p = Player(name="Steve")
  p = Player(uuid="550e8400-e29b-41d4-a716-446655440000")

  # PlayerDataStore [ext]

  PlayerDataStore provides persistent per-player data storage with dict-style access.

  from bridge.extensions import PlayerDataStore

  PlayerDataStore(name="default")

  Data is saved to plugins/PyJavaBridge/playerdata/<name>/<uuid>.json.
```

Search symbol's fields

```example
./pjb search Player.

Player  (player.md)
 ## Attributes
  ### .name
  ### .uuid
  ### .location
  ### .world
  ### .health
  ### .food_level
  ### .game_mode
  ### .inventory
  ### .level
  ### .exp
  ### .is_op
  ### .is_flying
  ### .is_sneaking
  ### .is_sprinting
  ### .scoreboard
  ### .permission_groups
  ### .primary_group
  ### .tab_list_header
  ### .tab_list_footer
  ### .tab_list_name
 ## Methods
  ### .send_message(message)
  ### .chat(message)
  ### .kick(reason="")
  ### .teleport(location)
  ### .give_exp(amount)
  ### .set_exp(exp)
  ### .set_level(level)
  ### .set_health(health)
  ### .set_food_level(level)
  ### .set_game_mode(mode)
  ### .set_op(value)
  ### .set_flying(value)
  ### .set_sneaking(value)
  ### .set_sprinting(value)
  ### .set_walk_speed(speed)
  ### .set_fly_speed(speed)
  ### .set_scoreboard(scoreboard)
 ## Effects
  ### .effects
  ### .add_effect(effect)
  ### .remove_effect(effect_type)
 ## Sounds & UI
  ### .play_sound(sound, volume=1.0, pitch=1.0)
  ### .set_resource_pack(url, hash="", prompt=None, required=False)
  ### .send_action_bar(message)
  ### .send_title(title, subtitle="", fade_in=10, stay=70, fade_out=20)
 ## Tab List
  ### .set_tab_list_header(header)
  ### .set_tab_list_footer(footer)
  ### .set_tab_list_header_footer(header="", footer="")
  ### .set_tab_list_name(name)
 ## Permissions
  ### .has_permission(permission)
  ### .add_permission(permission, value=True)
  ### .remove_permission(permission)
  ### .has_group(group)
  ### .add_group(group)
  ### .remove_group(group)
```

Search for details on a specific field

```example
./pjb search Player.play_sound
Player.play_sound  (Sounds & UI)

  await player.play_sound(sound, volume=1.0, pitch=1.0)

  Play a sound to the player at their location.

  - Parameters:
    - sound (Sound) — The sound to play.
    - volume (float) — Volume. Default 1.0.
    - pitch (float) — Pitch. Default 1.0.
  - Returns: Awaitable[None]

  await player.play_sound(Sound.ENTITY_EXPERIENCE_ORB_PICKUP)
  await player.play_sound('block_note_block_bass', volume=0.5, pitch=2.0)
```

## Work policy

After you are done with something, you must update the documentation and type stub file(s).
The documentation is built into html files by the build.py script. It is automatically ran via github actions when deploying to github pages, so you dont have to run it yourself.

## User API rules

This section guides you on what the user API should look like.

Here are a few key points:

- Use decorators when convenient
- Large new features should be extensions
- Document everything: docstrings, type stubs, markdown source files
- Accept multiple types as argument: If something has an enum, accept the enum type AND string.
- Transparent errors: Raise specific errors while maintaining the stack trace
- Properties should be synchronous: No awaiting to get attributes
- Encourage efficient user code: Make it easy for users to optimize their code
- Use defined wrapper classes: Users should see all the properties via autocompletions
