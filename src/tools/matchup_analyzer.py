from pydantic import BaseModel, Field


class MatchupParams(BaseModel):
    team1_wins: int = Field(description="Number of wins for team 1")
    team1_losses: int = Field(description="Number of losses for team 1")
    team1_ties: int = Field(description="Number of ties for team 1", default=0)
    team2_wins: int = Field(description="Number of wins for team 2")
    team2_losses: int = Field(description="Number of losses for team 2")
    team2_ties: int = Field(description="Number of ties for team 2", default=0)


async def matchup_analyzer(params: MatchupParams) -> str:
    """Compare two NFL teams based on their win-loss-tie records.
    Returns the team name that has the better record, or 'tie' if records are equal."""

    def win_pct(wins: int, losses: int, ties: int) -> float:
        total = wins + losses + ties
        if total == 0:
            return 0.0
        return (wins + 0.5 * ties) / total

    team1_pct = win_pct(params.team1_wins, params.team1_losses, params.team1_ties)
    team2_pct = win_pct(params.team2_wins, params.team2_losses, params.team2_ties)

    if team1_pct > team2_pct:
        return "team1"
    elif team2_pct > team1_pct:
        return "team2"
    else:
        return "tie"
