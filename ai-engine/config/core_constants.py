# ai-engine/config/core_constants.py

class MatchStatus:
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"

# Mapping từ giá trị API sang MatchStatus
API_STATUS_MAPPING = {
    # Scheduled statuses
    "TBD": MatchStatus.SCHEDULED,   # Time To Be Defined
    "NS": MatchStatus.SCHEDULED,    # Not Started

    # In-Play statuses
    "1H": MatchStatus.IN_PROGRESS,  # First Half
    "2H": MatchStatus.IN_PROGRESS,  # Second Half
    "HT": MatchStatus.IN_PROGRESS,  # Halftime
    "ET": MatchStatus.IN_PROGRESS,  # Extra Time
    "P": MatchStatus.IN_PROGRESS,   # Penalty In Progress
    "BT": MatchStatus.IN_PROGRESS,  # Break Time during extra time
    "LIVE": MatchStatus.IN_PROGRESS,# Live (rare cases)
    "SUSP": MatchStatus.IN_PROGRESS,# Match Suspended (In Play)
    "INT": MatchStatus.IN_PROGRESS, # Match Interrupted (In Play)

    # Finished statuses
    "FT": MatchStatus.FINISHED,     # Match Finished
    "AET": MatchStatus.FINISHED,    # After Extra Time
    "PEN": MatchStatus.FINISHED,    # After Penalty Shootout
    "AWD": MatchStatus.FINISHED,    # Technical Loss / Awarded
    "WO": MatchStatus.FINISHED,     # Walkover

    # Postponed
    "PST": MatchStatus.POSTPONED,   # Postponed

    # Cancelled
    "CANC": MatchStatus.CANCELLED,  # Cancelled

    # Abandoned
    "ABD": MatchStatus.ABANDONED    # Abandoned
}

class PlayerPosition:
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"
    UNKNOWN = "UNKNOWN"

# Mapping từ mô tả API sang PlayerPosition
API_POSITION_MAPPING = {
    "Goalkeeper": PlayerPosition.GK,
    "Defender": PlayerPosition.DEF,
    "Midfielder": PlayerPosition.MID,
    "Attacker": PlayerPosition.FWD
}

class MatchOutcome:
    HOME = "H"
    DRAW = "D"
    AWAY = "A"
    UNKNOWN = "UNKNOWN"

API_OUTCOME_MAPPING = {
    "Home": MatchOutcome.HOME,
    "Draw": MatchOutcome.DRAW,
    "Away": MatchOutcome.AWAY
}

# Thêm hằng số cho tình trạng cầu thủ
class PlayerAvailabilityStatus:
    MISSING = "Missing Fixture"
    QUESTIONABLE = "Questionable"
    UNKNOWN = "Unknown"

# Mapping cho tình trạng cầu thủ từ API
API_PLAYER_AVAILABILITY_MAPPING = {
    "Missing Fixture": PlayerAvailabilityStatus.MISSING,
    "Questionable": PlayerAvailabilityStatus.QUESTIONABLE
}

# Thêm hằng số cho loại kèo
class BetType:
    UNKNOWN = "Unknown"

# Dynamic mapping: use the /odds/bets endpoint to retrieve all available bet IDs and names
BET_TYPE_MAPPING = {}