# Cyberpunk 2077 Breach Protocol

[中文](README.md)

A local tool for the breach protocol minigame in *Cyberpunk 2077*. Paste a screenshot and it reads the code matrix, the target sequences, and the buffer length, then marks a route.

The program only analyzes an image you open or paste. It does not read game memory, click for you, or use the network while it runs.

This project continues [Cyberpunk_CodeMatrix_decipher](https://github.com/zlmturnout/Cyberpunk_CodeMatrix_decipher). The original tool asked you to type the matrix and then enumerated routes. This version reads the screenshot. The route rules still come from that project, and the MIT license in `LICENSE` is kept.

## What it does

Breach protocol shows a square code matrix, one to three sequences to upload, and a row of buffer slots. You start on any cell in the first row. After that, picks alternate between the current row and the current column, and a cell cannot be used twice. A sequence uploads when its codes appear as a contiguous stretch of the path.

This program:

- Finds the code matrix. The size is not fixed, so 4×4 through 7×7 screenshots work.
- Reads the target sequences to the right of the matrix. Each sequence is usually 2 to 4 codes.
- Counts the buffer slots above the matrix. If the count is unclear, it uses 8 and asks you to check.
- Finds a route, numbers the cells 1, 2, 3… on the screenshot, and lists the row and column of each step.

The game uses only six codes: `1C`, `55`, `7A`, `BD`, `E9`, and `FF`. Recognition compares those yellow monospace glyphs. It does not OCR the Chinese labels. The glyph templates live in `templates.npz`. An uncertain cell gets a red frame. Change it in the dropdown and the route is calculated again.

## How a route is chosen

The search prefers, in order:

1. More completed sequences.
2. Longer sequences when the count is the same.
3. A shorter path, so fewer later clicks can go wrong.

A sequence matches any contiguous stretch of the path. Stretches may sit next to each other or overlap. If the buffer cannot hold every sequence, the result lists what was uploaded and what was not. A square matrix with a small buffer can be searched completely, so the result is determined by those rules.

## How to run

You need Python 3, plus `numpy` and `pillow`. The window uses tkinter from the Python install.

```bat
python -m pip install -r requirements.txt
```

pip needs the network once, while installing. After that, double-click `启动.bat` or run `python app.py` in this folder. Running the solver does not use the network.

1. Copy the breach protocol screen with your screenshot tool, focus this window, and press Ctrl+V. **Open screenshot** also accepts a saved image.
2. The view frames the code matrix. Scroll to zoom around the pointer, drag with the left button, and use **Full image** to see the whole screenshot.
3. Check the matrix, sequences, and buffer size on the right. A red frame means that cell is uncertain.
4. Click the listed rows and columns in order. If the buffer is not full, the listed steps are enough; the remaining cells can be anything.

**English** on the toolbar switches the interface to English. **中文** switches it back. Step numbers and the codes themselves stay the same.

**Keep on top** holds the window above the game. Click it again to turn that off.

## Files

| File | Role |
| --- | --- |
| `app.py` | Window: open or paste a screenshot, edit cells, draw the route, switch language |
| `recognize.py` | Reads the matrix, sequences, buffer length, and a confidence for each cell |
| `solver.py` | Searches for a route under the breach protocol rules |
| `templates.npz` | Glyph templates for the six codes |
| `启动.bat` | Double-click launcher on Windows |
| `requirements.txt` | Python dependencies |
