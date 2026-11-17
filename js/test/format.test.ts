// Formats (format.ts): numbers as d3-format writes them, times as d3's utcFormat, checked on
// the outputs of d3 itself (d3-formats.json, which formats.py is checked on too); and ticks
// and tooltips labelled by an axis's format.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { axisFormat, numberFormat, timeFormat } from "../src/core/format";
import { formatValue, ticks } from "../src/core/ticks";

const D3 = JSON.parse(readFileSync(join(__dirname, "d3-formats.json"), "utf8")) as {
  numbers: [string, number | "-0", string][];
  times: [string, number, string][];
};

describe("formats", () => {
  it("write numbers as d3-format does", () => {
    const wrong = D3.numbers.filter(([spec, v, want]) => numberFormat(spec)(v === "-0" ? -0 : v) !== want);
    expect(wrong.slice(0, 5)).toEqual([]);
    expect(D3.numbers.length).toBeGreaterThan(1000);
  });

  it("write times as d3's utcFormat does", () => {
    const wrong = D3.times.filter(([spec, t, want]) => timeFormat(spec)(t) !== want);
    expect(wrong).toEqual([]);
  });

  it("refuse what they can't read", () => {
    expect(() => numberFormat(".2q")).toThrow(/invalid number format/);
    expect(() => timeFormat("%Q")).toThrow(/invalid time format/);
    expect(axisFormat("band", ".1f")).toBeNull();
    expect(axisFormat("number", null)).toBeNull();
  });

  it("label ticks and tooltips", () => {
    expect(ticks("number", 0, 3000, 0, 3, null, "$,.0f").map((t) => t.label)).toEqual(["$0", "$1,000", "$2,000", "$3,000"]);
    // a log axis: the values, not their logs
    expect(ticks("log", 0, 2, 0, 3, null, ".0f").map((t) => t.label)).toEqual(["1", "10", "100"]);
    const day = 86_400_000;
    expect(ticks("time", 0, 2 * day, Date.UTC(2026, 2, 1), 3, null, "%-d %b").map((t) => t.label)).toContain("2 Mar");
    expect(formatValue("number", 0.1234, 0, 1, null, ".1%")).toBe("12.3%");
    expect(formatValue("number", 0.1234, 0, 1)).toBe("0.123");
  });
});
