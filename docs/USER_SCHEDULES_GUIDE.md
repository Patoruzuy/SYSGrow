# Schedule Setup Guide (Simple)

This guide explains schedules in plain language. Use it to set up lights, fans, pumps, and other devices.

## What a Schedule Does

A schedule tells a device when to turn on and off. You can set:
- Start time and end time
- Days of the week
- Optional intensity (for dimmers)

## Schedule Types

### Simple (Time-based)
- The device runs between a start time and an end time.
- Example: Light on from 06:00 to 22:00 every day.

### Interval (Repeating)
- The device turns on for short bursts on a repeating cycle.
- You set:
  - Interval (how often it repeats)
  - Duration (how long each run lasts)
- Example: Fan runs every 120 minutes for 20 minutes.

### Photoperiod (Day/Night aware)
- The schedule uses daylight information to decide if it is day or night.
- You choose a **Photoperiod Source**:
  - **Schedule Only**: Uses the start/end time you set.
  - **Sensor-based**: Uses your light sensor (lux) to detect day/night.
  - **Sunrise/Sunset**: Uses sunrise and sunset times for day/night.
- **Sensor Threshold (lux)** means: *below this value, it is treated as night*.
- For Sensor-based and Sunrise/Sunset, start/end times are optional and auto-set to `00:00–00:00`.

### Automatic (Plant Stage)
- The system uses the active plant’s stage to set the light hours.
- You only choose the start time; the end time is calculated automatically.

## Tips

- If a device should run all day, set start/end to `00:00–00:00`.
- Higher priority schedules override lower ones when they overlap.
- Use Interval schedules for short bursts (like fans or pumps).
- Use Photoperiod schedules for lights when you want day/night behavior.

