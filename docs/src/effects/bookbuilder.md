---
title: BookBuilder
subtitle: Build written book items with a fluent API
---

# BookBuilder

`BookBuilder` creates written book `Item` objects with a fluent interface.

```python
from bridge import BookBuilder

book = (BookBuilder("My Guide", "Server")
        .page("Welcome to the server!")
        .page("Chapter 2: Rules")
        .page("Chapter 3: Commands")
        .build())

await player.open_book(book)
```

## Constructor

### BookBuilder(title="Book", author="Server")

- **Parameters:**
  - `title` *(str)* — Book title. Default `"Book"`.
  - `author` *(str)* — Book author. Default `"Server"`.

## Methods

All setter methods return `BookBuilder` for chaining.

### .title(title)

Set the book title.

- **Parameters:**
  - `title` *(str)* — New title.
- **Returns:** `BookBuilder`

### .author(author)

Set the book author.

- **Parameters:**
  - `author` *(str)* — New author.
- **Returns:** `BookBuilder`

### .page(content)

Add a single page.

- **Parameters:**
  - `content` *(str)* — Page text content.
- **Returns:** `BookBuilder`

### .pages(*contents)

Add multiple pages at once.

- **Parameters:**
  - `*contents` *(str)* — Page text contents.
- **Returns:** `BookBuilder`

```python
book = (BookBuilder("Story")
        .pages("Once upon a time...",
               "The hero ventured forth...",
               "The end.")
        .build())
```

### .build()

Build the final book item.

- **Returns:** `Item` — A written book ItemStack.
