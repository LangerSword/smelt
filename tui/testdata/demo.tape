# VHS demo tape — furnace (replay + live run)
#
# Record with:   vhs tui/testdata/demo.tape        (run from the repo root)
# Requires:      vhs, ttyd, ffmpeg on PATH.
#   install vhs:   go install github.com/charmbracelet/vhs@latest
#   install ttyd:  your package manager (e.g. `apt install ttyd`)
#
# Output lands at tui/demo.gif (a short loop for the README).

Output tui/demo.gif
Set FontSize 14
Set Width 1150
Set Height 720
Set Padding 12
Set Theme "Dracula"
Set Shell "bash"

# 1) replay the accepted gemini run
Type "cd tui && ./furnace replay ../runs/261011-024849-b4f411"
Enter
Sleep 3s
Type "q"
Sleep 500ms

# 2) replay the refused run (ASH, stops at select)
Type "./furnace replay testdata/runs/refused-gemini"
Enter
Sleep 3s
Type "q"
Sleep 500ms

# 3) live run via the local model (no API key needed)
Type "./furnace run ../examples/demo/run_length.py:rle_encode --provider local --model gemma-4-e2b-qat --smelt ../.venv/bin/smelt"
Enter
Sleep 40s
Type "q"
Sleep 1s
