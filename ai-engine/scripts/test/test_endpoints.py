# ai-engine\scripts\test\test_endpoints.py

import requests
import json
import time
from typing import Dict, List

BASE_URL = "https://api.sofascore.com/api/v1"

def fetch_match_info(match_id: int):
    url = f"{BASE_URL}/event/{match_id}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    event = data["event"]

    return {
        "match_id": match_id,
        "tournament_id": event["tournament"]["id"],
        "season_id": event["season"]["id"],
        "home_team_id": event["homeTeam"]["id"],
        "away_team_id": event["awayTeam"]["id"]
    }

def fetch_sample_player_id(team_id: int) -> int:
    url = f"{BASE_URL}/team/{team_id}/players"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data["players"][0]["player"]["id"]

def test_endpoint(url: str, params: Dict = None) -> Dict:
    try:
        response = requests.get(url, params=params)
        return {
            "url": url if not params else f"{url}?{requests.compat.urlencode(params)}",
            "status_code": response.status_code,
            "success": response.ok,
            "response_time": response.elapsed.total_seconds(),
            "size": len(response.content)
        }
    except Exception as e:
        return {
            "url": url,
            "status_code": None,
            "success": False,
            "response_time": None,
            "size": None,
            "error": str(e)
        }

def main():
    print("Starting Endpoint Validation...\n")
    
    match_id = 12436536
    ids = fetch_match_info(match_id)
    player_id = fetch_sample_player_id(ids["home_team_id"])

    # Danh sách endpoint và param nếu có
    endpoints = [
        # === Core Match Endpoints ===
        (f"/event/{ids['match_id']}", None),
        (f"/event/{ids['match_id']}/lineups", None),
        (f"/event/{ids['match_id']}/statistics", None),
        (f"/event/{ids['match_id']}/incidents", None),
        (f"/event/{ids['match_id']}/h2h/events", None),
        (f"/event/{ids['match_id']}/graph", None),
        (f"/event/{ids['match_id']}/momentum", None),
        (f"/event/{ids['match_id']}/heatmap/{ids['home_team_id']}", None),
        (f"/event/{ids['match_id']}/shotmap", None),

        # === Tournament/Season Endpoints ===
        (f"/unique-tournament/{ids['tournament_id']}", None),
        (f"/unique-tournament/{ids['tournament_id']}/seasons", None),
        (f"/unique-tournament/{ids['tournament_id']}/categories", None),
        (f"/unique-tournament/{ids['tournament_id']}/media", None),

        # === Season-specific Endpoints ===
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/standings/total", None),
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/events/last/0", None),
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/events/next/0", None),
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/events/round/1", None),
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/top-players/goals", None),
        (f"/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/statistics", None),

        # === Team Endpoints ===
        (f"/team/{ids['home_team_id']}", None),
        (f"/team/{ids['home_team_id']}/details", None),
        (f"/team/{ids['home_team_id']}/players", None),
        (f"/team/{ids['home_team_id']}/events/last/0", None),
        (f"/team/{ids['home_team_id']}/events/next/0", None),
        (f"/team/{ids['home_team_id']}/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/statistics/overall", None),
        (f"/team/{ids['home_team_id']}/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/statistics/breakdown", None),
        (f"/team/{ids['home_team_id']}/transfers", None),
        (f"/team/{ids['home_team_id']}/media", None),

        # === Player Endpoints ===
        (f"/player/{player_id}", None),
        (f"/player/{player_id}/details", None),
        (f"/player/{player_id}/unique-tournament/{ids['tournament_id']}/season/{ids['season_id']}/statistics/overall", None),
        (f"/player/{player_id}/statistics/seasons", None),
        (f"/player/{player_id}/characteristics", None),
        (f"/player/{player_id}/transfers", None),
        (f"/player/{player_id}/media", None),
        (f"/player/{player_id}/events/last/0", None),

        # === Live Endpoints ===
        (f"/sport/1/events/live", None),
        (f"/event/{ids['match_id']}/tracker", None),

        # === Search ===
        (f"/search/all", {"term": "manchester"}),
        (f"/search/manchester", None),

        # === General ===
        (f"/sport/1/categories", None),
        (f"/sports", None)
    ]

    results = []
    for ep, params in endpoints:
        full_url = BASE_URL + ep
        print(f"Testing: {ep}")
        res = test_endpoint(full_url, params=params)
        results.append(res)

        status = "PASS" if res["success"] else "❌ FAIL"
        print(f"  {status} - Status: {res['status_code']} - Time: {res.get('response_time', 'NA')}s\n")
        time.sleep(0.3)

    print("\nValidation Report:\n")
    print(f"Total endpoints: {len(results)}")
    print(f"Passed: {sum(r['success'] for r in results)}")
    print(f"Failed: {sum(not r['success'] for r in results)}")

    with open("api_validation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to 'api_validation_results.json'")

if __name__ == "__main__":
    main()
