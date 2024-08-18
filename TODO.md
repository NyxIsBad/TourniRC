S:/Code/TourniRC/.venv/Scripts/activate

TODAY:
- Team colors
- Timezone toggles

Currently need to:
- Login screen (Do I even want to do this? Maybe it's better just to terminal log and ask user to set up the ini, since login/disconnect would require me to stop and start entire irc clients)
- Disconnected screen/logout

- Ping timeout
- All the features in readme
  - Block list
  - Room history (new UI panel)
- Team colors (and write in regex irclib side)
- Tournament config + functionality (Need a screen to add these, incorporate into settings?)
  - Timezone toggling
  - Buttons to send
    - Map Commands by clicking a button (read from map pool info) 
  - Sound alerts
- Test message functionality
  - /me messages


- Resolve all TODO tags in all files and ID tags in HTML
- Automatically send "tab_swap" of current under the following condition: client stays open, and reconnects to server while server down. 
  - Should be part of dc/rc logic since dc can clear chat
- Go through HTML and use classes (h1, span, etc) correctly
- 24 hour/12 hour time swap button (new Quick Actions UI panel?)
- UTC/Local time swap button
- Download chat logs feature (new UI panel?)
- hotkeys.js <- not touched at all need to do all of this

All Socket IO tags:
- recv_msg: IRC to UI server, results in a bounce (added to Chats)
  - bounce_recv_msg: UI server to UI, added to current tab
- send_msg: UI to UI server, results in a bounce
  - bounce_send_msg: UI server to IRC server
- team_change: TODO: Implement - UI server to UI, change team color by tagging them.
- tab_swap: UI to UI server, returns with messages
  - tab_swap_response: UI server to UI, has messages
- tab_close: UI to UI server, deletes the chat.
  - bounce_tab_close: Close the connection by leaving the channel (TODO: implement in irclib (PART))
- tab_open: IRC to UI server, results in a bounce (added to Chats)
  - bounce_tab_open: Create the tab
- cmd_req_ch: UI server to IRC server, asking for a joinChannel
- cmd_part: UI server to UI, deletes the chat by having the UI click the close button on the relevant chat if it exists.
- set_timer: UI to UI server, sets timer value of current chat
- set_match_timer: UI to UI server, sets mt value of current chat