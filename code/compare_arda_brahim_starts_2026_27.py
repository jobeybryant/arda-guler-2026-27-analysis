import json
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw/laliga_2026_27/matches")

ARDA = "Arda Güler"
BRAHIM = "Brahim Díaz"


def person_name(obj):
    if not isinstance(obj, dict):
        return ""
    return obj.get("person", {}).get("name", "")


def get_root(path):
    d = json.loads(path.read_text())
    return d["props"]["pageProps"]


def starters_from_match(path):
    root = get_root(path)
    starters = []

    lineups = root["data"]["lineups"]

    for side in ["home", "away"]:
        for x in lineups.get(side, {}).get("starts", []):
            name = person_name(x)
            if name:
                starters.append(name)

    return starters


# ============================================================
# SCAN MATCHES
# ============================================================

rows = []

files = sorted(RAW_DIR.glob("*.json"))

print(f"\nFound {len(files)} La Liga match files.\n")

for path in files:

    starters = starters_from_match(path)

    arda_start = ARDA in starters
    brahim_start = BRAHIM in starters

    if arda_start and brahim_start:
        group = "BOTH START"

    elif arda_start:
        group = "ARDA START"

    elif brahim_start:
        group = "BRAHIM START"

    else:
        group = "NEITHER START"

    rows.append({
        "Match": path.stem,
        "Arda_Start": arda_start,
        "Brahim_Start": brahim_start,
        "Group": group
    })


df = pd.DataFrame(rows)


# ============================================================
# PRINT FULL MATCH AUDIT
# ============================================================

print("=" * 100)
print("2026-27 LA LIGA — ARDA vs BRAHIM START AUDIT")
print("=" * 100)

print(df.to_string(index=False))


# ============================================================
# PRINT EACH GROUP
# ============================================================

for group in [
    "ARDA START",
    "BRAHIM START",
    "BOTH START",
    "NEITHER START"
]:

    subset = df[df["Group"] == group]

    print("\n" + "=" * 100)
    print(f"{group} — {len(subset)} MATCHES")
    print("=" * 100)

    if len(subset) == 0:
        print("None")
    else:
        for match in subset["Match"]:
            print(match)


# ============================================================
# SAMPLE SIZE SUMMARY
# ============================================================

print("\n" + "=" * 100)
print("SAMPLE SIZE")
print("=" * 100)

summary = (
    df["Group"]
    .value_counts()
    .reindex(
        [
            "ARDA START",
            "BRAHIM START",
            "BOTH START",
            "NEITHER START"
        ],
        fill_value=0
    )
)

print(summary.to_string())


print("\nIndividual start counts:")
print(f"Arda starts:   {df['Arda_Start'].sum()}")
print(f"Brahim starts: {df['Brahim_Start'].sum()}")


# ============================================================
# SAVE
# ============================================================

out = Path(
    "data/processed/laliga_2026_27_arda_brahim_start_audit.csv"
)

df.to_csv(out, index=False)

print(f"\nSaved:\n{out}")
