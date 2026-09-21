# UAT: Images

Scenario 35. Run it with:

```bash
python3 -m uat 35
# or
python3 -m uat.scenario_35_images
```

The claim under test is one sentence: **a pixel is one cell wide and half a
cell tall**, and it is the same pixel a Canvas draws on. There is one pixel
plane in this library and an image is on it — so `width()` and `height()`
answer in pixels, an image 8 by 6 occupies 8 cells across and 3 rows down,
and `▀`, `▄` and `█` are what reaches the screen, through the same
`compose()` a Canvas uses.

The first version of this got it wrong, with a pixel being a whole cell and
an image being a grid of glyphs. Check 35.0 is the one that would have
caught it.

Three behaviours are reproduced from Tk rather than improved on, because
tkinter code is written around them. Each was measured on Tk 9.0.2 and each
has a check below: the `compound=none` default, a widget following its image,
and an image that nothing references going away.

---

## 35.0 The circle is round

This is the check the whole design rests on. If a pixel were a whole cell,
a circle drawn as wide as it is tall would appear as an ellipse half its
proper height, because a character cell is about twice as tall as it is
wide. Half-cells are very nearly square, so it comes out round.

**Do:** look at the `round:` circle on the right.

**Look for:**

- [ ] It is **round** — as tall as it is wide, to the eye.
- [ ] It is 12 cells across and occupies **6 rows**, because it is 12 pixels
      by 12.
- [ ] Its left half is cyan and its right magenta, and the two colours meet
      cleanly down the middle.
- [ ] Its edges use `▀` and `▄`, not just `█`. That is a half-lit cell, and
      it is the only reason the curve looks smooth.

## 35.1 An image is drawn where the widget is

**Do:** start the scenario.

**Look for:**

- [ ] The `Label:` row shows a small house.
- [ ] `Bitmap:` shows an arrow **pointing right**. This is real XBM data,
      parsed a bit per pixel, not a picture of an arrow typed out. (It
      pointed left until someone ran this: XBM is least-significant-bit
      first, and the bytes had been written as though it were the other way
      round.)
- [ ] `Button:` shows the house inside a button's border.
- [ ] `Check:` shows `[x]`, the house, then `on`.
- [ ] The status line reads `image=6x4px = 6x2 cells`, and `Label asks 6x2`.
      **The two heights differ by exactly half**, and that is the point: the
      image is measured in pixels and the widget lays out in cells.

## 35.2 `compound=none` hides the text — the surprising default

Measured on Tk with `text='hello'` and an 8x4 image: the widget asks for
10x6, the image plus its border. The text contributes **nothing**.

**Do:** look at the `with text:` row before pressing anything, then press `c`
once.

**Look for:**

- [ ] Before: the house, and **no** `Home` anywhere. The label has text and
      is not drawing it.
- [ ] After one `c`: `compound=left`, and `Home` appears to the right of the
      house with one blank cell between them.
- [ ] The status line's `caption asks` grows by the width of `Home` plus that
      one cell.

## 35.3 The rest of the compounds

**Do:** keep pressing `c`. It cycles none → left → right → top → bottom →
center → none.

**Look for:**

- [ ] `right`: `Home` first, then the house.
- [ ] `top`: the house above, `Home` below it.
- [ ] `bottom`: `Home` above, the house below.
- [ ] `center`: `Home` drawn over the house — the block is the larger of the
      two in each direction, not the sum.
- [ ] Back at `none`, `Home` disappears again.
- [ ] The `Checkbutton:` never changes. It is fixed at `left` on purpose, so
      there is something still to compare the others against.

## 35.4 A widget follows its image

Measured on Tk: resizing an image from 4x2 to 20x10 moved a live Label's
request from 6x4 to 22x12 **with nothing asked of the label**.

**Do:** press `p`, then `s`, then `s` again.

**Look for:**

- [ ] `p` paints the image's top half magenta, in **every** widget showing
      it at once — the label, the captioned label, the button and the
      checkbutton. Nothing was asked of any of them; the write went to the
      image.
- [ ] `s` redraws the house at double scale — 12x8 pixels, so 12 cells wide
      and 4 rows — and every one of those widgets grows with it. It is still
      recognisably **the same house**, just bigger. The status line's
      `image=` and `Label asks` move together, still halving.
- [ ] **The rows below each grown widget move down to make room.** The
      captions, the button and the `z / x:` row all shift; nothing is drawn
      over anything else.
- [ ] `s` again returns it to 6x4 and everything moves back up.

### Why things move, and when they do not

Worth being explicit, because it is a fair thing to wonder about: the
widgets here are laid out with **`grid`**, and `grid` reflows — a widget
whose requested size changes pushes its neighbours along. That is what makes
this check visible at all.

Had they been laid out with **`place`**, nothing would have moved. `place`
is absolute positioning in Tk and here: a placed widget stays exactly where
it was put, and a grown neighbour is simply drawn over it. That is not a
bug in images, it is what `place` means — and an earlier version of this
scenario used it, which is why pressing `s` used to paint the house straight
through the button's border and across the circle.

## 35.5 A hole is not a space

**Do:** press `s`, then `h`.

**Look for:**

- [ ] A diagonal of gaps appears through the image. Press `s` first, so
      there is a solid house worth punching through.
- [ ] Those cells show the **label's** background, not something the image
      painted. The image declined to write there rather than writing a
      space — which is what transparency is when there is no alpha channel.
- [ ] Where only one of a cell's two pixels is a hole, the cell becomes `▀`
      or `▄` rather than disappearing. Half a cell can be transparent.

## 35.6 zoom and subsample

ARCHITECTURE.md used to mark both N/A. They are the two operations that
survive the move to this plane most cleanly: repeating a pixel is exactly
what enlarging means when the plane is this coarse.

**Do:** press `z`, then `x`, watching the `z / x:` slot.

**Look for:**

- [ ] `z` doubles the image in both directions — every pixel becomes a 2x2
      block of pixels, so the image grows to twice the width and twice the
      rows.
- [ ] `x` halves it, keeping every second pixel, and the house becomes a
      few cells of suggestion. That is what throwing away three quarters of
      a small image looks like.
- [ ] Only the `z / x:` widget changes. `zoom()` and `subsample()` return new
      images; they do not alter the one they were called on. (Both work from
      the house at its **original** scale, so `s` does not change what they
      produce — zooming an already-doubled house is 24 cells wide and just
      runs out of terminal.)

## 35.7 The trap

**Do:** press `d`.

**Look for:**

- [ ] The house disappears from all four widgets at once — label, caption,
      button and checkbutton.
- [ ] The status line says `image=gone` and the registry no longer lists
      `house`.
- [ ] **The widgets stay exactly the size they were** — whatever `Label
      asks` said before, it still says. This is measured Tk behaviour: deleting an image under a live
      Label left it at its old 22x12. The geometry it negotiated survives;
      only the drawing stops.
- [ ] `Home` comes back on the captioned label. With no image, `compound=none`
      has nothing to prefer over the text.
- [ ] The **arrow is unaffected**. It is still referenced, so it is still
      there — which is the whole distinction being drawn.
- [ ] Nothing raises. An image going away underneath a widget is not an
      error; only *setting* a name that does not exist is.

This is why every tkinter tutorial says to keep a reference to your images.

**Do:** press `r`.

- [ ] Everything comes back, **all four widgets included**. (The checkbutton
      was the one left blank the first time this was run: it was built
      inline and never captured, so the rebuild could not reach it.)

---

## What would count as a failure

- **An oval circle.** That is the half-cell plane not being used, and it is
  the failure this scenario exists to make visible.
- An image whose height in cells equals its height in pixels.
- Text appearing next to an image at `compound=none`.
- A widget not following its image's size, or following it only after
  something else is touched.
- A hole painting over what is behind it.
- `d` leaving the art on the screen. The image is gone and the widget agrees
  it has none; anything still drawn is a repaint that never happened.
- `d` collapsing a widget to nothing rather than leaving its size alone.
- An exception from `d`, or from the terminal being resized at any point.
