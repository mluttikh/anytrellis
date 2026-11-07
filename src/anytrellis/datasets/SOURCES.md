# Sources of the bundled datasets

The datasets in this folder (`anytrellis.datasets.load`) are not covered by anytrellis's MIT
licence: each keeps the terms of its source.

| dataset | source | licence |
|---|---|---|
| anscombe | F. J. Anscombe (1973), *Graphs in Statistical Analysis*, The American Statistician 27(1):17-21; as in [vega-datasets](https://github.com/vega/vega-datasets) 2.8.0 | published numbers, also in R's `datasets` package; no licence stated |
| barley | Minnesota Agricultural Experiment Station; Immer, Hayes and Powers (1934); republished in Wiebe et al. (1940), *Yields of Barley Varieties in the United States and Canada, 1932-36*, USDA Technical Bulletin 735; as in vega-datasets 2.8.0 | a U.S. Government publication; also in R's `lattice` package |
| cars | Quinlan, R. (1993). *Auto MPG* [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5859H> | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| gapminder | Gapminder Foundation: life expectancy, population and fertility, 1955-2005; as in vega-datasets 2.8.0 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): based on free material from [GAPMINDER.ORG](https://www.gapminder.org/), CC-BY LICENSE |
| penguins | Gorman, Williams and Fraser (2014), Palmer Station Antarctica LTER; [palmerpenguins](https://github.com/allisonhorst/palmerpenguins) by Horst, Hill and Gorman; as in vega-datasets 2.8.0 | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| seattle_weather | NOAA National Climatic Data Center, daily records for Seattle, 2012-2015; as in vega-datasets 2.8.0 | a U.S. Government work: public domain |

Changes made here: column names in snake_case; for `gapminder`, readable region names; for
`cars`, the 406 cars of UCI's `auto-mpg.data-original`, with the model year as 1970-1982,
the origin as USA, Europe or Japan, and missing values left empty.
