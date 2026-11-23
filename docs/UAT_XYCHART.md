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
scales, bounds, the live feed and size. The chart has **no axes yet**:
they, the legend and the crosshair come later, and **Pass 2** checks them.

**How to run**, from the repository root:

```bash
python3 -m uat 53                     # your terminal as it is
TERM=xterm python3 -m uat 53          # eight colours
TERM=vt100 python3 -m uat 53          # no colour
```

Escape ends it. Use a terminal at least 80×24. Line 3 of the screen says
which colours TkCurses found, the data set and what is hidden, live or
drawn; lines 4 to 6 the options in force and the size.

The data is three series, never random, so two runs draw the same. In
`lines` and `times`: **cpu** green, a fast wave; **load** red, a slower
one with values missing; **disk** blue, a slow rise. In `areas`: **web**
green, **db** red with values missing, **cache** blue. `load` and `db`
miss their first two values, one alone, four together, and their last.

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

## 53. Lines

`python3 -m uat 53`.

- [ ] Three lines, green, red and blue, across the whole area. Each is
      **unbroken where it has values**: no pixel missing where it turns,
      climbs or falls steeply
- [ ] A steep stretch of the green line reads as one line, not as a
      scatter of separate cells
- [ ] Where two lines cross, **both are still followed by eye**: the one
      drawn later (blue over red over green) wins the shared cell, and
      the other picks up on the far side
- [ ] The red line has **gaps**: none at its very start, one short, one
      longer in the middle, and none at its very end. Nothing is drawn
      across them
- [ ] **Resize** the terminal narrower and wider. The chart draws again
      to fill it, and nothing is left behind where a line was

## 53. Areas and stacking

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
- [ ] **s**: `stackmode=percentage`. The three now **fill the height**:
      cache's top line runs along the top row, and each band is its share
      of the three at that point
- [ ] **s**: `stackmode=unstacked`. Each area is **filled from zero**,
      drawn over the one before it; cache, last, covers the bottom.
      Every line is still on top
- [ ] **s** once more comes back to `stacked`

## 53. Joining points

On `data=lines` (press **n** until it says so).

- [ ] **i**: `interpolation=smooth`. The lines become **curves**. At each
      peak and trough a curve **does not overshoot**: it rises no higher
      than the highest point near it, and falls no lower than the lowest
- [ ] **i**: `interpolation=step`. Each value is **held flat until the
      next x**, then jumps: horizontal runs joined by vertical ones
- [ ] **p**: `points=show`. A **lighter dot** marks each value given, on
      every line. **p**: `points=hide`, no dots. **p** once more:
      `points=auto`, no dots here, since 60 points to a line are too
      close together for them to help

## 53. Missing values

On `data=lines`, `interpolation=straight`.

- [ ] **m**: `missing=zero`. The red line **drops to zero** across each
      gap in the middle and comes back up. Its first two values and its
      last are still not drawn
- [ ] **m**: `linear`, the gaps are **bridged by a straight line**
      between the values either side. **m**: `last`, each gap **holds the
      value before it** flat. **m**: `next`, it **takes the value after
      it**. **m**: back to `hide`
- [ ] With `missing=linear`, **e**: `endvalues=zero` draws the start and
      end from zero; **e**: `nearest` holds the first and last values
      out to the edges. **e**: back to `hide`
- [ ] With `missing=linear`, **d**: `dottedgaps=1`. Every stretch
      `missing` filled in is **dotted**, two pixels on and two off; the
      real values stay solid. You can tell at a glance which parts are
      data and which are filled in

## 53. Scales and bounds

On `data=lines`, all the above back to their defaults.

- [ ] **c**: `scaletype=log`. The lines are **squeezed toward the top**:
      a log axis gives each tenfold the same height, so values between
      20 and 80 take a band of the height. The blue line, from about 8,
      climbs steeply at first. **c**: `sqrt`, between the two
- [ ] **c** back to `linear`. **b**: `bounds=data`. **Nothing moves**:
      the values run from 8 to 80, and rounded out to round numbers that
      is 0 to 80, the same as `full`
- [ ] **b**: `bounds=custom`, from 20 to 60. Lines **leave through the
      top and bottom edges and come back**, cut where they cross; none is
      drawn squashed against an edge
- [ ] **b** twice, back to `data`, then **f**: `nicebounds=0`. The axis is
      8 to 80, and the lowest and highest values touch the **very bottom
      and top rows**: the blue line starts on the bottom row. **f** again
      puts the rounding back
- [ ] On `data=areas`, **b** `data` does nothing: an area is drawn from
      zero whatever the bounds, as in Kibana

## 53. Live data and the program's own items

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

## 53. Hiding a series

- [ ] **h** hides the second series (`load hidden`, or `db hidden` on
      areas). It **vanishes**; on areas, cache **drops onto web**
- [ ] **h** again brings it back, in its place in the stack and its own
      colour

## 53. Without colour

- [ ] `TERM=xterm python3 -m uat 53` (line 3 says `colours 8`). Lines
      are green, red and blue. On areas, each is filled in **its line's
      own colour**, so a line is seen only where it is the top of its
      area. The stack still reads as three bands
- [ ] `TERM=vt100 python3 -m uat 53` (`colours none`). The lines are all
      one ink and **look alike**, as agreed for this chart. On areas the
      fill is solid and a line inside it shows as **dark notches**. Write
      down whether you can still follow a line; this is the one place a
      chart may simply be the wrong tool

## 53. Size

- [ ] **z** (`size: 50% x 50%`): the chart is **half the screen wide and
      half as tall**, at the top left of the area
- [ ] **Resize** the terminal wider and taller. It stays **half** of the
      new size
- [ ] **z** (`60 x 50%`): **60 columns** whatever the terminal's width,
      half its height. Resizing changes only the height
- [ ] **z** (`width 30`): 30 columns and **16 rows**, the height a chart
      asks for when none is given
- [ ] **z** once more fills the area again
