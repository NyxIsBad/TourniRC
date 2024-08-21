# TourniRC

TourniRC is an indev iRC client aiming to be a tournament client for osu built on python and flask. As a consequence of commonplace sheet practice, some commands & features that I would honestly like to have for the sake of completeness weren't added because it would make them redundant. It will ims to do what BrigittaBlazor and c4o haven't done by providing (most of which are still unimplemented):

## Features you're familiar with from Brigitta / c4o:
- Buttons to send ref commands (timers, aborts, starts, setting, clearhost)
  - But not invite, move, kick, ban, pw, etc because they're redundant by way of sheet
- Team displays (who's in the room, what's their teams, their mods)
- Audio triggers for preset events & custom chat triggers
- Saving logs
- Automatic dc/rc logic

## New Features:
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
- `npm run build` (Required anytime you make changes to the templates/js)
- Run main.py