# Arda Güler Chance-Creation Analysis — 2026/27

This folder contains the derived data and analysis code used for my analysis of Arda Güler's chance creation and Real Madrid's performance during the opening seven La Liga matches of the 2026/27 season.

The purpose of publishing this is reproducibility. These are the files behind the statistics used in the post so that the calculations and event classifications can be inspected rather than taken at face value.

## Main Results

Across Arda Güler's first seven La Liga appearances:

| Chance Type | Chances | Share |
|---|---:|---:|
| Open Play | 11 | 39.3% |
| Corners | 12 | 42.9% |
| Free Kicks | 5 | 17.9% |
| Set Pieces Total | 17 | 60.7% |
| Total | 28 | 100% |

Of the 17 identified set-piece chances, one resulted in a credited assist.

Across Arda's five La Liga starts:

- 326.6 starter minutes
- 23 total chances created
- 13 set-piece chances
- 10 open-play chances
- 2.76 open-play chances created per 90
- 0 open-play goals
- 0 open-play assists

## Data Sources

The analysis was built using:

- Official La Liga match play-by-play/event data
- Sportmonks API match-event, lineup, substitution and player-minute data
- Official UEFA match timelines, lineups and statistics for Champions League matches
- FBref team/player statistics for reference and cross-checking

Raw third-party provider/API data is not redistributed in this folder.

The CSV files included here are derived analysis outputs produced from the source data.

## Chance Classification

Each identified chance was classified into one of the following categories:

- OPEN PLAY
- CORNER
- FREE KICK
- PENALTY / other set-piece sequence where applicable

The classification process uses event sequencing rather than simply assigning every shot after a dead ball to a set piece.

The general logic was:

1. Explicit play-type information in the source event takes priority.
2. An immediate same-team continuation from a corner is classified as CORNER.
3. An attacking free-kick continuation may be classified as FREE KICK when it occurs within the defined sequence and no intervening shot, goal or possession/reset event terminates the sequence.
4. Defensive-half free kicks are not automatically propagated into attacking set-piece sequences.
5. Goals and relevant restarts terminate the previous sequence.
6. Events not meeting set-piece criteria are classified as OPEN PLAY.

Individual events and player ON/OFF intervals were manually audited where necessary.

## Included Derived Data

### `derived_data/laliga_2026_27_play_type_events_FINAL.csv`

Event-level dataset containing the final play-type classifications used in the analysis.

### `derived_data/laliga_2026_27_arda_events_FINAL.csv`

Arda-specific event dataset used to audit his chance creation and the open-play/set-piece breakdown.

### `derived_data/laliga_2026_27_arda_brahim_start_audit.csv`

Starter-minute audit used for the Arda Güler/Brahim Díaz comparison.

## Included Code

### `code/build_2026_27_play_type_events_FINAL.py`

Builds the final play-type event dataset and applies the open-play/set-piece classification logic.

This is the primary script behind the 28-chance breakdown.

### `code/arda_full_on_off_GF_GA_2026_27.py`

Calculates Real Madrid's open-play goals for/against during Arda's ON and OFF minutes.

For the seven-match sample:

- Arda ON: 348.0 minutes, 7 open-play goals scored, 1.81 per 90
- Arda OFF: 282.0 minutes, 7 open-play goals scored, 2.23 per 90

This corresponds to an observed open-play scoring rate approximately 19% lower during Arda's minutes in this sample.

This is descriptive ON/OFF data and should not by itself be interpreted as proving causation.

### `code/compare_arda_brahim_starts_2026_27.py`

Produces the starter-minute comparison between Arda Güler and Brahim Díaz used in the analysis.

The Brahim sample consists of only two club starts and should be treated accordingly.

## Important Limitations

This is a small early-season sample.

The statistics describe what happened during the observed minutes. They do not establish that a particular player caused Real Madrid's scoring rate to increase or decrease.

The Arda/Brahim starter comparison is especially limited because Brahim has only two starts in the sample, including one Champions League start.

The analysis is intended to separate raw chance-creation totals into their underlying components and make the calculations behind the argument transparent.

## Reproducibility

API credentials, private credentials, and raw third-party provider data are intentionally excluded.

The included scripts and derived CSV files are provided so the calculations, classifications and resulting statistics used in the analysis can be inspected and challenged.

If you find a classification or calculation error, point to the event and it can be checked against the underlying match record.
