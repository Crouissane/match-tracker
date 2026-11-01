import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from main import app, get_session


@pytest.fixture
def client():
    # A fresh, empty database in memory for every test
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    # Use the test database instead of database.db
    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_team(client):
    response = client.post("/teams", json={"name": "Arsenal", "country": "England"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Arsenal"
    assert data["id"] is not None


def test_get_team_not_found(client):
    response = client.get("/teams/99")

    assert response.status_code == 404

def test_create_duplicate_team(client):
    # Set up: create the team once
    client.post("/teams", json={"name": "Arsenal", "country": "England"})

    # Do: try to create the same team again
    response = client.post("/teams", json={"name": "Arsenal", "country": "England"})

    # Check
    assert response.status_code == 409
    assert response.json()["detail"] == "A team with this name and country already exists."

def test_create_team_with_empty_name(client):
    response = client.post("/teams", json={"name": "", "country": ""})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]

def test_match_against_itself(client):
    #set up: create a team
    team_response =client.post("/teams", json={"name": "Arsenal", "country": "England"})
    team_id = team_response.json()["id"]

    response = client.post("/matches", json={
        "home_team_id": team_id,
        "away_team_id": team_id,
        "home_score": 1,
        "away_score": 0
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "A team cannot play against itself."

def test_match_with_nonexistent_team(client):
    team_response = client.post("/teams", json={"name": "Arsenal", "country": "England"})
    team_id = team_response.json()["id"]

    response = client.post("/matches", json={
        "home_team_id": team_id,
        "away_team_id": 999, #nonexistent team
        "home_score": 1,
        "away_score": 0
    })

    assert response.status_code == 404
    assert response.json()["detail"] == "One or both teams not found"

def test_standing_order(client):
    # Create teams
    team1 = client.post("/teams", json={"name": "Team 1", "country": "Country 1"}).json()
    team2 = client.post("/teams", json={"name": "Team 2", "country": "Country 2"}).json()
    team3 = client.post("/teams", json={"name": "Team 3", "country": "Country 3"}).json()  

    match1 = client.post("/matches", json={
        "home_team_id": team1["id"],
        "away_team_id": team2["id"],
        "home_score": 3,
        "away_score": 1
    }).json()

    match2 = client.post("/matches", json={
        "home_team_id": team2["id"],
        "away_team_id": team3["id"],
        "home_score": 2,
        "away_score": 2
    }).json()   

    match3 = client.post("/matches", json={
        "home_team_id": team3["id"],
        "away_team_id": team1["id"],
        "home_score": 0,
        "away_score": 1
    }).json()

    response = client.get("/standings")
    standings = response.json()

    assert response.status_code == 200
    assert standings[0]["team"] == "Team 1"
    assert standings[0]["points"] == 6
    assert standings[1]["team"] == "Team 3"
    assert standings[1]["points"] == 1
    assert standings[2]["team"] == "Team 2"
    assert standings[2]["points"] == 1

def test_deleting_a_team_has_matches(client):
    team1 = client.post("/teams", json={"name": "Arsenal", "country": "England"}).json()
    team2 = client.post("/teams", json={"name": "PSG", "country": "France"}).json()

    match_response = client.post("/matches", json={
        "home_team_id": team1["id"],
        "away_team_id": team2["id"],
        "home_score": 1,
        "away_score": 0,
    })
    assert match_response.status_code == 201
    response = client.delete(f"/teams/{team1['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot delete team that has played matches."

    assert client.get(f"/teams/{team1["id"]}").status_code == 200