from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Depends
from pydantic import ConfigDict
from sqlmodel import SQLModel, Field, Session, create_engine, select, or_


# ---------- Models ----------
#
# One model per job:
#   XBase    -> fields shared by all the others
#   X        -> the database table (table=True does NOT validate input)
#   XCreate  -> what the client sends to create
#   XUpdate  -> what the client sends to partially update (PATCH)
#   XPublic  -> what the API sends back

class TeamBase(SQLModel):
    # Strip spaces before validating, so "   " becomes "" and fails min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=50)
    country: str = Field(min_length=1, max_length=50)


class Team(TeamBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class TeamCreate(TeamBase):
    pass


class TeamUpdate(SQLModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Every field is optional: the client sends only what it wants to change.
    name: str | None = Field(default=None, min_length=1, max_length=50)
    country: str | None = Field(default=None, min_length=1, max_length=50)


class TeamPublic(TeamBase):
    id: int


class MatchBase(SQLModel):
    home_team_id: int = Field(foreign_key="team.id")
    away_team_id: int = Field(foreign_key="team.id")
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


class Match(MatchBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class MatchCreate(MatchBase):
    pass


class MatchPublic(MatchBase):
    id: int


class StandingRow(SQLModel):
    team: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


# ---------- Database setup ----------

engine = create_engine("sqlite:///database.db")


def get_session():
    with Session(engine) as session:
        yield session


# Write the dependency once, reuse it in every endpoint.
SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


# ---------- Standings cache ----------

standings_cache: list[dict] | None = None


def invalidate_standings():
    """Call after every change that can affect the league table."""
    global standings_cache
    standings_cache = None


# ---------- Helpers ----------

def get_team_or_404(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def ensure_team_is_unique(session: Session, name: str, country: str, exclude_id: int | None = None):
    """Raise 409 if another team already has this name and country."""
    query = select(Team).where(Team.name == name, Team.country == country)
    if exclude_id is not None:
        query = query.where(Team.id != exclude_id)  # a team may keep its own name
    if session.exec(query).first():
        raise HTTPException(status_code=409, detail="A team with this name and country already exists.")


# ---------- Endpoints ----------

@app.get("/")
def home():
    return {"message": "Match Tracker API is running!"}


# ----- Teams -----

@app.get("/teams", response_model=list[TeamPublic])
def get_teams(session: SessionDep):
    return session.exec(select(Team)).all()


@app.get("/teams/{team_id}", response_model=TeamPublic)
def get_team(team_id: int, session: SessionDep):
    return get_team_or_404(session, team_id)


@app.post("/teams", status_code=201, response_model=TeamPublic)
def create_team(team: TeamCreate, session: SessionDep):
    ensure_team_is_unique(session, team.name, team.country)

    db_team = Team.model_validate(team)
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    invalidate_standings()
    return db_team


@app.put("/teams/{team_id}", response_model=TeamPublic)
def update_team(team_id: int, team: TeamCreate, session: SessionDep):
    db_team = get_team_or_404(session, team_id)
    ensure_team_is_unique(session, team.name, team.country, exclude_id=team_id)

    db_team.sqlmodel_update(team.model_dump())
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    invalidate_standings()
    return db_team


@app.patch("/teams/{team_id}", response_model=TeamPublic)
def patch_team(team_id: int, team: TeamUpdate, session: SessionDep):
    db_team = get_team_or_404(session, team_id)

    data = team.model_dump(exclude_unset=True)  # only the fields the client sent
    new_name = data.get("name", db_team.name)
    new_country = data.get("country", db_team.country)
    ensure_team_is_unique(session, new_name, new_country, exclude_id=team_id)

    db_team.sqlmodel_update(data)
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    invalidate_standings()
    return db_team


@app.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, session: SessionDep):
    db_team = get_team_or_404(session, team_id)

    # Does this team appear in any match?
    has_match = session.exec(
        select(Match).where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
        )
    ).first()
    if has_match:
        raise HTTPException(status_code=409, detail="Cannot delete team that has played matches.")

    session.delete(db_team)
    session.commit()
    invalidate_standings()


# ----- Matches -----

@app.get("/matches", response_model=list[MatchPublic])
def get_matches(session: SessionDep):
    return session.exec(select(Match)).all()


@app.get("/matches/{match_id}", response_model=MatchPublic)
def get_match(match_id: int, session: SessionDep):
    db_match = session.get(Match, match_id)
    if not db_match:
        raise HTTPException(status_code=404, detail="Match not found")
    return db_match


@app.post("/matches", status_code=201, response_model=MatchPublic)
def create_match(match: MatchCreate, session: SessionDep):
    # Cheap check first: it needs no database query.
    if match.home_team_id == match.away_team_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself.")

    home_team = session.get(Team, match.home_team_id)
    away_team = session.get(Team, match.away_team_id)
    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="One or both teams not found")

    db_match = Match.model_validate(match)
    session.add(db_match)
    session.commit()
    session.refresh(db_match)
    invalidate_standings()
    return db_match


# ---------- Standings ----------

def calculate_standings(teams: list[Team], matches: list[Match]) -> list[dict]:
    # One entry per team, all stats start at 0
    table = {
        team.id: {
            "team": team.name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
        }
        for team in teams
    }

    # Update stats from every match
    for match in matches:
        home = table[match.home_team_id]
        away = table[match.away_team_id]

        home["played"] += 1
        home["goals_for"] += match.home_score
        home["goals_against"] += match.away_score
        away["played"] += 1
        away["goals_for"] += match.away_score
        away["goals_against"] += match.home_score

        if match.home_score > match.away_score:
            home["wins"] += 1
            home["points"] += 3
            away["losses"] += 1
        elif match.home_score < match.away_score:
            away["wins"] += 1
            away["points"] += 3
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1

    # Goal difference, then sort: points, goal difference, goals scored
    standings = list(table.values())
    for row in standings:
        row["goal_difference"] = row["goals_for"] - row["goals_against"]
    standings.sort(key=lambda r: (r["points"], r["goal_difference"], r["goals_for"]), reverse=True)
    return standings


@app.get("/standings", response_model=list[StandingRow])
def get_standings(session: SessionDep):
    global standings_cache
    # "is not None", not "if standings_cache:" -- an empty list is a valid cached result.
    if standings_cache is not None:
        return standings_cache

    teams = session.exec(select(Team)).all()
    matches = session.exec(select(Match)).all()
    standings_cache = calculate_standings(teams, matches)
    return standings_cache
