# ai-engine/config/core_constants.py

class MatchStatus:
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"

# Mapping từ giá trị API sang MatchStatus
API_STATUS_MAPPING = {
    "NS": MatchStatus.SCHEDULED,
    "1H": MatchStatus.IN_PROGRESS,
    "2H": MatchStatus.IN_PROGRESS,
    "HT": MatchStatus.IN_PROGRESS,
    "ET": MatchStatus.IN_PROGRESS,
    "P": MatchStatus.IN_PROGRESS,
    "BT": MatchStatus.IN_PROGRESS,
    "FT": MatchStatus.FINISHED,
    "AET": MatchStatus.FINISHED,
    "PEN": MatchStatus.FINISHED,
    "AWD": MatchStatus.FINISHED,
    "WO": MatchStatus.FINISHED,
    "SUSP": MatchStatus.POSTPONED,
    "INT": MatchStatus.POSTPONED,
    "PST": MatchStatus.POSTPONED,
    "CANC": MatchStatus.CANCELLED,
    "ABD": MatchStatus.CANCELLED
}

class PlayerPosition:
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"

# Mapping từ mô tả API sang PlayerPosition
API_POSITION_MAPPING = {
    "Goalkeeper": PlayerPosition.GK,
    "Defender": PlayerPosition.DEF,
    "Midfielder": PlayerPosition.MID,
    "Attacker": PlayerPosition.FWD,
    "Forward": PlayerPosition.FWD
}

class MatchOutcome:
    HOME = "H"
    DRAW = "D"
    AWAY = "A"

API_OUTCOME_MAPPING = {
    "Home": MatchOutcome.HOME,
    "Draw": MatchOutcome.DRAW,
    "Away": MatchOutcome.AWAY
}