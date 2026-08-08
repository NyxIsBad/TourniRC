S:/Code/TourniRC/.venv/Scripts/activate

Currently need to:

Fixes:
- I am rebuilding the entire fucking tournament overlay for every Bancho event, via ui.py:81. Should probably:
  - Use internal tournament for score calc and send full tournament only when assignment/config changes, can do assignment/score updates with match_state events
- Split score rendering from mappool rendering (chat.html:630), should split into functions renderTournamentControls, renderMappool, renderScore, renderTournamentTabColors. 
  - See if doing this can make the commit mappool rendering was flickering redundant (eg we can override the fix with better architecture)
- Shit that's probably just bad design: 
  - handle_recv_msg in general is terrible, it does a billion things. 
  - I'm reconstructing tournament sound triggers for every single message and it results in some insane comprehension/nested dictionary bullshit
  - Tournament validation is done a billion times, and only needs to be done at load/save/create/duplicate/delete

All Socket IO tags:
- connect: UI connects to UI server, gets the current connection_state (also sets up debug chats if relevant)
- disconnect: UI disconnects from UI server, currently just gets logged
- backend_identity_request: UI to UI server, asks which backend instance it is connected to
  - backend_identity: UI server to UI, has backend instance id and whether credentials exist so frontend/backend restarts can be detected
- connection_state: UI server to UI, current connecting/authenticated/reconnecting/auth failed/logged out state
- irc_state: IRC server to UI server, updates connection_state with attempt/retry/reason info
- irc_retry: UI to UI server, requests an immediate IRC reconnect
  - cmd_reconnect: UI server to IRC server, tells the IRC supervisor to retry now
- login_submit: UI to UI server, submits pending username/password
  - cmd_login: UI server to IRC server, starts a login session
  - login_result: UI server to UI, says whether the submitted login form was accepted
- logout: UI to UI server, clears credentials/chats/recent rooms and logs out
  - cmd_logout: UI server to IRC server, stops the IRC session
  - logout_complete: UI server to UI, redirects back to login
- nickname: IRC server to UI server, sets current osu! username
- session_state: IRC server to UI server, returns open chats and the current chat so reconnect can restore them
- browser_ready: UI to UI server, asks to restore tabs, recent rooms, connection state, tournaments, and current tab after the page is actually ready
- restore_tab: IRC/UI server to UI, selects the tab that was current before a reconnect/page reload

- tab_open: IRC to UI server, results in a bounce (added to Chats)
  - bounce_tab_open: UI server to UI, Create the tab
- cmd_req_ch: UI server to IRC server, asking for a joinChannel
- tab_swap: UI to UI server, returns with messages
  - tab_swap returns response data via the sio ack callback
- tab_close: UI to UI server, deletes the chat.
  - bounce_tab_close: Close the connection by leaving the channel
- cmd_part: UI server to UI, deletes the chat by having the UI click the close button on the relevant chat if it exists.
- tab_reorder: UI to UI server, saves current drag/drop tab order
- tab_unread: UI server to UI, marks a non-current tab as unread
- change_alias: UI to UI server, sets alias of a chat
- alias_changed: UI server to UI, updates tab alias and refreshed channel info
- cmd_clear: UI server to UI, clears messages in the current tab
- cmd_savelog: removed
  - cmd_savelog_response: UI server to UI, has messages
- recv_msg: IRC to UI server, results in a bounce (added to Chats)
  - bounce_recv_msg: UI server to UI, added to current tab
- send_msg: UI to UI server, results in a bounce
  - bounce_send_msg: UI server to IRC server

- recent_room_open: UI to UI server, rejoins a room from recent rooms
- recent_room_remove: UI to UI server, removes one recent room
- recent_rooms_clear: UI to UI server, clears all recent rooms
- recent_rooms_limit: UI to UI server, sets and saves recent rooms limit
  - recent_rooms_state: UI server to UI, has recent rooms and current limit

- set_timer: UI to UI server, sets timer value of current chat
  - set_timer_input: UI server to UI, sets timer input value
- set_start_timer: UI to UI server, sets start timer value of current chat
  - set_start_timer_input: UI server to UI, sets start timer input value
- match_state: UI server to UI, has current match/channel info, players, timers, and tournament overlay
- team_change: TODO: we can remove this sio emission, because things are kind of just done in the backend, and everything else is given through team_overrides, emit match state, etc
- team_change (Current): UI server to UI, applies team color immediately when BanchoBot sends a team change

- notif: UI server to UI, creates a temporary toast.
  - Info: Unread Notifications, chat open, 
  - Warning: Incorrect command syntax
  - Error: Incorrect key instances
  - Success: 
- blocked_pm: UI server to UI, creates/updates grouped notification for a blocked PM
- play_sounds: UI server to UI, plays all global/tournament sounds matching a received message

- theme: UI to UI server, validates and saves current theme
- settings_get: UI to UI server, returns all current settings and available sound assets
- settings_update: UI to UI server, validates/saves one settings section
- settings_reset: UI to UI server, resets one visible settings section
  - settings_changed: UI server to UI, refreshes settings/hotkeys/macros/audio anywhere they are in use
- run_macro: UI to UI server, runs a saved macro by id (and optionally for a specific channel)
  - macro_confirmation: UI server to UI, asks for confirmation before an aliased macro is sent
- sound_delete: UI to UI server, deletes custom sound if no trigger is using it

- tournament_list: UI to UI server, returns tournament enabled state, tournament list, assignments, mods, and sounds
- tournament_create: UI to UI server, creates and returns a new tournament
- tournament_validate: UI to UI server, validates current tournament editor draft
- tournament_import_mappool: UI to UI server, parses pasted mappool commands into maps
- tournament_fetch_map_metadata: UI to UI server, fetches name/difficulty metadata for an osu! map id
- tournament_save: UI to UI server, validates and saves tournament editor draft
- tournament_duplicate: UI to UI server, duplicates tournament with new id/name
- tournament_delete: UI to UI server, deletes an unassigned tournament
- tournament_toggle: UI to UI server, enables/disables tournament features globally
- tournament_clear_assignments: UI to UI server, clears a tournament from every assigned match tab
- tournament_assign: UI to UI server, assigns/unassigns tournament for match tab and applies its timers
- tournament_select_pool: UI to UI server, sets selected mappool for match tab
- tournament_pick_map: UI to UI server, sends map/mods commands and optional map timer
- tournament_score_mods: UI to UI server, overrides a player's score calculation mods
  - tournament_state: UI server to UI, refreshes global tournament configuration/list/usage/assets
  - tournament_overlay: UI server to UI, refreshes assignment, selected tournament, score calculation, and winner for one match tab

- debug: UI to UI server, only triggered on console command, spits out something as I need.
