# TourniRC

TourniRC is an indev iRC client aiming to be a tournament client for osu built on python and flask. As a consequence of commonplace sheet practice, some commands & features that I would honestly like to have for the sake of completeness weren't added because it would make them redundant. It will aim to do what BrigittaBlazor and c4o haven't done by providing (most of which are still unimplemented):

## Features you're familiar with from Brigitta / c4o:
- Buttons to send ref commands (timers, aborts, starts, setting, clearhost)
  - But not invite, move, kick, ban, pw, etc because they're redundant by way of sheet
- Team displays (who's in the room, what's their teams, their mods)
- Audio triggers for preset events & custom chat triggers
- Saving logs
- Automatic dc/rc logic

## New Features:
- Stronger disconnect logic, including saving open rooms and automatically reconnecting to them, preserving chat history, etc. 
- Block list
  - Settings for users
- Hotkeys to change channels
  - And the ability to reorder them
- Persistent tab specific timer storage for individual tournaments
  - Also includes persistence for your login.
- Tournament specific configs that allow you to send map change commands with a button press
  - (after configuration in the client of course)
- A new modern UI powered by Tailwind & DaisyUI
  - Including moving the channel swapping to the sidebar, custom font sizes, and a collapsible actions section on the right of the screen to allow for more things to happen
  - 32 themes because dark and pink are cool I think
- Short term room history to allow you to join back quickly after an accidental disconnect

## Potential Future Features?
- Automatic score tracking/map winner tracking so you don't have to check the mp link/watch the game/use a slow sheet api
- Hotkeys to send commands?

# Contributing

- Git clone the repo
- `pip install -r requirements.txt`
- `npm run main`

## Portable Windows build

Install Python build dependencies with `uv pip install -r requirements-build.txt`,
then run `powershell -ExecutionPolicy Bypass -File .\build-windows.ps1`. It will write a versioned ZIP under `dist\`.

Writable `cfg\` and `logs\` directories are created beside the
executable.

## Creating a release

```bash
git tag -a v1.1.0 -m "TourniRC 1.1.0"
git push origin v1.1.0
```

can also be started manually from the repository's
actions tab for an existing `v`-prefixed tag

## Diagnostic Logs

TourniRC writes its runtime diagnostics to `logs/` automatically:

- `irc.log` contains the traditional human-readable application log and is reset on startup.
- `irc-events.log` contains rotating JSON-lines records for raw IRC traffic, parsed IRC events, errors, and reconnect state.
- `ui-events.log` contains rotating JSON-lines records for browser and Socket.IO activity.

IRC passwords and tokens are automatically replaced with `[REDACTED]`. Chat messages and channel names are retained for debugging, so log files should still be treated as private. Structured event logs rotate at 5 MB and retain three backups.

## Message Delivery During Connection Loss

irc is shit and does not have acks for message sends. thus, TourniRC does not automatically resend messages after reconnecting. This is intentional: replaying referee commands such as abort, timer, or match-control commands can duplicate. I added a warning but there is a stale window between when you can dc and when things are back, so if you get a reconnect window, you might have lost some state.

## Settings and Help

Read help page

## Configuration files

- `cfg/login.ini` contains the saved IRC username and password after a successful login
- `cfg/settings.json` contains configuration
- `cfg/recentrooms.ini` contains recent match-room history
- `cfg/sounds/` contains custom sound uploads

If `cfg/settings.json` is malformed, TourniRC preserves a timestamped `.invalid-...json` copy and starts with safe defaults.
