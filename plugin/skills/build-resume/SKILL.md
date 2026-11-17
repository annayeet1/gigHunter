---
name: build-resume
description: Interactively build or rebuild a master resume (and grow aboutme.md) by interviewing the user and reading their existing resumes, following gigHunter's sourced resume guidelines. Use when the user wants to create a resume from scratch, refresh their master resume, or fill in their gigHunter profile.
---

# gigHunter: build-resume

The full instructions for this workflow ship with the gigHunter engine, so they always match the
installed version.

1. Run `python -m gighunter workflow build-resume` (use `python3` on macOS/Linux).
2. If the command isn't found, the engine isn't installed. Offer to install it with
   `pip install "gighunter @ git+https://github.com/annayeet1/gigHunter"`, then retry step 1.
3. Follow the printed instructions exactly; they are this skill's instructions.
   The user's request and arguments for this skill are the input to that workflow.
