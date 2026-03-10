---
title: TextComponent
subtitle: Rich text builder using MiniMessage format
---

# TextComponent

`TextComponent` builds rich text with formatting, colors, gradients, and click/hover actions using [MiniMessage](https://docs.advntr.dev/minimessage/index.html) format. All methods return `self` for fluent chaining.

```python
from bridge import TextComponent

msg = (TextComponent("Hello ")
       .bold("world")
       .color("#ff5555", "!")
       .click_command("/help", " [Click for help]"))

await player.send_message(str(msg))
```

## Constructor

### TextComponent(text="")

Create a new component, optionally starting with plain text.

- **Parameters:**
  - `text` *(str)* — Initial text content. Default `""`.

```python
tc = TextComponent()
tc = TextComponent("Hello")
```

## Formatting Methods

All formatting methods return `TextComponent` for chaining.

### .text(content)

Append plain text.

### .bold(content)

Append **bold** text.

### .italic(content)

Append *italic* text.

### .underlined(content)

Append underlined text.

### .strikethrough(content)

Append ~~strikethrough~~ text.

### .obfuscated(content)

Append obfuscated (magic) text.

## Color & Gradient

### .color(color, content)

Append colored text.

- **Parameters:**
  - `color` *(str)* — Hex color (`#ff5555`) or named color (`red`).
  - `content` *(str)* — Text to color.

```python
tc.color("#00ff00", "Green text")
tc.color("gold", "Gold text")
```

### .gradient(colors, content)

Append gradient text.

- **Parameters:**
  - `colors` *(list[str])* — List of hex colors.
  - `content` *(str)* — Text to apply gradient to.

```python
tc.gradient(["#ff0000", "#0000ff"], "Rainbow!")
```

## Click Actions

### .click_url(url, content="")

Make text open a URL when clicked.

- **Parameters:**
  - `url` *(str)* — URL to open.
  - `content` *(str)* — Display text. If empty, shows the URL.

### .click_command(command, content="")

Make text run a command when clicked.

- **Parameters:**
  - `command` *(str)* — Command to execute (e.g. `/help`).
  - `content` *(str)* — Display text. If empty, shows the command.

### .click_suggest(command, content="")

Make text suggest a command in chat when clicked.

### .click_copy(text, content="")

Make text copy to clipboard when clicked.

## Hover

### .hover(hover_text, content="")

Add hover tooltip text.

- **Parameters:**
  - `hover_text` *(str)* — Text shown on hover.
  - `content` *(str)* — Display text. If empty, shows hover_text.

## Utility

### .newline()

Append a newline character.

## Operators

### str(component)

Convert to MiniMessage format string.

### component + other

Concatenate two TextComponents or a TextComponent and a string.

```python
msg = TextComponent("Hello ") + TextComponent().bold("world")
await player.send_message(str(msg))
```
