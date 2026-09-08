# Card Forge

Native PySide6 desktop app for composing gold-text cards over a dark
illustrated base plate and exporting them as PNG. The rendering engine
(`engine/render.py`) is a refactor of the original `card_text.py` CLI and
produces pixel-identical output; the GUI is a front end on top of it.

![icon](assets/icon.png)

## Features

- Live full-resolution preview (debounced, rendered on a worker thread)
- Center mode and structured left mode: `## ` bold headers, `[] ` empty
  checkbox, `[x] ` checked checkbox, blank line = paragraph break
- Inline markup with toolbar buttons: `**bold**`, `*italic*`,
  `***bold italic***`, `~~strikethrough~~` (Ctrl+B / Ctrl+I)
- Two-column checked-list mode for exercise cards
- Style controls: base plate, fonts, title/body max px, gap, line spacing,
  margins, text region, gold gradient palette — all savable as presets
- Filename helper composing `ksd{day}{kind}{n}{suffix}.png`
- Config persistence (fields + window geometry), recent exports,
  drag-a-PNG-to-set-base-plate
- Ctrl+E export · Ctrl+S save preset · Ctrl+Shift+P 100% preview window

## Run

```
pip install PySide6 Pillow
python main.py
```

`engine/render.py` is importable on its own — `render(CardSpec, base_image)`
returns the composited PIL image; no Qt required.

## Layout

```
main.py              app entry
engine/render.py     rendering engine (pure functions, no argparse)
ui/main_window.py    three-column main window + export bar
ui/preview.py        live preview pane + 100% window
ui/settings.py       style panel, sliders, gold palette, presets
presets/             JSON style presets
assets/              app icon
```
