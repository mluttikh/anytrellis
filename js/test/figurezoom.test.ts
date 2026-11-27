import { describe, expect, it } from "vitest";
import { type Span, ZoomMember, sameSpan } from "../src/core/figurezoom";

describe("plots that share a range zoom together", () => {
  it("tells the others news only, and a view that joins later starts where they are", () => {
    const seen: Span[] = [];
    const a = new ZoomMember("fig-x0|0|10", () => {});
    const b = new ZoomMember("fig-x0|0|10", (at) => seen.push(at));
    a.tell([0, 10]);
    a.tell([2, 5]);
    a.tell([2, 5 + 1e-12]); // the same, but for rounding
    expect(seen).toEqual([[0, 10], [2, 5]]);
    const c = new ZoomMember("fig-x0|0|10", () => {});
    expect(c.at).toEqual([2, 5]);
    const other = new ZoomMember("fig-x0|0|20", () => {}); // a range Python changed: a new start
    expect(other.at).toBeNull();
    for (const m of [a, b, c, other]) m.leave();
    expect(new ZoomMember("fig-x0|0|10", () => {}).at).toBeNull(); // all left: it starts again
  });

  it("compares ranges to their size", () => {
    expect(sameSpan([0, 1], [1e-12, 1])).toBe(true);
    expect(sameSpan([0, 1], [0.001, 1])).toBe(false);
    // a second of times in ms since 1970: their last digits, not a millisecond
    const t = 1.7e12;
    expect(sameSpan([t, t + 1000], [t + 2.5e-4, t + 1000])).toBe(true);
    expect(sameSpan([t, t + 1000], [t + 1, t + 1000])).toBe(false);
  });
});
