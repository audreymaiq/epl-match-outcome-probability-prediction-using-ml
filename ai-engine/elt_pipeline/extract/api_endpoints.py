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
    # Referees are extracted from the "referee" field in the /fixtures endpoint.
    
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
    "SIDELINED": "sidelined"

}