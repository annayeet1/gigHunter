<!-- gigHunter workflow 'tune-score'. Shipped with the engine; print it with
     `python -m gighunter workflow tune-score`. The Claude Code plugin skill
     /gighunter:tune-score loads this same text. -->

# Tune the match score (interactive)

## 0. Preflight
Run `python -m gighunter --version` (`python3` on macOS/Linux) and `python -m gighunter config`.
If the profile has no skills or target titles, stop and suggest the `build-resume` workflow (`/gighunter:build-resume` or `python -m gighunter workflow build-resume`) (or filling in
aboutme.md / JobParams.md): tuning an empty profile is meaningless.

## 1. Get listings to rate
Run `python -m gighunter scan --top 80 --save --json` and parse the JSON. Pick **8-12** listings that
span the range: about a third high-scoring, a third middling, and a third low but plausible. Vary companies and
titles. Skip listings already in `data/labels.jsonl`.

## 2. Collect ratings
Use AskUserQuestion with up to 4 listings per call, one question per listing:
- question: "<title> @ <company> (<location>), currently <score>%: how good a fit?"
- options: **Strong fit** / **Maybe** / **Not a fit**, each description showing the matched skills and gaps

Record each one: `python -m gighunter label <id> strong|maybe|no`.

For **surprises** (scored 70 or more but rated "no", or under 50 but rated "strong"), ask briefly why, and
save the reason with `--note "..."`. These reasons are the most valuable input.

## 3. Fit and explain
`python -m gighunter tune` prints ranking accuracy before and after, current and suggested weights,
a suggested `min_match_score`, and each listing's old and new score. Explain the result in plain words,
e.g. "title match was over-weighted: three 'no' listings scored high on title alone."

Also propose **non-weight fixes** suggested by the notes. These are often better than weights:
- skill synonyms missing: add to `config/skill_aliases.yaml`
- recurring reasons for "no": `dealbreakers` in JobParams.md
- liked roles under other titles: `target_titles` in JobParams.md
- liked domains: `bonus_keywords` in JobParams.md
- the threshold: `min_match_score` in `config/schedule.toml`

Don't change aboutme.md skills to game the score. Those are facts.

## 4. Apply with consent
Ask which changes to apply (AskUserQuestion, multiSelect). For weights run `python -m gighunter tune --apply`;
make the other edits directly. Then rerun `python -m gighunter scan --top 15` and show the new top list.
Offer to commit `config/`, `JobParams.md`, and `data/labels.jsonl`. Labels accumulate, so tuning
improves each time this skill runs.
