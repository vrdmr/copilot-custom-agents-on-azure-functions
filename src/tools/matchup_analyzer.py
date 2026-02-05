from pydantic import BaseModel, Field


class MatchupParams(BaseModel):
    team1: str = Field(description="First NFL team name (e.g., 'Kansas City Chiefs')")
    team2: str = Field(description="Second NFL team name (e.g., 'Philadelphia Eagles')")


async def matchup_analyzer(params: MatchupParams) -> str:
    """Compare two NFL teams head-to-head across key categories.
    Returns a structured breakdown of offensive, defensive, and special teams matchups."""

    # Team stat profiles (2024-25 season representative data)
    team_profiles = {
        "chiefs": {
            "full_name": "Kansas City Chiefs",
            "offense_rank": 7, "defense_rank": 8,
            "ppg": 25.4, "ppg_allowed": 19.2,
            "rush_ypg": 118.5, "pass_ypg": 245.3,
            "turnover_diff": "+9",
            "third_down_pct": "43.2%",
            "red_zone_pct": "61.5%",
            "strengths": ["QB play (Mahomes)", "Playoff experience", "Coaching", "Late-game execution"],
            "weaknesses": ["WR depth", "Offensive line consistency"],
        },
        "eagles": {
            "full_name": "Philadelphia Eagles",
            "offense_rank": 3, "defense_rank": 5,
            "ppg": 27.8, "ppg_allowed": 18.6,
            "rush_ypg": 162.3, "pass_ypg": 218.7,
            "turnover_diff": "+12",
            "third_down_pct": "45.1%",
            "red_zone_pct": "65.8%",
            "strengths": ["Dominant run game (Barkley)", "Defensive line", "Turnover creation", "Red zone efficiency"],
            "weaknesses": ["Pass defense vs elite QBs", "Playoff composure"],
        },
        "lions": {
            "full_name": "Detroit Lions",
            "offense_rank": 1, "defense_rank": 15,
            "ppg": 30.1, "ppg_allowed": 22.1,
            "rush_ypg": 145.2, "pass_ypg": 262.8,
            "turnover_diff": "+6",
            "third_down_pct": "47.3%",
            "red_zone_pct": "68.2%",
            "strengths": ["Explosive offense", "Offensive line", "Goff efficiency", "Play-action game"],
            "weaknesses": ["Defensive secondary", "Injury depth"],
        },
        "bills": {
            "full_name": "Buffalo Bills",
            "offense_rank": 2, "defense_rank": 10,
            "ppg": 28.9, "ppg_allowed": 20.5,
            "rush_ypg": 135.1, "pass_ypg": 250.4,
            "turnover_diff": "+7",
            "third_down_pct": "44.8%",
            "red_zone_pct": "63.1%",
            "strengths": ["Josh Allen dual-threat", "Big-play ability", "Home-field advantage"],
            "weaknesses": ["Playoff history", "Defensive consistency"],
        },
        "49ers": {
            "full_name": "San Francisco 49ers",
            "offense_rank": 5, "defense_rank": 3,
            "ppg": 26.5, "ppg_allowed": 17.8,
            "rush_ypg": 140.7, "pass_ypg": 230.1,
            "turnover_diff": "+8",
            "third_down_pct": "42.9%",
            "red_zone_pct": "59.4%",
            "strengths": ["Scheme versatility", "Defensive front", "Run game", "Coaching"],
            "weaknesses": ["QB durability", "Super Bowl heartbreak"],
        },
        "ravens": {
            "full_name": "Baltimore Ravens",
            "offense_rank": 4, "defense_rank": 6,
            "ppg": 27.1, "ppg_allowed": 19.0,
            "rush_ypg": 175.6, "pass_ypg": 198.4,
            "turnover_diff": "+5",
            "third_down_pct": "41.8%",
            "red_zone_pct": "62.3%",
            "strengths": ["Lamar Jackson running", "Ground game dominance", "Defense"],
            "weaknesses": ["Passing in playoffs", "WR corps"],
        },
    }

    def normalize(name: str) -> str:
        name = name.lower().strip()
        for key in team_profiles:
            if key in name or team_profiles[key]["full_name"].lower() in name:
                return key
        return name

    key1 = normalize(params.team1)
    key2 = normalize(params.team2)

    if key1 not in team_profiles:
        return f"❌ Don't have detailed stats for '{params.team1}'. Available: {', '.join(p['full_name'] for p in team_profiles.values())}"
    if key2 not in team_profiles:
        return f"❌ Don't have detailed stats for '{params.team2}'. Available: {', '.join(p['full_name'] for p in team_profiles.values())}"

    t1 = team_profiles[key1]
    t2 = team_profiles[key2]

    analysis = f"""🏈 HEAD-TO-HEAD MATCHUP: {t1['full_name']} vs {t2['full_name']}
{'='*60}

📊 OFFENSE
  {t1['full_name']}: #{t1['offense_rank']} overall | {t1['ppg']} PPG | {t1['rush_ypg']} rush YPG | {t1['pass_ypg']} pass YPG
  {t2['full_name']}: #{t2['offense_rank']} overall | {t2['ppg']} PPG | {t2['rush_ypg']} rush YPG | {t2['pass_ypg']} pass YPG
  Edge: {'🔴 ' + t1['full_name'] if t1['offense_rank'] < t2['offense_rank'] else '🟢 ' + t2['full_name']}

🛡️ DEFENSE
  {t1['full_name']}: #{t1['defense_rank']} overall | {t1['ppg_allowed']} PPG allowed
  {t2['full_name']}: #{t2['defense_rank']} overall | {t2['ppg_allowed']} PPG allowed
  Edge: {'🔴 ' + t1['full_name'] if t1['defense_rank'] < t2['defense_rank'] else '🟢 ' + t2['full_name']}

🔑 KEY STATS
  Turnover Diff: {t1['full_name']} {t1['turnover_diff']} | {t2['full_name']} {t2['turnover_diff']}
  3rd Down: {t1['full_name']} {t1['third_down_pct']} | {t2['full_name']} {t2['third_down_pct']}
  Red Zone: {t1['full_name']} {t1['red_zone_pct']} | {t2['full_name']} {t2['red_zone_pct']}

💪 STRENGTHS
  {t1['full_name']}: {', '.join(t1['strengths'])}
  {t2['full_name']}: {', '.join(t2['strengths'])}

⚠️ WEAKNESSES
  {t1['full_name']}: {', '.join(t1['weaknesses'])}
  {t2['full_name']}: {', '.join(t2['weaknesses'])}"""

    return analysis
