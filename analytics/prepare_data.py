"""
MVP 1 Phase 1 — Dataset Preparation
Reads the raw Kaggle dataset, cleans and validates it against DATA_SCHEMA.md v0.2,
and writes the final MVP 1 dataset to data/processed/cleaned_players.csv.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "players_data_raw_2025_26.csv"
OUTPUT_FILE = ROOT / "data" / "processed" / "cleaned_players.csv"

# ── Constants ─────────────────────────────────────────────────────────────────

SEASON = "2025-26"
MIN_MINUTES = 90
VALID_POSITIONS = {"GK", "DF", "MF", "FW"}

# ── Column selection: raw name → schema name ──────────────────────────────────

COLUMN_MAP: dict[str, str] = {
    "Player": "player_name",
    "Nation": "nationality",
    "Pos": "position",
    "Squad": "club",
    "Comp": "competition",
    "Age": "age",
    "MP": "appearances",
    "Min": "minutes_played",
    "Gls": "goals",
    "Ast": "assists",
    "G-PK": "non_penalty_goals",
}

FINAL_COLUMNS = [
    "player_name",
    "season",
    "nationality",
    "position",
    "club",
    "competition",
    "age",
    "appearances",
    "minutes_played",
    "goals",
    "assists",
    "non_penalty_goals",
]

# ── Nationality: FBref 3-letter code → full country name ──────────────────────

NATIONALITY_MAP: dict[str, str] = {
    "AFG": "Afghanistan",
    "ALB": "Albania",
    "ALG": "Algeria",
    "AND": "Andorra",
    "ANG": "Angola",
    "ARG": "Argentina",
    "ARM": "Armenia",
    "AUS": "Australia",
    "AUT": "Austria",
    "AZE": "Azerbaijan",
    "BEL": "Belgium",
    "BEN": "Benin",
    "BFA": "Burkina Faso",
    "BIH": "Bosnia and Herzegovina",
    "BLR": "Belarus",
    "BOL": "Bolivia",
    "BRA": "Brazil",
    "BUL": "Bulgaria",
    "CAN": "Canada",
    "CGO": "Republic of Congo",
    "CHI": "Chile",
    "CHN": "China",
    "CIV": "Ivory Coast",
    "CMR": "Cameroon",
    "COD": "DR Congo",
    "COL": "Colombia",
    "CRC": "Costa Rica",
    "CRO": "Croatia",
    "CYP": "Cyprus",
    "CZE": "Czech Republic",
    "DEN": "Denmark",
    "ECU": "Ecuador",
    "EGY": "Egypt",
    "ENG": "England",
    "EQG": "Equatorial Guinea",
    "ESP": "Spain",
    "EST": "Estonia",
    "ETH": "Ethiopia",
    "FIN": "Finland",
    "FRA": "France",
    "GAB": "Gabon",
    "GEO": "Georgia",
    "GER": "Germany",
    "GHA": "Ghana",
    "GNB": "Guinea-Bissau",
    "GRE": "Greece",
    "GUI": "Guinea",
    "HON": "Honduras",
    "HUN": "Hungary",
    "IDN": "Indonesia",
    "IRL": "Republic of Ireland",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "ISL": "Iceland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JAM": "Jamaica",
    "JPN": "Japan",
    "KAZ": "Kazakhstan",
    "KEN": "Kenya",
    "KOR": "South Korea",
    "KOS": "Kosovo",
    "LAT": "Latvia",
    "LBR": "Liberia",
    "LIT": "Lithuania",
    "LUX": "Luxembourg",
    "MAD": "Madagascar",
    "MAR": "Morocco",
    "MDA": "Moldova",
    "MEX": "Mexico",
    "MKD": "North Macedonia",
    "MLI": "Mali",
    "MLT": "Malta",
    "MNE": "Montenegro",
    "MOZ": "Mozambique",
    "MTN": "Mauritania",
    "NAM": "Namibia",
    "NED": "Netherlands",
    "NGA": "Nigeria",
    "NIR": "Northern Ireland",
    "NOR": "Norway",
    "NZL": "New Zealand",
    "PAN": "Panama",
    "PAR": "Paraguay",
    "PER": "Peru",
    "PHI": "Philippines",
    "POL": "Poland",
    "POR": "Portugal",
    "ROU": "Romania",
    "RSA": "South Africa",
    "RUS": "Russia",
    "SCO": "Scotland",
    "SEN": "Senegal",
    "SLE": "Sierra Leone",
    "SLO": "Slovenia",
    "SRB": "Serbia",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
    "SWE": "Sweden",
    "SYR": "Syria",
    "TOG": "Togo",
    "TRI": "Trinidad and Tobago",
    "TUN": "Tunisia",
    "TUR": "Turkey",
    "UKR": "Ukraine",
    "URU": "Uruguay",
    "USA": "United States",
    "VEN": "Venezuela",
    "WAL": "Wales",
    "ZAM": "Zambia",
    "ZIM": "Zimbabwe",
}

# ── Competition: raw value → full league name ─────────────────────────────────

COMPETITION_MAP: dict[str, str] = {
    "eng Premier League": "Premier League",
    "es La Liga": "La Liga",
    "de Bundesliga": "Bundesliga",
    "it Serie A": "Serie A",
    "fr Ligue 1": "Ligue 1",
}


# ── Normalisation helpers ─────────────────────────────────────────────────────


def normalise_nationality(raw: str | None) -> str:
    if pd.isna(raw) or not str(raw).strip():
        return "Unknown"
    parts = str(raw).strip().split()
    # raw format: "{2-letter flag} {3-letter code}" e.g. "us USA"
    code = parts[1].upper() if len(parts) >= 2 else parts[0].upper()
    return NATIONALITY_MAP.get(code, "Unknown")


def normalise_position(raw: str | None) -> str | None:
    if pd.isna(raw) or not str(raw).strip():
        return None
    first = str(raw).split(",")[0].strip()
    return first if first in VALID_POSITIONS else None


def normalise_competition(raw: str | None) -> str:
    if pd.isna(raw):
        return "Unknown"
    raw_str = str(raw).strip()
    if raw_str in COMPETITION_MAP:
        return COMPETITION_MAP[raw_str]
    # fallback: strip the country prefix (first word)
    parts = raw_str.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else raw_str


# ── Pipeline steps ────────────────────────────────────────────────────────────


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_raw(path: Path) -> pd.DataFrame:
    logging.info(f"Loading: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")
    # dtype=str prevents pandas from guessing types before we clean them
    df = pd.read_csv(path, dtype=str)
    logging.info(f"Raw shape:  {len(df)} rows × {len(df.columns)} columns")
    return df


def select_and_rename(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in COLUMN_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing from raw file: {missing}")
    df = df[list(COLUMN_MAP.keys())].copy()
    df = df.rename(columns=COLUMN_MAP)
    logging.info(f"Selected {len(df.columns)} columns")
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df["season"] = SEASON
    df["nationality"] = df["nationality"].apply(normalise_nationality)
    df["position"] = df["position"].apply(normalise_position)
    df["competition"] = df["competition"].apply(normalise_competition)

    df["age"] = pd.to_numeric(df["age"], errors="coerce").astype("Int64")

    # Int64 (capital I) is the nullable integer dtype — handles NaN without promoting to float
    counting_cols = ["appearances", "minutes_played", "goals", "assists", "non_penalty_goals"]
    for col in counting_cols:
        df[col] = (
            df[col]
            .str.replace(",", "", regex=False)  # strip thousands separators if present
            .pipe(pd.to_numeric, errors="coerce")
            .astype("Int64")
        )

    return df


def validate(df: pd.DataFrame) -> pd.DataFrame:
    initial = len(df)

    def drop(mask: pd.Series, reason: str) -> pd.DataFrame:
        n = (~mask).sum()
        if n:
            logging.warning(f"Removing {n} rows — {reason}")
        return df[mask].copy()

    df = drop(
        df["player_name"].notna() & (df["player_name"].str.strip() != ""),
        "missing player_name",
    )
    df = drop(
        df["club"].notna() & (df["club"].str.strip() != ""),
        "missing club",
    )
    df = drop(
        df["position"].notna() & df["position"].isin(VALID_POSITIONS),
        "invalid or missing position",
    )
    df = drop(df["age"].notna(), "missing age")
    df = drop(
        df["minutes_played"].notna() & (df["minutes_played"] >= MIN_MINUTES),
        f"fewer than {MIN_MINUTES} minutes played",
    )

    # Flag anomalies — retain rows but log for awareness
    age_out = df["age"].notna() & ((df["age"] < 15) | (df["age"] > 45))
    if age_out.sum():
        logging.warning(
            f"Flagged {age_out.sum()} rows with age outside 15–45: "
            f"{df.loc[age_out, 'player_name'].tolist()}"
        )

    bad_min = (
        df["minutes_played"].notna()
        & df["appearances"].notna()
        & (df["minutes_played"] > df["appearances"] * 95)
    )
    if bad_min.sum():
        logging.warning(
            f"Flagged {bad_min.sum()} rows where minutes_played > appearances × 95"
        )

    bad_npg = (
        df["non_penalty_goals"].notna()
        & df["goals"].notna()
        & (df["non_penalty_goals"] > df["goals"])
    )
    if bad_npg.sum():
        logging.warning(
            f"Flagged {bad_npg.sum()} rows where non_penalty_goals > goals"
        )

    # Fill null counting stats with 0
    for col in ["goals", "assists", "non_penalty_goals"]:
        nulls = int(df[col].isna().sum())
        if nulls:
            logging.warning(f"Filling {nulls} null values in '{col}' with 0")
        df[col] = df[col].fillna(0)

    # Deduplicate: keep highest minutes_played per player_name + club
    before = len(df)
    df = df.sort_values("minutes_played", ascending=False)
    df = df.drop_duplicates(subset=["player_name", "club"], keep="first")
    dupes = before - len(df)
    if dupes:
        logging.warning(f"Removed {dupes} duplicate rows (kept highest minutes_played)")

    logging.info(f"Validation: {initial} → {len(df)} rows retained")
    return df


def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df[FINAL_COLUMNS].to_csv(path, index=False)
    logging.info(f"Saved: {path}")
    logging.info(f"Final shape: {len(df)} rows × {len(FINAL_COLUMNS)} columns")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    setup_logging()
    logging.info("=== MVP 1 Phase 1 — Dataset Preparation ===")
    try:
        df = load_raw(RAW_FILE)
        df = select_and_rename(df)
        df = transform(df)
        df = validate(df)
        save(df, OUTPUT_FILE)
        logging.info("=== Done ===")
    except (FileNotFoundError, ValueError) as e:
        logging.error(str(e))
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
