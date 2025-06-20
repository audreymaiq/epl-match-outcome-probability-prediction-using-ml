# utils/enum_mapping.py

MATCH_STATUS_MAPPING = {
    "TBD": "SCHEDULED",
    "NS": "SCHEDULED",
    "1H": "IN_PROGRESS",
    "HT": "IN_PROGRESS",
    "2H": "IN_PROGRESS",
    "ET": "IN_PROGRESS",
    "P": "IN_PROGRESS",
    "BT": "IN_PROGRESS",
    "FT": "FINISHED",
    "AET": "FINISHED",
    "PEN": "FINISHED",
    "SUSP": "POSTPONED",
    "PST": "POSTPONED",
    "CANC": "CANCELLED",
    "ABD": "CANCELLED"
}

MATCH_EVENT_TYPE_MAPPING = {
    "Goal": "goal",
    "Card": "yellow card",
    "Red card": "red card",
    "subst": "substitution",
    "Foul": "foul",
    "Corner": "corner",
    "Offside": "offside",
    "Penalty awarded": "penalty",
    "Penalty missed": "missed penalty",
    "Own goal": "own goal"
}

PLAYER_STATUS_MAPPING = {
    "doubtful": "Doubtful",
    "injured": "Injured",
    "suspended": "Suspended",
    "not available": "Away on Intl Duty",
    "available": "Available"
}