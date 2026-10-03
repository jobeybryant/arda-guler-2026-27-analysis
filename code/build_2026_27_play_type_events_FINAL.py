import json
import re
import csv
from pathlib import Path
from collections import Counter


# ============================================================
# ARDA OPEN-PLAY PROJECT
# FINAL PLAY-TYPE CLASSIFIER — 2026-27 LALIGA
#
# PURPOSE
# -------
# Classify every shot/goal as:
#
#   OPEN_PLAY
#   CORNER
#   FREE_KICK
#   PENALTY
#
# PHILOSOPHY
# ----------
# 1. Explicit La Liga text always wins.
# 2. Corners can propagate through an immediate attacking
#    second phase, but only with strict boundaries.
# 3. Free kicks are classified much more strictly.
# 4. Defensive-half free kicks NEVER make a later attacking
#    shot a set-piece shot merely because they occurred nearby.
# 5. Goals, possession-changing events, and restarts terminate
#    a previous set-piece sequence.
# 6. Every non-explicit inferred classification is auditable.
#
# This script does NOT calculate Arda ON/OFF.
# It creates the final event classification layer.
# ============================================================


RAW_ROOT = Path(
    "data/raw/laliga_2026_27/matches"
)

OUTPUT = Path(
    "data/processed/laliga_2026_27_play_type_events_FINAL.csv"
)

ARDA_OUTPUT = Path(
    "data/processed/laliga_2026_27_arda_events_FINAL.csv"
)

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# KNOWN EVENT KINDS
# ============================================================

SHOT_KINDS = {
    1: "BLOCKED",
    2: "SAVED",
    8: "GOAL",
    10: "MISSED",
    12: "OWN_GOAL",
    18: "WOODWORK",
    29: "PENALTY_GOAL",
}

GOAL_KINDS = {
    8,
    12,
    29,
}

CORNER_KIND = 3

FREE_KICK_WIN_KIND = 7

PENALTY_KINDS = {
    13,
    16,
    29,
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def low(value):
    return clean(value).lower()


def kind_id(event):

    return (
        event
        .get("match_comment_kind", {})
        .get("id")
    )


def minute_value(value):

    if value is None:
        return None

    s = str(value).strip()

    m = re.match(
        r"^(\d+)(?:\+(\d+))?$",
        s
    )

    if m:

        return (
            int(m.group(1))
            +
            int(m.group(2) or 0)
        )

    try:
        return float(s)

    except Exception:
        return None


# ============================================================
# PLAYER / TEAM EXTRACTION
# ============================================================

def extract_player_team(text):

    text = clean(text)

    patterns = [

        r"Attempt saved\. ([^(]+?) \(([^)]+)\)",
        r"Attempt blocked\. ([^(]+?) \(([^)]+)\)",
        r"Attempt missed\. ([^(]+?) \(([^)]+)\)",

        r"Goal!.*?\. ([^(]+?) \(([^)]+)\)",

        r"Own Goal by ([^,]+), ([^.]+)\.",

        # Spanish

        r"Remate fallado por ([^(]+?) \(([^)]+)\)",

        r"Remate rechazado de ([^(]+?) \(([^)]+)\)",

        r"Remate parado.*?\. ([^(]+?) \(([^)]+)\)",

        r"¡Gooooool!.*?\. ([^(]+?) \(([^)]+)\)",
    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if m:

            return (
                clean(m.group(1)),
                clean(m.group(2))
            )

    return "", ""


# ============================================================
# ASSISTER
# ============================================================

def extract_assister(text):

    patterns = [

        r"Assisted by ([^.]+?)(?: with | following |\.|$)",

        r"Asistencia de ([^.]+?)(?: con | tras |\.|$)",
    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if m:

            return clean(
                m.group(1)
            )

    return ""


# ============================================================
# CREATION TYPE
# ============================================================

def creation_type(text):

    t = low(text)

    if (
        "through ball" in t
        or "pase en profundidad" in t
    ):
        return "THROUGH_BALL"

    if (
        "fast break" in t
        or "contraataque" in t
        or "contragolpe" in t
    ):
        return "FAST_BREAK"

    if (
        "with a cross" in t
        or "con un centro" in t
        or "centro al área" in t
        or "centro al area" in t
    ):
        return "CROSS"

    if (
        "headed pass" in t
        or "pase de cabeza" in t
    ):
        return "HEADED_PASS"

    if extract_assister(text):
        return "PASS"

    return "UNASSISTED"


# ============================================================
# EXPLICIT CLASSIFICATION
#
# Highest-confidence source.
# ============================================================

def explicit_classification(
    text,
    event_kind
):

    t = low(text)

    # --------------------------------------------------------
    # PENALTY
    # --------------------------------------------------------

    if (
        event_kind == 29
        or
        (
            "penalty" in t
            and any(
                x in t
                for x in [
                    "converts",
                    "converted",
                    "saved",
                    "missed",
                ]
            )
        )
        or
        (
            "penalti" in t
            and any(
                x in t
                for x in [
                    "convierte",
                    "convirtió",
                    "parado",
                    "fallado",
                ]
            )
        )
    ):

        return (
            "PENALTY",
            "EXPLICIT_TEXT",
            "HIGH"
        )

    # --------------------------------------------------------
    # CORNER
    # --------------------------------------------------------

    corner_phrases = [

        "following a corner",
        "from a corner",
        "after a corner",

        "tras un saque de esquina",
        "tras botar un córner",
        "tras botar un corner",
    ]

    if any(
        phrase in t
        for phrase in corner_phrases
    ):

        return (
            "CORNER",
            "EXPLICIT_TEXT",
            "HIGH"
        )

    # --------------------------------------------------------
    # FREE KICK / SET PIECE
    # --------------------------------------------------------

    fk_phrases = [

        "direct free kick",
        "direct free-kick",

        "following a free kick",
        "following a free-kick",

        "from a free kick",
        "from a free-kick",

        "following a set piece situation",
        "following a set-piece situation",

        "falta directa",
        "libre directo",

        "tras botar una falta",
    ]

    if any(
        phrase in t
        for phrase in fk_phrases
    ):

        return (
            "FREE_KICK",
            "EXPLICIT_TEXT",
            "HIGH"
        )

    # --------------------------------------------------------
    # OPEN-PLAY TRANSITION
    # --------------------------------------------------------

    transition_phrases = [

        "following a fast break",
        "fast break",

        "contraataque",
        "contragolpe",
    ]

    if any(
        phrase in t
        for phrase in transition_phrases
    ):

        return (
            "OPEN_PLAY",
            "EXPLICIT_TEXT",
            "HIGH"
        )

    return (
        None,
        None,
        None
    )


# ============================================================
# EVENT FLAGS
# ============================================================

def is_corner_event(event):

    t = low(
        event.get(
            "content",
            ""
        )
    )

    return (
        kind_id(event) == CORNER_KIND
        or t.startswith("corner,")
        or t.startswith("corner ")
        or "saque de esquina" in t
    )


def is_goal_event(event):

    return (
        kind_id(event)
        in GOAL_KINDS
    )


def is_shot_event(event):

    return (
        kind_id(event)
        in SHOT_KINDS
    )


def is_penalty_event(event):

    t = low(
        event.get(
            "content",
            ""
        )
    )

    return (
        kind_id(event)
        in PENALTY_KINDS

        or "penalty" in t

        or "penalti" in t
    )


def is_free_kick_win(event):

    t = low(
        event.get(
            "content",
            ""
        )
    )

    return (
        kind_id(event)
        == FREE_KICK_WIN_KIND

        or "wins a free kick" in t

        or "ha recibido una falta" in t
    )


# ============================================================
# FREE-KICK LOCATION
#
# We only infer an attacking set piece from context if the
# description clearly places the FK in an attacking area.
# ============================================================

def attacking_free_kick(event):

    t = low(
        event.get(
            "content",
            ""
        )
    )

    attacking_phrases = [

        "attacking half",
        "final third",
        "left wing",
        "right wing",
        "dangerous position",

        "campo contrario",
        "zona de ataque",
        "banda izquierda",
        "banda derecha",
    ]

    defensive_phrases = [

        "defensive half",
        "zona defensiva",
        "propio campo",
    ]

    if any(
        x in t
        for x in defensive_phrases
    ):
        return False

    return any(
        x in t
        for x in attacking_phrases
    )


# ============================================================
# HARD SEQUENCE RESET
#
# If one of these occurs between a set piece and a later shot,
# the old set-piece phase is dead.
# ============================================================

def hard_reset(event):

    t = low(
        event.get(
            "content",
            ""
        )
    )

    if is_goal_event(
        event
    ):
        return True

    reset_phrases = [

        "offside",
        "goal kick",
        "throw-in",
        "throw in",

        "substitution",

        "first half ends",
        "second half ends",
        "first half begins",
        "second half begins",

        "match ends",

        "fuera de juego",
        "saque de puerta",
        "saque de banda",
        "cambio en",

        "final de la primera parte",
        "final del partido",
    ]

    return any(
        phrase in t
        for phrase in reset_phrases
    )


# ============================================================
# TEAM REFERENCES
#
# Used only for sanity checking context.
# ============================================================

def team_mentioned(
    event,
    team
):

    if not team:
        return False

    return (
        low(team)
        in low(
            event.get(
                "content",
                ""
            )
        )
    )


# ============================================================
# CORNER CONTINUATION
#
# Corner rules are intentionally broader than FK rules because
# La Liga often logs:
#
#   corner
#   first shot
#   rebound / second shot
#
# as separate comments.
#
# We permit:
#
#   CORNER
#       -> shot
#
# or:
#
#   CORNER
#       -> shot
#       -> immediate second shot
#
# but NOT long sequences.
# ============================================================

def infer_corner(
    comments,
    shot_index,
    shot_team
):

    shot = comments[
        shot_index
    ]

    shot_min = minute_value(
        shot.get("time")
    )

    # Maximum three preceding events.
    start = max(
        0,
        shot_index - 3
    )

    prior = comments[
        start:shot_index
    ]

    prior = list(
        reversed(prior)
    )

    intervening_shots = 0

    context = []

    for distance, event in enumerate(
        prior,
        start=1
    ):

        text = clean(
            event.get(
                "content",
                ""
            )
        )

        context.append(
            f'{event.get("time")}\' {text}'
        )

        event_min = minute_value(
            event.get(
                "time"
            )
        )

        # Too far away.
        if (
            shot_min is not None
            and event_min is not None
            and shot_min - event_min > 1
        ):
            break

        # Hard reset means stop.
        if hard_reset(
            event
        ):
            break

        if is_shot_event(
            event
        ):

            # Allow at most ONE prior shot in the same
            # attacking corner phase.
            intervening_shots += 1

            if intervening_shots > 1:
                break

            # If the previous shot is clearly by the other
            # team, stop.
            prev_player, prev_team = (
                extract_player_team(
                    event.get(
                        "content",
                        ""
                    )
                )
            )

            if (
                prev_team
                and shot_team
                and low(prev_team)
                != low(shot_team)
            ):
                break

            continue

        if is_corner_event(
            event
        ):

            # Corner description should reference the
            # shooting team.
            if (
                shot_team
                and not team_mentioned(
                    event,
                    shot_team
                )
            ):
                break

            return (
                True,
                context
            )

    return (
        False,
        context
    )


# ============================================================
# FREE-KICK CONTINUATION
#
# Much stricter than corners.
#
# We infer FREE_KICK only when:
#
# - an attacking FK win is extremely close;
# - no shot/goal/reset intervenes;
# - it belongs to the shooting team;
# - maximum 1 clock minute apart.
#
# Defensive-half FKs are NEVER propagated.
# ============================================================

def infer_free_kick(
    comments,
    shot_index,
    shot_team
):

    shot = comments[
        shot_index
    ]

    shot_min = minute_value(
        shot.get("time")
    )

    # Only two immediately preceding PBP events.
    start = max(
        0,
        shot_index - 2
    )

    prior = comments[
        start:shot_index
    ]

    prior = list(
        reversed(prior)
    )

    context = []

    for event in prior:

        text = clean(
            event.get(
                "content",
                ""
            )
        )

        context.append(
            f'{event.get("time")}\' {text}'
        )

        event_min = minute_value(
            event.get(
                "time"
            )
        )

        if (
            shot_min is not None
            and event_min is not None
            and shot_min - event_min > 1
        ):
            break

        if hard_reset(
            event
        ):
            break

        # Any intervening shot kills FK inference.
        if is_shot_event(
            event
        ):
            break

        if is_free_kick_win(
            event
        ):

            # Must clearly be attacking.
            if not attacking_free_kick(
                event
            ):
                break

            # Must mention the shooting team.
            if (
                shot_team
                and not team_mentioned(
                    event,
                    shot_team
                )
            ):
                break

            return (
                True,
                context
            )

    return (
        False,
        context
    )


# ============================================================
# PENALTY CONTEXT
# ============================================================

def infer_penalty(
    comments,
    shot_index
):

    start = max(
        0,
        shot_index - 2
    )

    prior = comments[
        start:shot_index
    ]

    prior = list(
        reversed(prior)
    )

    context = []

    for event in prior:

        text = clean(
            event.get(
                "content",
                ""
            )
        )

        context.append(
            f'{event.get("time")}\' {text}'
        )

        if hard_reset(
            event
        ):
            break

        if is_penalty_event(
            event
        ):

            return (
                True,
                context
            )

    return (
        False,
        context
    )


# ============================================================
# FINAL CLASSIFICATION
# ============================================================

def classify_event(
    comments,
    shot_index,
    shot_team
):

    shot = comments[
        shot_index
    ]

    text = clean(
        shot.get(
            "content",
            ""
        )
    )

    event_kind = kind_id(
        shot
    )

    # --------------------------------------------------------
    # 1. EXPLICIT TEXT
    # --------------------------------------------------------

    play_type, method, confidence = (
        explicit_classification(
            text,
            event_kind
        )
    )

    if play_type:

        return (
            play_type,
            method,
            confidence,
            ""
        )

    # --------------------------------------------------------
    # 2. PENALTY CONTEXT
    # --------------------------------------------------------

    yes, context = infer_penalty(
        comments,
        shot_index
    )

    if yes:

        return (
            "PENALTY",
            "IMMEDIATE_SEQUENCE",
            "HIGH",
            " || ".join(context)
        )

    # --------------------------------------------------------
    # 3. CORNER CONTEXT
    # --------------------------------------------------------

    yes, context = infer_corner(
        comments,
        shot_index,
        shot_team
    )

    if yes:

        return (
            "CORNER",
            "IMMEDIATE_SEQUENCE",
            "HIGH",
            " || ".join(context)
        )

    # --------------------------------------------------------
    # 4. ATTACKING FREE KICK CONTEXT
    # --------------------------------------------------------

    yes, context = infer_free_kick(
        comments,
        shot_index,
        shot_team
    )

    if yes:

        return (
            "FREE_KICK",
            "IMMEDIATE_ATTACKING_FK",
            "HIGH",
            " || ".join(context)
        )

    # --------------------------------------------------------
    # 5. OPEN PLAY
    #
    # No explicit or tightly connected dead-ball origin.
    # --------------------------------------------------------

    return (
        "OPEN_PLAY",
        "NO_QUALIFYING_SET_PIECE",
        "HIGH",
        ""
    )


# ============================================================
# MATCH LABEL
# ============================================================

def match_label(
    path
):

    name = path.stem

    return re.sub(
        r"^gw\d+_",
        "",
        name
    )


# ============================================================
# MAIN EXTRACTION
# ============================================================

files = sorted(
    RAW_ROOT.glob(
        "*.json"
    )
)

rows = []


print("=" * 90)
print("ARDA OPEN-PLAY PROJECT")
print("FINAL 2026-27 PLAY-TYPE CLASSIFIER")
print("=" * 90)

print(
    "\nMatch files:",
    len(files)
)


for path in files:

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    comments = (
        data
        ["props"]
        ["pageProps"]
        ["data"]
        ["comments"]
    )

    # La Liga comments are newest -> oldest.
    comments = list(
        reversed(
            comments
        )
    )

    match = match_label(
        path
    )

    match_count = 0

    for i, event in enumerate(
        comments
    ):

        event_kind = kind_id(
            event
        )

        if (
            event_kind
            not in SHOT_KINDS
        ):
            continue

        text = clean(
            event.get(
                "content",
                ""
            )
        )

        player, team = (
            extract_player_team(
                text
            )
        )

        assister = (
            extract_assister(
                text
            )
        )

        (
            play_type,
            method,
            confidence,
            context
        ) = classify_event(
            comments,
            i,
            team
        )

        row = {

            "Season":
                "2026-27",

            "Match_File":
                path.name,

            "Match":
                match,

            "Minute":
                event.get(
                    "time"
                ),

            "Kind_ID":
                event_kind,

            "Event":
                SHOT_KINDS[
                    event_kind
                ],

            "Player":
                player,

            "Team":
                team,

            "Assister":
                assister,

            "Creation_Type":
                creation_type(
                    text
                ),

            "Play_Type":
                play_type,

            "Classification_Method":
                method,

            "Confidence":
                confidence,

            "Description":
                text,

            "Sequence_Context":
                context,
        }

        rows.append(
            row
        )

        match_count += 1

    print(
        f"{path.name}: "
        f"{match_count} shots"
    )


# ============================================================
# WRITE FULL EVENT FILE
# ============================================================

columns = [

    "Season",
    "Match_File",
    "Match",
    "Minute",
    "Kind_ID",
    "Event",
    "Player",
    "Team",
    "Assister",
    "Creation_Type",
    "Play_Type",
    "Classification_Method",
    "Confidence",
    "Description",
    "Sequence_Context",
]


with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=columns
    )

    writer.writeheader()

    writer.writerows(
        rows
    )


# ============================================================
# ARDA-ONLY FILE
# ============================================================

arda_rows = [

    row
    for row in rows

    if (
        "arda" in low(
            row["Player"]
        )

        or

        "arda" in low(
            row["Assister"]
        )
    )
]


with ARDA_OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=columns
    )

    writer.writeheader()

    writer.writerows(
        arda_rows
    )


# ============================================================
# GLOBAL SUMMARY
# ============================================================

print("\n" + "=" * 90)
print("FINAL PLAY-TYPE SUMMARY")
print("=" * 90)


counts = Counter(
    row[
        "Play_Type"
    ]
    for row in rows
)


for key in [
    "OPEN_PLAY",
    "CORNER",
    "FREE_KICK",
    "PENALTY",
]:

    print(
        f"{key:12s}: "
        f"{counts[key]:3d}"
    )


print(
    "\nTOTAL:",
    len(rows)
)


# ============================================================
# TEAM SPLIT
# ============================================================

print("\n" + "=" * 90)
print("REAL MADRID SHOTS — PLAY TYPE")
print("=" * 90)


rm_rows = [

    row
    for row in rows

    if low(
        row["Team"]
    ) == "real madrid"
]


rm_counts = Counter(
    row[
        "Play_Type"
    ]
    for row in rm_rows
)


for key in [
    "OPEN_PLAY",
    "CORNER",
    "FREE_KICK",
    "PENALTY",
]:

    value = rm_counts[
        key
    ]

    pct = (
        100 * value / len(rm_rows)
        if rm_rows
        else 0
    )

    print(
        f"{key:12s}: "
        f"{value:3d} "
        f"({pct:5.1f}%)"
    )


print(
    "TOTAL RM SHOTS:",
    len(rm_rows)
)


# ============================================================
# ARDA — SHOTS CREATED
# ============================================================

arda_created = [

    row
    for row in rows

    if "arda" in low(
        row["Assister"]
    )
]


print("\n" + "=" * 90)
print("ARDA — ALL SHOTS CREATED")
print("=" * 90)


for row in arda_created:

    print()

    print(
        f'{row["Match"]} '
        f'{row["Minute"]}\''
    )

    print(
        f'→ {row["Player"]} '
        f'[{row["Event"]}]'
    )

    print(
        "PLAY:",
        row["Play_Type"]
    )

    print(
        "CREATION:",
        row["Creation_Type"]
    )

    print(
        "METHOD:",
        row[
            "Classification_Method"
        ]
    )

    print(
        row["Description"]
    )

    if row[
        "Sequence_Context"
    ]:

        print(
            "CONTEXT:",
            row[
                "Sequence_Context"
            ]
        )


# ============================================================
# ARDA — CREATIVE SPLIT
# ============================================================

print("\n" + "=" * 90)
print("ARDA — FINAL CREATIVE SPLIT")
print("=" * 90)


arda_create_counts = Counter(
    row[
        "Play_Type"
    ]
    for row in arda_created
)


total_created = len(
    arda_created
)


for key in [
    "OPEN_PLAY",
    "CORNER",
    "FREE_KICK",
    "PENALTY",
]:

    value = (
        arda_create_counts[
            key
        ]
    )

    pct = (
        100 * value
        / total_created

        if total_created
        else 0
    )

    print(
        f"{key:12s}: "
        f"{value:3d} "
        f"({pct:5.1f}%)"
    )


set_piece_created = sum(

    arda_create_counts[
        key
    ]

    for key in [
        "CORNER",
        "FREE_KICK",
        "PENALTY",
    ]
)


print(
    "\nTOTAL CREATED:",
    total_created
)

print(
    "OPEN PLAY:",
    arda_create_counts[
        "OPEN_PLAY"
    ]
)

print(
    "SET PIECE:",
    set_piece_created
)


if total_created:

    print(
        "SET-PIECE SHARE:",
        f"{100 * set_piece_created / total_created:.1f}%"
    )


# ============================================================
# ARDA — OWN SHOTS
# ============================================================

arda_shots = [

    row
    for row in rows

    if "arda" in low(
        row["Player"]
    )
]


print("\n" + "=" * 90)
print("ARDA — OWN SHOTS")
print("=" * 90)


for row in arda_shots:

    print(
        f'{row["Match"]} '
        f'{row["Minute"]}\' '
        f'{row["Event"]:8s} '
        f'| {row["Play_Type"]:10s} '
        f'| {row["Description"]}'
    )


arda_shot_counts = Counter(
    row[
        "Play_Type"
    ]
    for row in arda_shots
)


print("\nARDA OWN-SHOT SPLIT:")


for key in [
    "OPEN_PLAY",
    "CORNER",
    "FREE_KICK",
    "PENALTY",
]:

    print(
        f"{key:12s}: "
        f"{arda_shot_counts[key]}"
    )


# ============================================================
# ARDA — ACTUAL ASSISTS
# ============================================================

arda_assists = [

    row
    for row in arda_created

    if row[
        "Event"
    ] == "GOAL"
]


print("\n" + "=" * 90)
print("ARDA — ACTUAL ASSISTS")
print("=" * 90)


for row in arda_assists:

    print(
        f'{row["Match"]} '
        f'{row["Minute"]}\' '
        f'→ {row["Player"]} '
        f'| {row["Play_Type"]} '
        f'| {row["Creation_Type"]}'
    )


assist_counts = Counter(
    row[
        "Play_Type"
    ]
    for row in arda_assists
)


print(
    "\nTOTAL ASSISTS:",
    len(
        arda_assists
    )
)

print(
    "OPEN-PLAY ASSISTS:",
    assist_counts[
        "OPEN_PLAY"
    ]
)

print(
    "SET-PIECE ASSISTS:",
    sum(
        assist_counts[x]
        for x in [
            "CORNER",
            "FREE_KICK",
            "PENALTY",
        ]
    )
)


# ============================================================
# ARDA — CREATION TYPE x PLAY TYPE
# ============================================================

print("\n" + "=" * 90)
print("ARDA — CREATION TYPE × PLAY TYPE")
print("=" * 90)


cross_table = Counter(

    (
        row[
            "Play_Type"
        ],
        row[
            "Creation_Type"
        ]
    )

    for row in arda_created
)


for (
    play_type,
    creation
), value in sorted(
    cross_table.items()
):

    print(
        f"{play_type:12s} "
        f"{creation:15s} "
        f"{value:3d}"
    )


# ============================================================
# SANITY CHECKS
# ============================================================

print("\n" + "=" * 90)
print("SANITY CHECKS")
print("=" * 90)


problems = []


# ------------------------------------------------------------
# Defensive-half FKs must never be inferred as FREE_KICK.
# ------------------------------------------------------------

for row in rows:

    if (
        row[
            "Classification_Method"
        ]
        == "IMMEDIATE_ATTACKING_FK"

        and

        any(
            phrase in low(
                row[
                    "Sequence_Context"
                ]
            )

            for phrase in [
                "defensive half",
                "zona defensiva",
                "propio campo",
            ]
        )
    ):

        problems.append(
            (
                "DEFENSIVE_FK_ERROR",
                row
            )
        )


# ------------------------------------------------------------
# Explicit fast breaks must be OPEN PLAY.
# ------------------------------------------------------------

for row in rows:

    t = low(
        row[
            "Description"
        ]
    )

    if (
        (
            "fast break" in t
            or "contraataque" in t
            or "contragolpe" in t
        )

        and

        row[
            "Play_Type"
        ]
        != "OPEN_PLAY"
    ):

        problems.append(
            (
                "FAST_BREAK_ERROR",
                row
            )
        )


# ------------------------------------------------------------
# Explicit corners must be CORNER.
# ------------------------------------------------------------

for row in rows:

    t = low(
        row[
            "Description"
        ]
    )

    if (
        (
            "following a corner" in t
            or "tras un saque de esquina" in t
        )

        and

        row[
            "Play_Type"
        ]
        != "CORNER"
    ):

        problems.append(
            (
                "CORNER_ERROR",
                row
            )
        )


if not problems:

    print(
        "PASS — no automatic sanity-check failures."
    )

else:

    print(
        "FAILURES:",
        len(problems)
    )

    for label, row in problems:

        print()

        print(
            label
        )

        print(
            row[
                "Match"
            ],
            row[
                "Minute"
            ]
        )

        print(
            row[
                "Description"
            ]
        )

        print(
            row[
                "Sequence_Context"
            ]
        )


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 90)
print("FILES WRITTEN")
print("=" * 90)

print(
    OUTPUT
)

print(
    ARDA_OUTPUT
)

print("\nDONE.")
