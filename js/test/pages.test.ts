import { describe, expect, it } from "vitest";
import { pageLabels, pageList, pinsOf } from "../src/core/pages";
import type { PagesSpec } from "../src/core/types";

const pages = (rows: number, cols: number, extra: Partial<PagesSpec> = {}): PagesSpec => ({ rows, cols, stats: [], ...extra });

describe("pinned panels", () => {
  it("lead every page, in the order pinned, as pages.py does", () => {
    const ten = [...Array(10).keys()];
    expect(pageList(ten, pages(2, 2), [7, 2])).toEqual([[7, 2, 0, 1], [7, 2, 3, 4], [7, 2, 5, 6], [7, 2, 8, 9]]);
    expect(pageList([], pages(2, 2), [3])).toEqual([[3]]);
    expect(pinsOf([1, 2, 3, 4, 1], 4)).toEqual([1, 2, 3]);
  });

  it("go on each page of every level; a level's name from its own panels", () => {
    const spec = pages(1, 3, { groups: [0, 0, 0, 1, 1, 1], levels: ["a", "b"] });
    const list = pageList([0, 1, 2, 3, 4, 5], spec, [4]);
    expect(list).toEqual([[4, 0, 1], [4, 2], [4, 3, 5]]);
    expect(pageLabels(list, spec)).toEqual(["a (1 of 2)", "a (2 of 2)", "b"]);
  });

  it("are not moved on a grid's pages", () => {
    expect(pageList([0, 1, 2, 3], pages(1, 2, { grid: true }), [3])).toEqual([[0, 1], [2, 3]]);
  });
});
