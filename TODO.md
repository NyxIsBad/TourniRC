S:/Code/TourniRC/.venv/Scripts/activate

Currently need to:

- All TODO tags
- Settings page as a toast:
  - Custom banchobot color
  - Panels for setting room history limit
  - Block list
  - Configure a tournament
    - Going to want to add a button on the tournament tab to jump to this

- Help page as a toast:
  - Explain command shorthands
  - Hotkeys??
  - How to navigate settings page and change themes
  - How to log in (.ini)

- All the features in readme
  - Room history (finish buttons to open a room, clear individually, clear all)
- Double click tab to rename
- Tournament tab
  - Buttons to send
    - Map Commands by clicking a button (read from map pool info) 
  - Sound alerts

- Unread flags that change whether or not the unread notif shows up + whether or not special highlights show up on the tab.
- Pinned msg (Hotbar on top)?
- hotkeys.js <- not touched at all need to do all of this

- Disconnected screen/logout
- Completely refactor the login situation with osu_irc 
- Automatically send "tab_swap" of current under the following condition: client stays open, and reconnects to server while server down. 
  - Should be part of dc/rc logic since dc can clear chat

All Socket IO tags:
- recv_msg: IRC to UI server, results in a bounce (added to Chats)
  - bounce_recv_msg: UI server to UI, added to current tab
- send_msg: UI to UI server, results in a bounce
  - bounce_send_msg: UI server to IRC server
- team_change: TODO: Implement - UI server to UI, change team color by tagging them.
- tab_swap: UI to UI server, returns with messages
  - tab_swap_response: UI server to UI, has messages
- tab_close: UI to UI server, deletes the chat.
  - bounce_tab_close: Close the connection by leaving the channel
- tab_open: IRC to UI server, results in a bounce (added to Chats)
  - bounce_tab_open: UI server to UI, Create the tab
- notif: UI server to UI, creates a temporary toast.
  - Info: Unread Notifications, chat open, 
  - Warning: Incorrect command syntax
  - Error: Incorrect key instances
  - Success: 
- cmd_req_ch: UI server to IRC server, asking for a joinChannel
- cmd_part: UI server to UI, deletes the chat by having the UI click the close button on the relevant chat if it exists.
- cmd_savelog: UI to UI server, asks for savelog info for a channel (Unused**)
  - cmd_savelog_response: UI server to UI, has messages
- set_timer: UI to UI server, sets timer value of current chat
  - set_timer_input: UI server to UI, sets timer input value
- set_match_timer: UI to UI server, sets mt value of current chat
  - set_match_timer_input: UI server to UI, sets mt input value
- change_alias: UI to UI server, sets alias of a chat

- debug: UI to UI server, only triggered on console command, spits out something as I need.