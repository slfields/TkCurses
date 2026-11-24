# Acceptance: XY charts

`XYChart` is a widget only TkCurses has, a line and area chart after
Kibana's, drawn on the Canvas. What it should look like is what
[ARCHITECTURE.md](../ARCHITECTURE.md#xychart) designs. The automated tests
check which item lands on which pixel, that nothing is drawn off the plot,
and which colour each cell takes. They cannot tell whether a line reads as
a line in your font, whether a dimmed fill is told apart from its line on
your terminal, or whether a stack makes sense to look at. This checklist
is for those.

There are two passes over the same scenario. **Pass 1**, run as soon as
lines drew, checks the series: lines and areas, stacking, joining, gaps,
scales, bounds, the live feed and size. **Pass 2** checks what came
after it: the axes and their titles, gridlines, reference lines, units,
the legend and its statistics, and the crosshair and readout, with the
keys and the mouse. The sections are marked with their pass; pass 1's
are unchanged but for the names on the status lines, and still hold.

**How to run**, from the repository root:

```bash
python3 -m uat 53                     # your terminal as it is
TERM=xterm python3 -m uat 53          # eight colours
TERM=vt100 python3 -m uat 53          # no colour
```

Escape ends it, once there is no crosshair and no legend entry
underlined: until then, Escape is the chart's, and takes those away.
Use a terminal at least 80×24. Lines 1 to 4 of the screen list the
keys. Line 5 says which colours TkCurses found, the data set, whether
the second series is hidden, live, the note and the size; lines 6 and 7
the series options in force; line 8 the legend, statistics, units,
references and readout, and where the crosshair is with **how many
`<<XYChartCursor>>` events the program has had**.

The data is three series, never random, so two runs draw the same. In
`lines` and `times`: **cpu** green, a fast wave; **load** red, a slower
one with values missing; **disk** blue, a slow rise below the other
two. In `areas`: **web** green, **db** red with values missing, **cache**
blue. `load` and `db` miss their first two values, one alone, four
together, and their last. `times` is `lines` read once a minute from
23:30, with **no readings for 15 minutes** after 23:57.

| | |
|---|---|
| Terminal and font | |
| Size | |
| Colours (`tput colors`, and whether `COLORTERM` says truecolor) | |
| Date / version | |

---

## The one that matters most

After each run, **the terminal still works**: prompt back, cursor
visible, typing echoed.

## 53. Lines (pass 1)

`python3 -m uat 53`.

- [ ] Three lines, green, red and blue, across the whole area. Each is
      **unbroken where it has values**: no pixel missing where it turns,
      climbs or falls steeply
- [ ] A steep stretch of the green line reads as one line, not as a
      scatter of separate cells
- [ ] Where two lines cross, **both are still followed by eye**. A pixel
      holds one colour, so the line drawn later (blue over red over
      green) takes the pixels they share, and the other picks up on the
      far side. That is the only place a line should look broken, apart
      from the red line's gaps
- [ ] The red line's **missing values** show as gaps, and nothing is
      drawn across them: it starts a little in from the left edge (its
      first two values), breaks for **one column** just over a quarter of
      the way along (one value), breaks for **about five columns** past the
      middle (four values), and stops one step short of the right edge
      (its last). Any other break in it is a fault: say where
- [ ] **Resize** the terminal narrower and wider. The chart draws again
      to fill it, and nothing is left behind where a line was

## 53. Times (pass 1)

**n** twice: `data=times`.

- [ ] The same three series, but **not the same picture**: x is spaced by
      the clock, not by the count. From about a third of the way along to
      just past the middle, every line runs **straight across**:
      the 15 minutes with no readings, joined from the last reading
      before to the first after
- [ ] Either side of it the waves are **squeezed** to fit, since the same
      60 readings now share less width
- [ ] The x axis is labelled in clock times: see Axes, in pass 2

## 53. Areas and stacking (pass 1)

**n** once: `data=areas`.

- [ ] Three areas stacked: **web** at the bottom from zero, **db** on it,
      **cache** on top. Each is **filled in a dimmer shade** of its
      line's colour, and **its line runs along its top**, bright
- [ ] **No fill hides a line**: every bright line is whole, even where it
      runs through another series' fill
- [ ] Where db has a value missing, there is a **notch of background**
      between web and cache: db is not drawn there, and cache rests on
      web. That is `missing=hide` showing the gap; write down if it reads
      as a fault instead
- [ ] **s**: `stack=percentage`. The three now **fill the height**:
      cache's top line runs along the top row, and each band is its share
      of the three at that point
- [ ] **s**: `stack=unstacked`. Each area is **filled from zero**,
      drawn over the one before it; cache, last, covers the bottom.
      Every line is still on top
- [ ] **s** once more comes back to `stacked`

## 53. Joining points (pass 1)

On `data=lines` (press **n** until it says so).

- [ ] **i**: `interp=smooth`. The lines become **curves**. At each
      peak and trough a curve **does not overshoot**: it rises no higher
      than the highest point near it, and falls no lower than the lowest
- [ ] **i**: `interp=step`. Each value is **held flat until the
      next x**, then jumps: horizontal runs joined by vertical ones
- [ ] **p**: `points=show`. A **lighter dot** marks each value given, on
      every line. **p**: `points=hide`, no dots. **p** once more:
      `points=auto`, no dots here, since 60 points to a line are too
      close together for them to help

## 53. Missing values (pass 1)

On `data=lines`, `interp=straight`.

- [ ] **m**: `missing=zero`. The red line **drops to zero** across each
      gap in the middle and comes back up. Its first two values and its
      last are still not drawn
- [ ] **m**: `linear`, the gaps are **bridged by a straight line**
      between the values either side. **m**: `last`, each gap **holds the
      value before it** flat. **m**: `next`, it **takes the value after
      it**. **m**: back to `hide`
- [ ] With `missing=linear`, **e**: `ends=zero` draws the start and
      end from zero; **e**: `nearest` holds the first and last values
      out to the edges. **e**: back to `hide`
- [ ] With `missing=linear`, **d**: `dotted=1`. Every stretch
      `missing` filled in is **dotted**, two pixels on and two off; the
      real values stay solid. You can tell at a glance which parts are
      data and which are filled in

## 53. Scales and bounds (pass 1)

On `data=lines`, all the above back to their defaults.

- [ ] **c**: `scale=log`. The lines are **squeezed toward the top**:
      a log axis gives each tenfold the same height, so values between
      20 and 80 take a band of the height. The blue line, from about 4,
      climbs steeply at first. **c**: `sqrt`, between the two
- [ ] **c** back to `linear`. **b**: `bounds=data`. **Nothing moves**:
      the values run from 4 to 80, and rounded out to round numbers that
      is 0 to 80, the same as `full`
- [ ] **b**: `bounds=custom`, from 20 to 60. Lines **leave through the
      top and bottom edges and come back**, cut where they cross; none is
      drawn squashed against an edge. Blue, below 20 nearly all the way,
      is gone but for the last sixth of the width
- [ ] **b** twice, back to `data`, then **f**: `nice=0`. The axis is
      4 to 80, and the lowest and highest values touch the **very bottom
      and top rows**: the blue line starts on the bottom row. **f** again
      puts the rounding back
- [ ] On `data=areas`, **b** `data` does nothing: an area is drawn from
      zero whatever the bounds, as in Kibana

## 53. Live data and the program's own items (pass 1)

- [ ] **l**: `live=on`. Every 200 ms each series moves **one point to the
      left**, a new value coming in at the right, and the gaps in red move
      with it. The motion is **steady**: no flicker, no frame where the
      chart is blank or half drawn
- [ ] **n** to `times` with the feed on, and on to `lines`: the feed goes
      on, **with no error**. **l** stops it
- [ ] **x**: `note=on`. "a note of the program's own" is written over
      the chart near its top left. It stays **on top of every series**,
      with the live feed running and after **s**, **i** and **n** change
      what is drawn under it. **x** again removes it, leaving nothing
      behind

## 53. Hiding a series (pass 1)

- [ ] **h** hides the second series (`load hidden`, or `db hidden` on
      areas). It **vanishes**; on areas, cache **drops onto web**
- [ ] **h** again brings it back, in its place in the stack and its own
      colour

## 53. Without colour (pass 1)

- [ ] `TERM=xterm python3 -m uat 53` (line 3 says `colours 8`). Lines
      are green, red and blue. On areas, each is filled in **its line's
      own colour**, so a line is seen only where it is the top of its
      area. The stack still reads as three bands
- [ ] `TERM=vt100 python3 -m uat 53` (`colours none`). The lines are all
      one ink and **look alike**, as agreed for this chart. On areas the
      fill is solid and a line inside it shows as **dark notches**. Write
      down whether you can still follow a line; this is the one place a
      chart may simply be the wrong tool

## 53. Size (pass 1)

- [ ] **z** (`size: 50% x 50%`): the chart is **half the screen wide and
      half as tall**, at the top left of the area
- [ ] **Resize** the terminal wider and taller. It stays **half** of the
      new size
- [ ] **z** (`60 x 50%`): **60 columns** whatever the terminal's width,
      half its height. Resizing changes only the height
- [ ] **z** (`width 30`): 30 columns, and **every row the area has**,
      14 at 80×24: a chart asks for 16 when no height is given, and
      gets what is there
- [ ] **z** once more fills the area again

---

# Pass 2

Start each section from a fresh `python3 -m uat 53` unless it says
otherwise.

## 53. Axes (pass 2)

- [ ] Down the left, **values**: `0`, `20`, `40`, `60`, `80`, each on a
      `┤` tick of the axis line `│`, with **a blank row between any
      two**. Along the bottom, `└` then `─` with a `┬` under each
      **number**, written centred under its tick
- [ ] **No label touches another**, nor runs into the plot or off the
      edge, at any size: resize the terminal narrower and shorter. As
      it shrinks, labels are **dropped, not squeezed**, and at the
      smallest the axes go and the lines fill what is left
- [ ] **a**: `titles=1`. `value` above the values, at the top left, and
      `reading` centred under the numbers. **a** takes them away
- [ ] **g**: `grid=1`. **Dotted** lines `┈` and `┊` run from each tick
      across and up the plot, dimmer than the series and **under** them:
      no line is broken where a gridline crosses it. **g** again
- [ ] **t**: `ticks=0`. The numbers go and the ticks stay; the plot
      **widens** into the room they left. **t** again
- [ ] **n** twice, `data=times`. Along the bottom, **clock times**:
      `23:30`, `23:40`, … and, where the day turns, `Nov 24` in place of
      `00:00`. Under them at the left, **`Nov 23, 2026`**: the date the
      times are on. The 15 minutes without readings take **their share
      of the width**, so the ticks are evenly spaced in time, not in
      readings

## 53. Units (pass 2)

- [ ] **u**: `units=%`. Every value label is `80%`, `60%`, …
- [ ] **u**: `units=$`. Written **before** the number: `$80`. **k**
      (statistics) and the crosshair (**End**) show `$` too, in the
      legend and the readout
- [ ] **u** back to `-`

## 53. Reference lines (pass 2)

- [ ] **r**: `refs=on`. Three things appear:
      - an **alert** line across at 70, red, `alert` at its right end;
      - a **normal** band from 40 to 50, a **dimmed green** fill with
        its line at 45 and `normal` at its right end;
      - a **deploy** line down the chart at the 45th reading, white,
        `deploy` at its top.
- [ ] The band is **under** the series, and every series line is whole
      through it. The two lines across and the one down are **over**
      the series
- [ ] **n** to `areas` and to `times`: the references stay, and on times
      **deploy** is still at the 45th reading, now a time. **r** again
      removes all three and leaves nothing behind

## 53. Legend (pass 2)

- [ ] At the right, a column ruled off with `│`: **`██ cpu`** in green,
      **`██ load`** red, **`██ disk`** blue, names in **bold**. On areas,
      `web`, `db`, `cache`
- [ ] **k**: `stats=2`. Under each name, `avg 50 · max 80`, to three
      significant figures. **k**: `stats=5`: last, min, max, avg and
      diff. The legend is **at most a third of the chart**, so these are
      cut with `…`; **load**'s `last` is `–`, its last value being
      missing. **k** back to 0
- [ ] **j** steps the legend's side: `bottom`, ruled off with `─` and
      the entries across; `left`; `top`; then `hide`, and the chart
      **takes the room back**. **j** again: `right`
- [ ] With one series hidden (**h**), its entry stays: a **hollow**
      swatch `░░` and a dim name, not bold

## 53. Hiding from the legend (pass 2)

This is the fault found in pass 2's first run, now fixed: check it
stays fixed.

- [ ] **Click** `cpu`'s entry: its line goes, the swatch goes hollow.
      Click `load`, then `disk`: **all three hidden**. The plot is empty,
      and **the legend is still there**, three hollow entries
- [ ] **Click** `load` again: it comes back, in red, with its axes
- [ ] Click two entries **quickly one after the other**: **both**
      change, the second click not lost as a double click
- [ ] With the keyboard: **Down** underlines `cpu`'s name, **Down**
      again `load`'s, **Up** back. **Space** hides and shows the one
      underlined. **Escape** takes the underline away, and only a
      second Escape quits

## 53. Crosshair and readout (pass 2)

- [ ] The bottom row reads **`0 – 59`**: the range of x, with no
      crosshair
- [ ] **Left**: a **dim line down the chart at the last x**, a
      **lighter mark** where each series meets it, and the bottom row
      reads `59  cpu 40.7  load –  disk 22.8`, each value **in its
      series' colour**. Line 8: `cursor=59 (1 sent)`
- [ ] **Left** again moves it **one x left**, and `sent` counts up by
      one each time. **Right**, **Home** and **End** do as they say. At
      either end, a key that cannot move it sends nothing
- [ ] **Click** on the plot: the crosshair goes to the x **nearest the
      mouse**
- [ ] **l**, live, with the crosshair on: it **stays at its x** as
      the points move under it, until that x leaves the chart, when it
      moves to the **nearest x on its left**, or to the first x if
      there is none left of it. **l** stops it
- [ ] **n** to `times`, **End**: the readout begins `Nov 24 00:44`
- [ ] **Escape** takes the crosshair away (`cursor=-`), and the program
      is **still running**. Escape again quits
- [ ] **o**: `readout=0`. The bottom row goes to the chart; **o** brings
      it back

## 53. Without colour (pass 2)

- [ ] `TERM=xterm python3 -m uat 53`: the legend's swatches are the
      series' colours. **r**: the band is **solid green**, there being
      no dimmer shade to give it: the red and blue lines show across
      it, and **the green line does not**, as an area's own line does
      not show through its fill at 8 colours. Write down whether the
      band is still worth having there. **g**: gridlines in the ordinary
      ink
- [ ] `TERM=vt100 python3 -m uat 53`: the swatches are all `██`, and a
      hidden series' `░░` is **still told apart** from a shown one's.
      The readout is one ink: the series are told apart **by name**
- [ ] Under `TERM=vt100` **the mouse does nothing**: a VT100 had none,
      its terminfo entry has no mouse capability, and so ncurses never
      asks the terminal to report clicks. That is expected, for every
      widget. Do the legend with the keys instead: **Down** and **Up**
      underline an entry, **Space** hides and shows it, and the
      crosshair is all keys anyway

## 53. Size (pass 2)

- [ ] **z** (`50% x 50%`): 40 by 12. The axes, the legend and the
      readout all **fit or go**: nothing is cut in half, and nothing
      overlaps
- [ ] **z** (`width 30`) with **k** `stats=2`: the legend takes **a
      third of the width**, its figures cut short with `…` (`avg 5…`),
      and the chart keeps its axes, with fewer labels along the bottom.
      Write down whether a legend that narrow helps or is better hidden
