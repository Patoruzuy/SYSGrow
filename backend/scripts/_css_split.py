# (one-off CSS split helper — completed, can be deleted)
import os

src = 'static/css/components.css'

f = open(src, encoding='utf-8').readlines()
original_len = len(f)

# Find the buttons @import line index (0-based)
import_idx = next(i for i, line in enumerate(f) if "@import 'components/buttons.css'" in line)

new_imports = [
    "@import 'components/modals.css';\n",
    "@import 'components/charts.css';\n",
    "@import 'components/sensor-analytics.css';\n",
    "@import 'components/plant-devices.css';\n",
]

# Build the new file by stitching parts (original indices, before any editing):
# 0 .. import_idx        -> header + buttons import (keep)
# import_idx+1 .. 681    -> between buttons import and modals start (keep: grids, alerts, cards)
# 682 .. 1202            -> modals section  (REPLACED with stub)
# 1203 .. 1638           -> plant-cards, actuators, quick-stats etc. (KEEP)
# 1639 .. 2815           -> Chart & ML Visualization (REPLACED with stub)
# 2816 .. 3823           -> Sensor Analytics (REPLACED with stub)
# 3824 .. 4201           -> Plant Device Management (REPLACED with stub)
# 4202 ..                -> Contextual Help, Alert/Banner, List Group (KEEP)

modals_stub  = ['/* Extracted: see components/modals.css */\n', '\n']
charts_stub  = ['/* Extracted: see components/charts.css */\n', '\n']
sa_stub      = ['/* Extracted: see components/sensor-analytics.css */\n', '\n']
pd_stub      = ['/* Extracted: see components/plant-devices.css */\n', '\n']

new_file = (
    f[0:import_idx + 1]           # up to and including buttons import
    + new_imports                  # 4 new @import lines
    + f[import_idx + 1 : 682]      # grids, alert-timeline, cards sections
    + modals_stub                  # stub replaces modals block
    + f[1203 : 1639]               # plant-cards + misc shared components
    + charts_stub                  # stub replaces charts block
    + sa_stub                      # stub replaces sensor-analytics block
    + pd_stub                      # stub replaces plant-devices block
    + f[4202:]                     # contextual help, alert, list-group
)

with open(src, 'w', encoding='utf-8') as out:
    out.writelines(new_file)

print(f"Done. components.css: {original_len} -> {len(new_file)} lines")
print("\nFirst 15 lines:")
for i, line in enumerate(new_file[:15]):
    print(f"  {i+1:3d}: {line}", end='')

print("\nLast 10 lines of @import block (lines 6-10):")
for i in range(5, 12):
    print(f"  {i+1:3d}: {new_file[i]}", end='')
