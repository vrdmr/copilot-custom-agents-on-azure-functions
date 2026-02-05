import hashlib
from pydantic import BaseModel, Field


class PredictionParams(BaseModel):
    team1: str = Field(description="First NFL team name")
    team2: str = Field(description="Second NFL team name")
    context: str = Field(
        default="regular",
        description="Game context: 'regular', 'playoff', or 'superbowl'"
    )


async def predict_winner(params: PredictionParams) -> str:
    """Make a fun, data-driven prediction for an NFL matchup.
    Uses weighted factors like offense, defense, experience, and momentum."""

    team_ratings = {
        "chiefs": {
            "name": "Kansas City Chiefs",
            "overall": 92, "offense": 87, "defense": 88,
            "coaching": 98, "playoff_exp": 99, "clutch": 97,
            "momentum": 85, "qb_factor": 99,
        },
        "eagles": {
            "name": "Philadelphia Eagles",
            "overall": 91, "offense": 92, "defense": 89,
            "coaching": 88, "playoff_exp": 80, "clutch": 82,
            "momentum": 90, "qb_factor": 85,
        },
        "lions": {
            "name": "Detroit Lions",
            "overall": 89, "offense": 95, "defense": 78,
            "coaching": 90, "playoff_exp": 65, "clutch": 75,
            "momentum": 93, "qb_factor": 86,
        },
        "bills": {
            "name": "Buffalo Bills",
            "overall": 90, "offense": 91, "defense": 83,
            "coaching": 85, "playoff_exp": 75, "clutch": 78,
            "momentum": 88, "qb_factor": 94,
        },
        "49ers": {
            "name": "San Francisco 49ers",
            "overall": 89, "offense": 88, "defense": 91,
            "coaching": 92, "playoff_exp": 85, "clutch": 80,
            "momentum": 82, "qb_factor": 80,
        },
        "ravens": {
            "name": "Baltimore Ravens",
            "overall": 90, "offense": 89, "defense": 87,
            "coaching": 88, "playoff_exp": 72, "clutch": 75,
            "momentum": 86, "qb_factor": 92,
        },
    }

    def normalize(name: str) -> str:
        name = name.lower().strip()
        for key in team_ratings:
            if key in name or team_ratings[key]["name"].lower() in name:
                return key
        return name

    key1 = normalize(params.team1)
    key2 = normalize(params.team2)

    if key1 not in team_ratings:
        return f"❌ No ratings for '{params.team1}'. Available: {', '.join(r['name'] for r in team_ratings.values())}"
    if key2 not in team_ratings:
        return f"❌ No ratings for '{params.team2}'. Available: {', '.join(r['name'] for r in team_ratings.values())}"

    t1 = team_ratings[key1]
    t2 = team_ratings[key2]

    # Weight factors differently based on context
    if params.context == "superbowl":
        weights = {
            "overall": 0.15, "offense": 0.15, "defense": 0.15,
            "coaching": 0.15, "playoff_exp": 0.20, "clutch": 0.10,
            "momentum": 0.05, "qb_factor": 0.05,
        }
    elif params.context == "playoff":
        weights = {
            "overall": 0.15, "offense": 0.15, "defense": 0.15,
            "coaching": 0.15, "playoff_exp": 0.15, "clutch": 0.10,
            "momentum": 0.05, "qb_factor": 0.10,
        }
    else:
        weights = {
            "overall": 0.20, "offense": 0.20, "defense": 0.20,
            "coaching": 0.10, "playoff_exp": 0.05, "clutch": 0.05,
            "momentum": 0.10, "qb_factor": 0.10,
        }

    score1 = sum(t1[k] * w for k, w in weights.items())
    score2 = sum(t2[k] * w for k, w in weights.items())

    diff = abs(score1 - score2)
    winner = t1 if score1 > score2 else t2
    loser = t2 if score1 > score2 else t1

    if diff > 5:
        confidence = "HIGH 🔥"
        verdict = f"{winner['name']} should handle this one"
    elif diff > 2:
        confidence = "MEDIUM 🤔"
        verdict = f"{winner['name']} has the edge, but don't sleep on {loser['name']}"
    else:
        confidence = "COIN FLIP 😬"
        verdict = f"This is anybody's game — buckle up"

    # Generate a deterministic but fun predicted score
    seed = hashlib.md5(f"{key1}{key2}{params.context}".encode()).hexdigest()
    base_score = int(seed[:2], 16) % 14 + 17  # 17-30 range
    margin = max(0, int(diff))
    w_score = base_score + margin
    l_score = base_score

    context_label = {
        "superbowl": "🏆 SUPER BOWL",
        "playoff": "🏈 PLAYOFF",
        "regular": "📺 REGULAR SEASON"
    }.get(params.context, "📺 REGULAR SEASON")

    result = f"""{context_label} PREDICTION: {t1['name']} vs {t2['name']}
{'='*55}

📊 COMPOSITE RATINGS (weighted for {params.context} context):
  {t1['name']}: {score1:.1f}
  {t2['name']}: {score2:.1f}

🔍 FACTOR BREAKDOWN:
  Offense:      {t1['name']} {t1['offense']} | {t2['name']} {t2['offense']}
  Defense:      {t1['name']} {t1['defense']} | {t2['name']} {t2['defense']}
  Coaching:     {t1['name']} {t1['coaching']} | {t2['name']} {t2['coaching']}
  Playoff Exp:  {t1['name']} {t1['playoff_exp']} | {t2['name']} {t2['playoff_exp']}
  Clutch:       {t1['name']} {t1['clutch']} | {t2['name']} {t2['clutch']}
  QB Factor:    {t1['name']} {t1['qb_factor']} | {t2['name']} {t2['qb_factor']}

🎯 PREDICTION:
  Winner: {winner['name']}
  Confidence: {confidence}
  Projected Score: {winner['name']} {w_score} - {loser['name']} {l_score}
  
💬 THE TAKE: {verdict}"""

    return result
