# Shortcuts and df.plot

`at.line`, `at.points`, `at.bars`, `at.area`, `at.hist`, `at.density`, `at.box`,
`at.violin`, `at.ecdf` and `at.hexbin` each make a plot and its mark in one call:
`at.line(data, **arguments)` is `Trellis(data, ...).line(...)`, each argument going to
`Trellis()` ([its arguments](trellis.md)) or to the mark by its name. See [Make a plot in
one call](../how-to/one-call.md).

::: anytrellis.shortcuts.plot

::: anytrellis.shortcuts.Accessor
    options:
      members: false
