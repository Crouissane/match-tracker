from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

# What a team must look like when someone creates one
class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    country: str = Field(min_length=1, max_length=50)   

# Our "database" for now
teams = []
next_id = 1


@app.get("/")
def home():
    return {"message": "Match Tracker API is running!"}


# Get all teams
@app.get("/teams")
def get_teams():
    return teams


# Create a new team
@app.post("/teams", status_code=201)
def create_team(team: TeamCreate):
    for existing_team in teams:
            if existing_team["name"] == team.name and existing_team["country"] == team.country:
                raise HTTPException(status_code = 409, detail="A team with this name and country already exists.")
    global next_id
    new_team = {"id": next_id, "name": team.name, "country": team.country}
    teams.append(new_team)
    next_id += 1
    return new_team


# Get one team by its id
@app.get("/teams/{team_id}")
def get_team(team_id: int):
    for team in teams:
        if team["id"] == team_id:
            return team
    raise HTTPException(status_code=404, detail="Team not found")

@app.put("/teams/{team_id}")
def update_team(team_id: int, team: TeamCreate):
    for existing_team in teams:
        if existing_team["id"] == team_id:
            existing_team["name"] = team.name
            existing_team["country"] = team.country
            return existing_team
    raise HTTPException(status_code=404, detail="Team not found")

@app.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int):
    for existing_team in teams:
        if existing_team["id"] == team_id:
            teams.remove(existing_team)
            return
    raise HTTPException(status_code=404, detail="Team not found")