# Mouse and keys

Click a plot first: before a click, scrolling scrolls the page and keys go to the
notebook. After it, the keys below go to the plot, and stay there, so JupyterLab's own
shortcuts don't also act on them.

## Mouse and trackpad

| Do | Over | To |
| --- | --- | --- |
| Scroll | a panel | zoom x, at the pointer |
| Shift+scroll | a panel | zoom y |
| Scroll | an axis | zoom that axis alone |
| Drag | a panel | pan |
| Drag | an axis | pan that axis alone |
| Double-click | an axis | reset that axis |
| Shift+drag | a panel | box zoom: sideways zooms x, up or down zooms y, otherwise both |
| Hover | a mark | its values, and a crosshair in every panel that shares x |
| Double-click | a panel | see it alone |
| Click | a legend entry | select that colour's marks |
| Shift, Cmd or Ctrl+click | a legend entry | add or remove a colour |

Zoom and pan apply to every panel that shares the scale. An axis stands for its whole
scale: with `share_y="row"`, zooming the left axis of a row zooms that row.

## Keys

| Key | Does |
| --- | --- |
| ++r++ or ++0++ | reset the zoom |
| ++u++, ++cmd+z++ or ++ctrl+z++ | undo the last zoom |
| ++z++ | drag draws a zoom box, and back (Shift+drag always does) |
| ++y++ | fit y to the data in view, and keep fitting it as x changes; again to stop |
| ++s++ | drag draws a selection brush, and back |
| ++esc++ | clear the selection; with none, back to all panels |
| ++enter++ | open the panel under the pointer |
| ++page-up++ / ++page-down++ | the previous / next panel, at the same zoom |
| ++backspace++ | back to all panels |
| ++f++ | full screen, and back |

## The toolbar

The buttons at the top right do the same as keys: box zoom (++z++), select (++s++), fit y
(++y++), reset (++r++) and full screen (++f++). With a panel opened, the strip over it has
*All panels* and the previous and next buttons.

## Selecting

With ++s++ (or the select button), a drag draws a brush, shaped as a zoom box is: x, y or
both. It selects the marks it meets in every panel, and the rest fade.

| What | Is selected when |
| --- | --- |
| a point | it is inside the brush |
| a line or area segment | either end is inside |
| a bar or rect | it overlaps the brush |
| a box | its body or lines are met |
| a histogram bin | it overlaps the brush |
| grey context (`facet="exclude"`), text, rules | never |

Drag the brush to move it; a click or ++esc++ clears it. With a legend colour chosen too,
a mark must meet both.

## Full screen

Browsers allow full screen only from a click or a key, so not from Python. Where a page
forbids it (some notebook frames, Safari on iPhone) the button is not shown.
