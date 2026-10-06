---
description: Негативный кейс. Мелкая правка не должна запускать подбор инструментов.
expected_outcome: Claude просто переименовывает переменную; skill-scout не вызывается.
tags: [negative]
max_turns: 5
timeout_seconds: 180
allowed_tools: [Skill, Read]
---

Переименуй в этом фрагменте переменную x в total и покажи результат:

x = 0
for i in range(10):
    x += i
print(x)
