---
title: Paginator
subtitle: Multi-page menu
---

# Paginator

`Paginator` extends [`Menu`](menu.md) with multi-page navigation. The last row is reserved for prev/next buttons and a page indicator.

---

## Constructor

```python
Paginator(title="", rows=3, items=None)
```

- **Parameters:**
  - `title` (`str`) — Menu title.
  - `rows` (`int`) — Rows per page (1–6). Last row is navigation.
  - `items` (`list[MenuItem] | None`) — Items auto-distributed across pages.

---

## Properties

### page_count → int

Number of pages.

---

## Methods

### add_page() → int

Add an empty page, returns the page index.

### set_page_item(page, slot, menu_item)

Set an item on a specific page and slot.

### open(player, page=0)

Open the menu on a specific page.

---

## Example

```python
items = [MenuItem(f"Item {i}") for i in range(50)]
paginator = Paginator("§6Shop", rows=4, items=items)
paginator.open(player)
```

Navigation buttons (arrows) appear automatically when there are multiple pages.
