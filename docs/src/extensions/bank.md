---
title: Bank [ext]
subtitle: Global currency / bank system
---

# Bank [ext]

`Bank` provides per-player balance tracking with persistent JSON storage.

```python
from bridge.extensions import Bank
```

---

## Constructor

```python
Bank(name="default", currency="coins")
```

Data is saved to `plugins/PyJavaBridge/banks/<name>.json`.

---

## Methods

### balance(player) → float

### deposit(player, amount)

### withdraw(player, amount) → bool

Returns `False` if insufficient funds.

### transfer(from_player, to_player, amount) → bool

### set_balance(player, amount)

---

## Decorators

### @bank.on_transaction

```python
@bank.on_transaction
def logged(player, amount, action, bank):
    print(f"{player.name}: {action} {amount}")
```

---

## Class Methods

### Bank.get(name) → Bank | None

Retrieve a bank by name.

---

## Player Integration

Set `Player._default_bank = my_bank` to enable `player.balance`, `player.deposit()`, `player.withdraw()`.
