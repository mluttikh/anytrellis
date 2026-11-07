# Upgrading

What to change in your code when you upgrade anytrellis. While anytrellis is 0.x, a
minor version (0.1 to 0.2) may change the API; each change is listed here with the code
before and after.

## 0.2.0

One change in what a plot shows; no code stops working.

**A wrap of more than 100 panels pages.** It shows 6 by 4 panels at a time, with a bar to
turn the pages, sort and filter them ([Page through many panels](../how-to/pages.md)).
To draw every panel at once, as 0.1 did:

```python
# 0.1: all 300 panels in one grid
Trellis(df, wrap="station")

# 0.2: the same
Trellis(df, wrap="station", rows="all")
```

Everything else in 0.2 is new: images from the toolbar and from Python (`save_png`,
`save_svg`), violins, error bars, step lines and pages of panels. See the
[changelog](changelog.md).

## 0.1.0

The first release: nothing to change.
