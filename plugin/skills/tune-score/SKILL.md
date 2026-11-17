---
name: tune-score
description: Calibrate gigHunter's match score to the user's own judgement. Show real scanned listings, collect strong/maybe/no ratings, fit the score weights, and suggest threshold, alias and preference fixes. Use when scores feel wrong, the digest has too many or too few listings, or the user wants to tune or calibrate matching.
---

# gigHunter: tune-score

The full instructions for this workflow ship with the gigHunter engine, so they always match the
installed version.

1. Run `python -m gighunter workflow tune-score` (use `python3` on macOS/Linux).
2. If the command isn't found, the engine isn't installed. Offer to install it with
   `pip install "gighunter @ git+https://github.com/annayeet1/gigHunter"`, then retry step 1.
3. Follow the printed instructions exactly; they are this skill's instructions.
   The user's request and arguments for this skill are the input to that workflow.
