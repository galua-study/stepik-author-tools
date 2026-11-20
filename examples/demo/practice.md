## Task 1.1.4. Local practice

**Type:** local self-check

### Condition

Write a function that adds one to an integer.

### Self-check

Run these assertions locally:

```python
assert increment(0) == 1
assert increment(-1) == 0
```

### Correct answer

```python
def increment(value: int) -> int:
    return value + 1
```

### Explanation

PRIVATE DEMO KEY: addition also works for negative integers.
