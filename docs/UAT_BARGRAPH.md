# Acceptance: bar graphs

`BarGraph` is a widget only TkCurses has, so there is no Tk to compare it
with: what it should look like is what [its reference](reference/exclusive/bargraph.md)
says and what the [examples](guide/bargraph.md) draw. The automated tests
check which characters land in which cells. They cannot tell whether an
eighth-block glyph *looks* like an eighth in your font, whether the
thresholds' colours are told apart on your terminal, or whether a wide
label sits where it should. This checklist is for those.

**How to run**, from the repository root:

```bash
python3 -m uat 51
python3 examples/bars.py
python3 examples/meters.py
python3 examples/scales.py
```

Escape ends the scenario; Ctrl-C ends an example. Use a terminal at least
80×24.

| | |
|---|---|
| Terminal | |
| Size | |
| Colours (`tput colors`, and whether `COLORTERM` says truecolor) | |
| Date / version | |

---

## The one that matters most

After the scenario and each example ends, **the terminal still works**:
prompt back, cursor visible, typing echoed.

## 51. Eighths of a cell

`python3 -m uat 51`

- [ ] The left graph, **Steps**, shows one full cell and a partial one
      above it, and the readout says `13 of 64 = 1 cell and 5/8`
- [ ] Press **Up** a few times. Each press raises the bar's tip by **one
      eighth of a cell** - a small, even step, never a jump of a whole
      cell and never no change at all - and the readout follows. At
      `16 of 64` the top is a whole cell again
- [ ] The steps look even in **your font**: a font whose block glyphs are
      not drawn to the cell's full height shows gaps or uneven steps here,
      which is the font, but worth writing down
- [ ] Hold **Up** to 48 and past it: the part of the bar **above 48** turns
      yellow, the rest stays green. Past 56 the part above 56 is red. The
      tip shows red however small the red part is
- [ ] **Down** brings it back, and the colours go with it

## 51. Series and labels

- [ ] The middle graph, **Series**, has three bars of three colours each,
      stacked: green at the bottom, yellow, then cyan
- [ ] Where two colours meet inside one cell there is **no third colour**
      and no gap; the bar's top is where it should be
- [ ] Press **m**: the readout says `overlay`, and each bar becomes as tall
      as its largest value, with the smaller ones drawn in front from the
      bottom. **m** again goes back
- [ ] The labels `東京`, `Café` and `plain` sit **centred** under their
      bars. `東京` takes four columns; `Café` is written with a combining
      accent and must look like four letters, not five, centred as four
- [ ] **Resize** the terminal narrower and wider. The middle graph grows
      and shrinks with it, its bars stay evenly shared, and nothing is left
      behind where a bar was

## 51. Shades

- [ ] The right graph, **Shades**, lies on its side with readouts `30%`,
      `65%`, `100%` at the right
- [ ] Press **g**. On a truecolor terminal each bar now darkens towards its
      start - smoothly, from a dark shade at the left to its full colour
      only where it reaches 100%. At 256 colours the same in **bands**. With
      8 or 16 colours **nothing changes**, which is right: there are no
      shades to draw with

## Examples

- [ ] `examples/bars.py`: **o** turns the graph on its side and back, **m**
      switches stacked and overlay; the status line stays on the screen
- [ ] `examples/meters.py`: the four cores' bars move smoothly and their
      readouts change **in place** - never two numbers on one line, never a
      stray digit left from a wider one. A core above 70% shows yellow,
      above 90% red, and a thin mark stays where each peaked for about two
      seconds
- [ ] In the same program, about every ten seconds the requests burst:
      the axis grows to `400/s` **at once**, without the bars first
      overflowing the top, then a few seconds after the burst comes back
      down in steps to `40/s`
- [ ] `examples/scales.py`: the log axis reads `1ms`, `100ms`, `10s`,
      evenly spaced to within a row, with a red line at half a second; the
      disks read `210 GiB`, `440 GiB`, `500 GiB`, `/home` with a yellow end
      and `/var` with yellow and red; the budget axis is in dollars; the
      temperatures shade from blue to red
