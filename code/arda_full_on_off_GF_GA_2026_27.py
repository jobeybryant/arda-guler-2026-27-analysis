import json
from pathlib import Path
import pandas as pd

# ============================================================
# PATHS
# ============================================================

RAW_DIR = Path("data/raw/laliga_2026_27/matches")
EVENT_FILE = Path(
    "data/processed/laliga_2026_27_play_type_events_FINAL.csv"
)

ARDA = "Arda Güler"

# Seven matches x 90 regulation minutes
TOTAL_MINUTES = 7 * 90


# ============================================================
# HELPERS
# ============================================================

def person_name(obj):
    if not isinstance(obj, dict):
        return ""
    return obj.get("person", {}).get("name", "")


def exact_time(ev):
    """
    Raw event elapsed time from zero-based minute + seconds.

    Example:
    minute=67, second=21 -> 67.35
    """
    minute = ev.get("minute")
    second = ev.get("second", 0)

    if minute is None:
        return None

    return float(minute) + float(second or 0) / 60.0


def get_root(path):
    d = json.loads(path.read_text())
    return d["props"]["pageProps"]


def find_arda_interval(path):
    root = get_root(path)

    started = False
    listed_sub = False

    lineups = root["data"]["lineups"]

    for side in ["home", "away"]:
        for x in lineups.get(side, {}).get("starts", []):
            if person_name(x) == ARDA:
                started = True

        for x in lineups.get(side, {}).get("subs", []):
            if person_name(x) == ARDA:
                listed_sub = True

    if started:
        start = 0.0
        end = 90.0
        status = "START"

        for ev in root.get("events", []):
            if person_name(ev.get("lineup_off")) == ARDA:
                t = exact_time(ev)
                if t is not None:
                    end = min(t, 90.0)
                    break

        return status, start, end

    if listed_sub:
        start = None
        end = 90.0

        for ev in root.get("events", []):
            if person_name(ev.get("lineup")) == ARDA:
                t = exact_time(ev)
                if t is not None:
                    start = min(t, 90.0)
                    break

        if start is None:
            return "DNP", None, None

        for ev in root.get("events", []):
            if person_name(ev.get("lineup_off")) == ARDA:
                t = exact_time(ev)
                if t is not None and t > start:
                    end = min(t, 90.0)
                    break

        return "SUB", start, end

    return "DNP", None, None


def arda_on(goal_time, start, end):
    """
    Determines whether Arda was ON for a classifier goal.

    Classifier stores added-time goals as Minute=90.
    Therefore a 90th-minute goal belongs ON if Arda's interval
    runs through the end of regulation (end == 90).
    """
    if start is None or end is None:
        return False

    if start <= goal_time < end:
        return True

    # Critical added-time boundary fix:
    if goal_time == 90 and end == 90:
        return True

    return False


# ============================================================
# 1. BUILD ARDA MINUTE INTERVALS
# ============================================================

files = sorted(RAW_DIR.glob("*.json"))

intervals = {}
audit = []

for path in files:
    key = path.stem

    status, start, end = find_arda_interval(path)

    if status == "DNP":
        minutes = 0.0
    else:
        minutes = end - start
        intervals[key] = (start, end)

    audit.append({
        "Match": key,
        "Status": status,
        "Start": start,
        "End": end,
        "Minutes": minutes
    })

audit = pd.DataFrame(audit)

arda_on_minutes = audit["Minutes"].sum()
arda_off_minutes = TOTAL_MINUTES - arda_on_minutes


# ============================================================
# 2. LOAD OPEN-PLAY GOALS
# ============================================================

df = pd.read_csv(EVENT_FILE)

op_goals = df[
    df["Play_Type"].astype(str).str.upper().eq("OPEN_PLAY")
    &
    df["Event"].astype(str).str.upper().isin(["GOAL", "OWN_GOAL"])
].copy()

# Normalize filename -> match key
op_goals["Match_Key"] = (
    op_goals["Match_File"]
    .astype(str)
    .str.replace(".json", "", regex=False)
)

op_goals["Goal_Time"] = pd.to_numeric(
    op_goals["Minute"],
    errors="coerce"
)


# ============================================================
# 3. IDENTIFY BENEFICIARY OF EACH GOAL
# ============================================================

def goal_for_team(row):
    event = str(row["Event"]).upper()
    team = str(row["Team"])

    if event == "GOAL":
        return team

    if event == "OWN_GOAL":
        # Team column = team of player who scored own goal.
        # Therefore beneficiary is the OTHER team.
        if team == "Real Madrid":
            return "OPPONENT"
        else:
            return "Real Madrid"

    return None


op_goals["Goal_For"] = op_goals.apply(goal_for_team, axis=1)


# ============================================================
# 4. CLASSIFY EVERY OP GOAL AS ARDA ON/OFF
# ============================================================

rows = []

for _, r in op_goals.iterrows():

    match = r["Match_Key"]
    goal_time = float(r["Goal_Time"])

    if match in intervals:
        start, end = intervals[match]
        is_on = arda_on(goal_time, start, end)
    else:
        is_on = False

    beneficiary = r["Goal_For"]

    if beneficiary == "Real Madrid":
        kind = "GF"
    else:
        kind = "GA"

    rows.append({
        "Match": match,
        "Minute": r["Minute"],
        "Event": r["Event"],
        "Player": r["Player"],
        "Team": r["Team"],
        "Goal_For": beneficiary,
        "GF_GA": kind,
        "Arda_State": "ON" if is_on else "OFF",
        "Description": r["Description"]
    })

goal_audit = pd.DataFrame(rows)


# ============================================================
# 5. COUNT GF / GA
# ============================================================

gf_on = len(
    goal_audit[
        (goal_audit["GF_GA"] == "GF") &
        (goal_audit["Arda_State"] == "ON")
    ]
)

gf_off = len(
    goal_audit[
        (goal_audit["GF_GA"] == "GF") &
        (goal_audit["Arda_State"] == "OFF")
    ]
)

ga_on = len(
    goal_audit[
        (goal_audit["GF_GA"] == "GA") &
        (goal_audit["Arda_State"] == "ON")
    ]
)

ga_off = len(
    goal_audit[
        (goal_audit["GF_GA"] == "GA") &
        (goal_audit["Arda_State"] == "OFF")
    ]
)


# ============================================================
# 6. RATES
# ============================================================

gf90_on = gf_on / arda_on_minutes * 90
gf90_off = gf_off / arda_off_minutes * 90

ga90_on = ga_on / arda_on_minutes * 90
ga90_off = ga_off / arda_off_minutes * 90

gd90_on = gf90_on - ga90_on
gd90_off = gf90_off - ga90_off


# ============================================================
# 7. PRINT EVERYTHING
# ============================================================

print("\n" + "=" * 90)
print("ARDA MINUTE AUDIT")
print("=" * 90)

print(
    audit.to_string(
        index=False,
        formatters={
            "Start": lambda x: "" if pd.isna(x) else f"{x:.2f}",
            "End": lambda x: "" if pd.isna(x) else f"{x:.2f}",
            "Minutes": lambda x: f"{x:.2f}"
        }
    )
)


print("\n" + "=" * 90)
print("OPEN-PLAY GOAL AUDIT")
print("=" * 90)

print(
    goal_audit[
        [
            "Match",
            "Minute",
            "Player",
            "Team",
            "Goal_For",
            "GF_GA",
            "Arda_State"
        ]
    ].to_string(index=False)
)


print("\n" + "=" * 90)
print("FINAL ARDA OPEN-PLAY ON/OFF")
print("=" * 90)

result = pd.DataFrame([
    {
        "State": "Arda ON",
        "Minutes": arda_on_minutes,
        "OP_GF": gf_on,
        "OP_GF90": gf90_on,
        "OP_GA": ga_on,
        "OP_GA90": ga90_on,
        "OP_GD90": gd90_on
    },
    {
        "State": "Arda OFF",
        "Minutes": arda_off_minutes,
        "OP_GF": gf_off,
        "OP_GF90": gf90_off,
        "OP_GA": ga_off,
        "OP_GA90": ga90_off,
        "OP_GD90": gd90_off
    }
])

print(
    result.round({
        "Minutes": 1,
        "OP_GF90": 2,
        "OP_GA90": 2,
        "OP_GD90": 2
    }).to_string(index=False)
)


print("\nON - OFF:")
print(f"GF/90 difference: {gf90_on - gf90_off:+.2f}")
print(f"GA/90 difference: {ga90_on - ga90_off:+.2f}")
print(f"GD/90 difference: {gd90_on - gd90_off:+.2f}")


print("\nVALIDATION:")
print(f"ON + OFF minutes = {arda_on_minutes + arda_off_minutes:.2f}")
print(f"Total OP GF = {gf_on + gf_off}")
print(f"Total OP GA = {ga_on + ga_off}")

print("\nMinute-90 ON goals:")
print(
    goal_audit[
        (goal_audit["Minute"] == 90) &
        (goal_audit["Arda_State"] == "ON")
    ][
        ["Match", "Player", "GF_GA", "Arda_State"]
    ].to_string(index=False)
)


# ============================================================
# 8. SAVE
# ============================================================

result.to_csv(
    "data/processed/laliga_2026_27_arda_op_GF_GA_on_off_AUDITED.csv",
    index=False
)

goal_audit.to_csv(
    "data/processed/laliga_2026_27_arda_op_goal_audit.csv",
    index=False
)

print("\nSaved:")
print("data/processed/laliga_2026_27_arda_op_GF_GA_on_off_AUDITED.csv")
print("data/processed/laliga_2026_27_arda_op_goal_audit.csv")
