S:/Code/TourniRC/.venv/Scripts/activate

Currently need to:
- Send messages
- Login screen
- Disconnect screen

- Ping timeout
- All the features in readme
- Figure out disconnect reasons
- Tournament config + functionality
  - Timezone toggling
  - Buttons to send
    - Map start
    - Map abort
    - Timer
    - Map Commands by clicking a button (read from map pool info) 
  - Sound alerts
- Test message functionality
  - /me messages


- Resolve all TODO tags in all files and ID tags in HTML
  - all CNAMES are also following ID

Go through HTML and use classes (h1, span, etc) correctly
24 hour/12 hour time swap

All Socket IO tags:
- recv_msg: IRC to UI server, results in a bounce (added to Chats)
  - bounce_recv_msg: UI server to UI, added to current tab
- send_msg: UI to UI server, results in a bounce
  - bounce_send_msg: UI server to IRC server
- tab_swap: UI to UI server, returns with messages (TODO: Make this async promise)
- tab_close: UI to UI server, deletes the chat. (TODO: Delete the chat on the UI as well)
  - bounce_tab_close: Close the connection by leaving the channel (TODO: implement)
- tab_open: IRC to UI server, results in a bounce (added to Chats)
  - bounce_tab_open: Create the tab