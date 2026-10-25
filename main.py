from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import SQLModel, Field, Session, create_engine, select


# ---------- Models ----------

class TeamBase(SQLModel):
    name: str = Field(min_length=1, max_length=50)
    country: str = Field(min_length=1, max_length=50)


class Team(TeamBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class TeamCreate(TeamBase):
    pass

class MatchBase(SQLModel):
    home_team_id: int = Field(foreign_key="team.id")
    away_team_id: int = Field(foreign_key="team.id")
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


class Match(MatchBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class MatchCreate(MatchBase):
    pass



# ---------- Database setup ----------

engine = create_engine("sqlite:///database.db")


def get_session():
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def home():
    return {"message": "Match Tracker API is running!"}


@app.get("/teams")
def get_teams(session: Session = Depends(get_session)):
    teams = session.exec(select(Team)).all()
    return teams

@app.get("/teams/{team_id}")
def get_team(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team:
        return team
    else:
        raise HTTPException(status_code=404, detail="Team not found")

@app.post("/teams", status_code=201)
def create_team(team: TeamCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(Team).where(Team.name == team.name, Team.country == team.country)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A team with this name and country already exists.")

    db_team = Team.model_validate(team)
    session.add(db_team)
    session.commit()
    session.refresh(db_team)
    return db_team

@app.put("/teams/{team_id}")
def update_team(team_id: int, team: TeamCreate, session: Session = Depends(get_session)):
    existing_team = session.get(Team, team_id)
    if existing_team:
        existing_team.name = team.name
        existing_team.country = team.country
        session.commit()
        session.refresh(existing_team)
        return existing_team
    else:
        raise HTTPException(status_code=404, detail="Team not found")

@app.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, session: Session = Depends(get_session)):
    existing_team = session.get(Team, team_id)
    if existing_team:
        session.delete(existing_team)
        session.commit()
        return
    else:
        raise HTTPException(status_code=404, detail="Team not found")

@app.get("/matches")
def get_matches(session: Session = Depends(get_session)):
    matches = session.exec(select(Match)).all()
    return matches

@app.post("/matches", status_code=201)
def create_match(match: MatchCreate, session: Session = Depends(get_session)):
    # Check if both teams exist
    home_team = session.get(Team, match.home_team_id)
    away_team = session.get(Team, match.away_team_id)
    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="One or both teams not found")
    if match.home_team_id == match.away_team_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself.")
    match = Match.model_validate(match)
    session.add(match)
    session.commit()
    session.refresh(match)
    return match

@app.get("/matches/{match_id}")
def get_match(match_id: int, session: Session = Depends(get_session)):
    db_match = session.get(Match, match_id)
    if not db_match:
        raise HTTPException(status_code=404, detail="Match not found")
    return db_match
