# Share a plot

A plot can go out as an image, for slides and reports, or as a page that stays
interactive.

## Images for slides and reports

Click the plot's Export button (or press ++e++) and choose:

- **Copy image**: a PNG on the clipboard; paste it into slides, a document or a chat.
- **Copy as vector**: an SVG on the clipboard, sharp at any size, with a PNG beside it
  for apps that don't read SVG. Chrome, Edge and VS Code offer it.
- **Download PNG** or **Download SVG**: a file, named after the plot's title.
- **Save PNG** or **Save SVG next to the notebook**: the file in the folder Python runs
  in, without overwriting one already there.

The image is the plot as you see it: zoom in, select, open a panel or switch to the dark
theme first, and the image shows that. The toolbar, the tooltip and the crosshair are left
out. A PNG is twice the plot's size on screen, so it stays sharp on slides.

An SVG keeps every mark as a vector element, so a plot of many thousands of marks makes a
large file that slides draw slowly; the plot says how large it is. Use a PNG for those.

## A page that stays interactive

`save_html` writes the plot into one HTML file, with its data and the code that draws it.
It opens in any browser, without Python or an internet connection, and zooms, hovers,
brushes and opens panels as it does in the notebook.

```python
plot.save_html("fuel-use.html")
plot.save_html("fuel-use.html", title="Fuel use, 1970-1982")  # the browser tab's title
```

`to_html()` returns the same page as a string, to put in an email, a report or a web
app.

### What the page keeps

| In the page | Kept |
| --- | --- |
| Zoom, pan, hover, box zoom, fit y | Yes |
| Brushing and legend clicks | Yes, in the page |
| `link=` within the plot | Yes |
| The panel opened with `open()` and a selection made with `select()` | Yes, as the page opens |
| Plots linked with `link()` | No: Python passes their selection |
| `selected()` | No: there is no Python |

### Size

The page holds the data of the columns the plot draws, plus 70 KB for the code. A few
thousand rows make a page of a few hundred kilobytes; a million points, about 50 MB.
Sample or summarise before saving a page you want to send.

### In other documents

- **A web page or blog**: put the file on the site and link to it, or show it in an
  `<iframe>`.
- **Several plots in one page**: these docs do it; the code that draws plots is loaded
  once, and each plot is a `<div class="anytrellis-embed">` holding its data.
- **A slide**: export an image (above), or open the page in a browser and present it.
