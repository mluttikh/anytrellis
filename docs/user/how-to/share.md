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

For slides, make the plot with `theme=at.Theme(context="talk")` (or `set_theme(context=
"talk")` once): its text, lines and points are 1.5 times as big, so they read from the back
of the room ([Text size, and plots for slides](layout.md#text-size-and-plots-for-slides)).

An SVG keeps every mark as a vector element, so a plot of many thousands of marks makes a
large file that slides draw slowly; the plot says how large it is. Use a PNG for those.

### From Python: scripts and reports

`save_png` and `save_svg` write the image from Python, with no browser: in a script, a
scheduled report or a CI job.

```python
plot.save_png("fuel-use.png")                     # twice the plot's size, as the button
plot.save_svg("fuel-use.svg")
plot.save_png("slide.png", width=1200, height=600, theme="dark")
plot.save_png("thumbnail.png", width=400, scale=1)
```

It is the plot as shown in the notebook: the zoom you last looked at, the selection, a
linked plot's highlight and an opened panel (`open()`). A plot that was never shown is
drawn whole, 800 pixels wide; `width` and `height` set the size, in the same pixels as on
screen, and `scale` the PNG's pixels per one of them.

PNGs need `resvg-py`, which draws the SVG:

```bash
pip install "anytrellis[png]"
```

### For print: mm, dpi and PDF

A journal asks for a figure 180 mm wide at 300 dpi, or a vector PDF. `width` and `height`
take lengths as well as pixels, and the PNG takes a `dpi`:

```python
plot.save_pdf("figure-2.pdf", width="180mm")             # vector, text kept as text
plot.save_svg("figure-2.svg", width="180mm")             # printed 180 mm wide
plot.save_png("figure-2.png", width="180mm", dpi=300)    # 2125 pixels wide, 300 dpi
plot.save_png("poster.png", width="40cm", height="30cm", dpi=150)
```

A length is `"180mm"`, `"18cm"`, `"7in"` or `"500pt"`. The plot lays out at that size in
CSS pixels, 96 to the inch, so its 12 px text prints at 9 pt, the size journals ask for;
make the text larger for a poster with `context="poster"` or the theme's `font_size`
(`at.set_theme(font_size=14)`). The SVG and the PDF say their printed size, and the PNG records its dpi, so a word
processor or LaTeX places each at its size. `dpi` replaces `scale`: `dpi=300` is
`scale=3.125`.

The PDF is drawn from the same SVG: every mark a vector shape and every label text you
can search and copy, its fonts embedded. It needs `vl-convert-python`, a wheel with no
system libraries:

```bash
pip install "anytrellis[pdf]"
```

A [figure of several plots](figures.md) takes the same `width` and `dpi`, and has
`save_pdf` too.

### Every page of a paged plot, one PDF

A paged plot's image is the page shown. `pages=` puts pages in one PDF, each on a page of
its own: `"all"`, in the order the plot shows them (sorted and filtered as it is), or a
list of their numbers or names. Each says under the title which page it is ("Page 2 of
7", or the level of `page=`: "region: coast"), as the page bar does, and is a bookmark of
the PDF.

```python
stations.save_pdf("stations.pdf", pages="all", width="180mm")   # a report of every page
regions.save_pdf("two.pdf", pages=["south", "coast"])           # page="region": by name
```

The plot shown stays on its page. Each page is its grid, not a panel opened. With
`load="pages"`, Python reads the rows a few pages at a time, as it does when you turn
them, so a PDF of a large table's pages needs the memory of a page, not of the table.
Joining the pages needs `pypdf`, in the same `pdf` extra.

Python draws the text in a common sans-serif font, so the labels can look slightly
different from the browser's. The Export menu's images are the browser's own.

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
| Plots linked with `link()` | Yes, saved together with `Link.save_html` ([link plots](link.md#save-linked-plots-to-one-page)) |
| Views (`save_view`, or kept in the page) | Yes; a link ending `#view=<name>` opens on one. Views kept in the page last until it closes |
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
