# Share a plot

`save_html` writes the plot into one HTML file, with its data and the code that draws it.
It opens in any browser, without Python or an internet connection, and zooms, hovers,
brushes and opens panels as it does in the notebook.

```python
plot.save_html("fuel-use.html")
plot.save_html("fuel-use.html", title="Fuel use, 1970-1982")  # the browser tab's title
```

`to_html()` returns the same page as a string, to put in an email, a report or a web
app.

## What the page keeps

| In the page | Kept |
| --- | --- |
| Zoom, pan, hover, box zoom, fit y | Yes |
| Brushing and legend clicks | Yes, in the page |
| `link=` within the plot | Yes |
| The panel opened with `open()` and a selection made with `select()` | Yes, as the page opens |
| Plots linked with `link()` | No: Python passes their selection |
| `selected()` | No: there is no Python |

## Size

The page holds the data of the columns the plot draws, plus 70 KB for the code. A few
thousand rows make a page of a few hundred kilobytes; a million points, about 50 MB.
Sample or summarise before saving a page you want to send.

## In other documents

- **A web page or blog**: put the file on the site and link to it, or show it in an
  `<iframe>`.
- **Several plots in one page**: these docs do it; the code that draws plots is loaded
  once, and each plot is a `<div class="anytrellis-embed">` holding its data.
- **A slide**: open the page in a browser and present it, or take a screenshot.
