# Map controls

[Documentation index](README.md)

These controls work in both RE1 and RE2. Use Tab to focus the map or an explored room. A bright border marks the focused map. Focused rooms have a thicker wall highlight; the current room keeps its white outline.

| Key | Action while the map or a room has focus |
| --- | --- |
| Arrow keys | Move the view in that direction |
| `+` or `=` | Zoom in |
| `-` | Zoom out |
| `0` | Fit all explored rooms on the displayed floor |
| Enter or Space | Inspect the focused room |

The mouse wheel and zoom buttons also zoom; dragging moves the map. Navigation keeps the selected room and reveals no unexplored rooms. Live updates preserve the chosen view and focused room. If the focused outline disappears, focus moves to the map. Keyboard controls pause when tracking is interrupted or the floor has no outlined rooms. Browser shortcuts and typing outside the map keep their usual behavior.

Use **Floor** to browse explored floors and **Follow player** to return to the current floor and resume selecting rooms as you enter them.

Restarting the tracker refreshes an open map tab to load the matching game and playthrough. The tab clears the previous map while loading and resets search, Back history, zoom and pan. Saved exploration comes from the restarted tracker. Temporary game-read or connection errors during the same run retain the chosen view and search for recovery. If the map asks you to reload, reload the tab to reconnect.

## Find items and rooms

Use **Find item or room** to filter remaining items and unresolved checks by their displayed names, room or floor. Matching **Cleared rooms** appear separately when you search by room or floor name. Select a result to inspect its room on the map. Collected items do not become remaining-item matches. Escape clears the search and restores the normal item overview. Results include explored rooms only and follow fresh tracking state.

Live updates keep keyboard focus on the same room result, preferring its current section. Focus follows a room into another section or returns to search when the room leaves the results. Updates within one section preserve page scroll. An interruption moves result focus to the room details; recovery keeps that keyboard position.

## Inspect connected rooms

Select an underlined destination in **Doors** to inspect its explored room. The tracker switches floors when needed and centers the recorded outline, retaining zoom when it fits. The room details receive focus when the current room has no outline. Door access continues to reflect game state. Destinations without a recorded map view stay as text. **Follow player** resumes tracking the room you enter.

## Return to previous inspections

**Back** retraces room selections, door/item results and floor browsing in the current browser session. It restores the previous zoom and pan while showing fresh items, completion and door access. Zooming, panning and live player movement do not add entries. Repeatedly selecting the same view adds no extra step. **Follow player** clears this inspection history and resumes following.

Only views still available in explored history remain accessible. A room without an outline can be revisited through Back while it remains the same current room. Back is disabled during interrupted tracking and recovers valid entries when tracking returns.
