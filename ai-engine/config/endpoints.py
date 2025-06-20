# endpoints.py
# Tất cả endpoint cần thiết cho schema
API_ENDPOINTS = {
    # Leagues (Bảng Leagues)
    "LEAGUES": "leagues",
    
    # Teams và Stadiums (Bảng Teams và Stadiums)
    "TEAMS": "teams",
    "TEAMS_STATISTICS": "teams/statistics",
    "TEAMS_SEASONS": "teams/seasons",
    "VENUES": "venues",
    
    # Seasons (Bảng Seasons)
    "LEAGUES_SEASONS": "leagues/seasons",
    
    # Players (Bảng Players)
    "PLAYERS": "players",
    "PLAYERS_SEASONS": "players/seasons",
    "PLAYERS_SQUADS": "players/squads",
    "PLAYERS_TOPSCORERS": "players/topscorers",
    "PLAYERS_TOPASSISTS": "players/topassists",
    "PLAYERS_TOPYELLOWCARDS": "players/topyellowcards",
    "PLAYERS_TOPREDCARDS": "players/topredcards",
    
    # Referees (Bảng Referees)
    "REFEREES": "coachs",  # API sử dụng endpoint 'coachs' cho trọng tài
    
    # Matches (Bảng Matches)
    "FIXTURES": "fixtures",
    "FIXTURES_ROUNDS": "fixtures/rounds",
    "FIXTURES_HEADTOHEAD": "fixtures/headtohead",
    "FIXTURES_STATISTICS": "fixtures/statistics",
    "FIXTURES_EVENTS": "fixtures/events",
    "FIXTURES_LINEUPS": "fixtures/lineups",
    "FIXTURES_PLAYERS": "fixtures/players",
    
    # Standings (Bảng Standings)
    "STANDINGS": "standings",
    
    # Injuries (Bảng SquadAvailability)
    "INJURIES": "injuries",
    
    # Predictions (Dùng cho phân tích)
    "PREDICTIONS": "predictions",
    
    # Odds (Bảng BettingOdds)
    "ODDS": "odds",
    "ODDS_BOOKMAKERS": "odds/bookmakers",
    "ODDS_BETS": "odds/bets",
    
    # Timezones (Cho Stadiums)
    "TIMEZONES": "timezone",
    
    # Countries (Cho Leagues, Teams)
    "COUNTRIES": "countries",
    
    # Trophies và Sidelined
    "TROPHIES": "trophies",
    "SIDELINED": "sidelined",

}

# Mapping vị trí cầu thủ từ API sang schema
POSITION_MAPPING = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfielder": "MID",
    "Attacker": "FWD",
    "Center Back": "CB",
    "Left Back": "LB",
    "Right Back": "RB",
    "Defensive Midfield": "DM",
    "Central Midfield": "CM",
    "Attacking Midfield": "AM",
    "Left Midfield": "LM",
    "Right Midfield": "RM",
    "Left Wing": "LW",
    "Right Wing": "RW",
    "Center Forward": "CF",
    "Second Striker": "SS"
}

# Mapping trạng thái trận đấu (Matches.status)
STATUS_MAPPING = {
    "NS": "SCHEDULED",     # Not Started
    "1H": "IN_PROGRESS",   # First Half
    "2H": "IN_PROGRESS",   # Second Half
    "HT": "IN_PROGRESS",   # Halftime
    "ET": "IN_PROGRESS",   # Extra Time
    "P": "IN_PROGRESS",    # Penalty In Progress
    "FT": "FINISHED",      # Match Finished
    "AET": "FINISHED",     # After Extra Time
    "PEN": "FINISHED",     # Penalties Finished
    "BT": "IN_PROGRESS",   # Break Time
    "SUSP": "POSTPONED",   # Match Suspended
    "INT": "POSTPONED",    # Match Interrupted
    "PST": "POSTPONED",    # Match Postponed
    "CANC": "CANCELLED",   # Match Cancelled
    "ABD": "CANCELLED",    # Match Abandoned
    "AWD": "FINISHED",     # Technical Loss
    "WO": "FINISHED"       # WalkOver
}

# Mapping loại sự kiện (MatchEvents.event_type)
EVENT_TYPE_MAPPING = {
    "Goal": "goal",
    "Own Goal": "own goal",
    "Penalty": "penalty",
    "Missed Penalty": "missed penalty",
    "Yellow Card": "yellow card",
    "Red Card": "red card",
    "Second Yellow card": "red card",  # 2 thẻ vàng = thẻ đỏ
    "Substitution": "substitution",
    "Var": "foul",          # VAR decision
    "Foul": "foul",
    "Corner": "corner",
    "Offside": "offside",
    "Hand ball": "foul",
    "Free Kick": "foul",
    "Injury": "foul"
}

# Mapping giai đoạn trận đấu (MatchEvents.period)
PERIOD_MAPPING = {
    "1H": "1H",
    "2H": "2H",
    "ET": "ET1",  # Extra Time First Half
    "P": "PEN",   # Penalties
    "BT": "HT"    # Break Time (xử lý như Halftime)
}

# Mapping tình trạng cầu thủ (SquadAvailability.status)
PLAYER_STATUS_MAPPING = {
    "Missing Fixture": "Injured",
    "Questionable": "Doubtful",
    "Suspended": "Suspended",
    "Not Available": "Away on Intl Duty"
}

# Mapping kết quả trận đấu (Matches.outcome)
OUTCOME_MAPPING = {
    "Home": "H",
    "Draw": "D",
    "Away": "A"
}

# Mapping vị trí địa lý (TeamSeasonLocationStats.location)
LOCATION_MAPPING = {
    "home": "Home",
    "away": "Away",
    "total": "Overall"
}

# Mapping cho thống kê thẻ (RefereeStats)
CARD_MAPPING = {
    "yellow": "avg_yellow_cards_per_match",
    "red": "avg_red_cards_per_match"
}

# Mapping cho dữ liệu bookmaker (BettingOdds)
BOOKMAKER_MAPPING = {
    1: "Bet365",
    2: "William Hill",
    3: "Ladbrokes",
    4: "Pinnacle",
    5: "Unibet",
    6: "Betfair",
    8: "888sport",
    9: "10Bet",
    10: "Betway",
    11: "Marathon Bet",
    12: "1xBet",
    13: "Bwin",
    14: "Interwetten",
    15: "Tipico"
}

# API field to database column mapping
FIELD_MAPPING = {
    # Leagues
    "league.id": "id",
    "league.name": "name",
    "league.country": "country",
    "league.logo": "logo_url",
    
    # Teams
    "team.id": "id",
    "team.name": "name",
    "team.code": "short_name",
    "team.founded": "established_year",
    
    # Stadiums
    "venue.id": "id",
    "venue.name": "name",
    "venue.city": "city",
    "venue.capacity": "capacity",
    
    # Players
    "player.id": "id",
    "player.name": "name",
    "player.age": "date_of_birth",  # Chuyển đổi sau
    "player.height": "height",
    "player.nationality": "nationality",
    
    # Matches
    "fixture.id": "id",
    "fixture.date": "match_datetime",
    "fixture.referee": "referee_id",  # Cần mapping tên -> ID
    "teams.home.id": "home_team_id",
    "teams.away.id": "away_team_id",
    "goals.home": "home_goals",
    "goals.away": "away_goals",
    "score.halftime.home": "half_time_home_goals",
    "score.halftime.away": "half_time_away_goals",
    
    # Player stats
    "games.minutes": "minutes_played",
    "goals.total": "goals",
    "goals.assists": "assists",
    "shots.total": "shots",
    "shots.on": "shots_on_target",
    "passes.total": "passes",
    "passes.accuracy": "accurate_passes",  # Chuyển đổi %
    "tackles.total": "tackles",
    "duels.won": "interceptions",  # Tạm ánh xạ
    "fouls.committed": "fouls_committed",
    "cards.yellow": "yellow_cards",
    "cards.red": "red_cards",
    "saves": "saves"
}

# Danh sách các trường cần chuyển đổi đặc biệt
SPECIAL_CONVERSIONS = {
    "player.age": lambda age: datetime.now().year - int(age),
    "passes.accuracy": lambda pct: int(pct.replace('%', '')) / 100
}

# Các endpoint cần phân trang
PAGINATED_ENDPOINTS = [
    "players",
    "fixtures",
    "teams",
    "transfers",
    "injuries"
]

# Timezone mặc định cho dữ liệu
DEFAULT_TIMEZONE = "UTC"

# Giá trị mặc định cho các trường
DEFAULT_VALUES = {
    "height": 180,  # cm
    "capacity": 10000,
    "minutes_played": 90
}