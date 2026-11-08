import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import main
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
    # The cache lives in the module, so reset it or tests leak into each other
    main.invalidate_standings()
    yield TestClient(app)
    app.dependency_overrides.clear()
    main.invalidate_standings()


# ---------- Helpers ----------

def create_team(client, name, country="England"):
    response = client.post("/teams", json={"name": name, "country": country})
    assert response.status_code == 201
    return response.json()


def create_match(client, home, away, home_score, away_score):
    response = client.post("/matches", json={
        "home_team_id": home["id"],
        "away_team_id": away["id"],
        "home_score": home_score,
        "away_score": away_score,
    })
    assert response.status_code == 201
    return response.json()


# ---------- Teams ----------

def test_create_team(client):
    response = client.post("/teams", json={"name": "Arsenal", "country": "England"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Arsenal"
    assert data["id"] is not None


def test_create_team_strips_whitespace(client):
    response = client.post("/teams", json={"name": "  Arsenal ", "country": "England"})

    assert response.status_code == 201
    assert response.json()["name"] == "Arsenal"


def test_get_team_not_found(client):
    response = client.get("/teams/99")

    assert response.status_code == 404


def test_create_duplicate_team(client):
    # Set up: create the team once
    create_team(client, "Arsenal")

    # Do: try to create the same team again
    response = client.post("/teams", json={"name": "Arsenal", "country": "England"})

    # Check
    assert response.status_code == 409
    assert response.json()["detail"] == "A team with this name and country already exists."


def test_create_team_with_empty_name(client):
    response = client.post("/teams", json={"name": "", "country": ""})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]


def test_create_team_with_only_spaces(client):
    response = client.post("/teams", json={"name": "   ", "country": "England"})

    assert response.status_code == 422


def test_update_team(client):
    team = create_team(client, "Arsenal")

    response = client.put(f"/teams/{team['id']}", json={"name": "Arsenal FC", "country": "England"})

    assert response.status_code == 200
    assert response.json()["name"] == "Arsenal FC"


def test_update_team_keeping_same_name(client):
    team = create_team(client, "Arsenal")

    # Saving a team with its own current name is not a duplicate
    response = client.put(f"/teams/{team['id']}", json={"name": "Arsenal", "country": "England"})

    assert response.status_code == 200


def test_update_team_into_duplicate(client):
    create_team(client, "Arsenal")
    psg = create_team(client, "PSG", "France")

    response = client.put(f"/teams/{psg['id']}", json={"name": "Arsenal", "country": "England"})

    assert response.status_code == 409


def test_update_team_not_found(client):
    response = client.put("/teams/99", json={"name": "Arsenal", "country": "England"})

    assert response.status_code == 404


def test_patch_team_changes_only_sent_fields(client):
    team = create_team(client, "Arsenal")

    response = client.patch(f"/teams/{team['id']}", json={"country": "Spain"})

    assert response.status_code == 200
    assert response.json()["name"] == "Arsenal"  # untouched
    assert response.json()["country"] == "Spain"


def test_patch_team_into_duplicate(client):
    create_team(client, "Arsenal", "England")
    other = create_team(client, "Arsenal", "Spain")

    response = client.patch(f"/teams/{other['id']}", json={"country": "England"})

    assert response.status_code == 409


def test_delete_team(client):
    team = create_team(client, "Arsenal")

    assert client.delete(f"/teams/{team['id']}").status_code == 204
    assert client.get(f"/teams/{team['id']}").status_code == 404


def test_deleting_a_team_has_matches(client):
    team1 = create_team(client, "Arsenal")
    team2 = create_team(client, "PSG", "France")
    create_match(client, team1, team2, 1, 0)

    response = client.delete(f"/teams/{team1['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot delete team that has played matches."
    assert client.get(f"/teams/{team1['id']}").status_code == 200


# ---------- Matches ----------

def test_match_against_itself(client):
    team = create_team(client, "Arsenal")

    response = client.post("/matches", json={
        "home_team_id": team["id"],
        "away_team_id": team["id"],
        "home_score": 1,
        "away_score": 0,
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "A team cannot play against itself."


def test_match_with_nonexistent_team(client):
    team = create_team(client, "Arsenal")

    response = client.post("/matches", json={
        "home_team_id": team["id"],
        "away_team_id": 999,  # nonexistent team
        "home_score": 1,
        "away_score": 0,
    })

    assert response.status_code == 404
    assert response.json()["detail"] == "One or both teams not found"


def test_match_with_negative_score(client):
    team1 = create_team(client, "Arsenal")
    team2 = create_team(client, "PSG", "France")

    response = client.post("/matches", json={
        "home_team_id": team1["id"],
        "away_team_id": team2["id"],
        "home_score": -1,
        "away_score": 0,
    })

    assert response.status_code == 422


# ---------- Standings ----------

def test_standings_with_no_matches(client):
    create_team(client, "Arsenal")

    standings = client.get("/standings").json()

    assert len(standings) == 1
    assert standings[0]["played"] == 0
    assert standings[0]["points"] == 0


def test_standing_order(client):
    team1 = create_team(client, "Team 1", "Country 1")
    team2 = create_team(client, "Team 2", "Country 2")
    team3 = create_team(client, "Team 3", "Country 3")

    create_match(client, team1, team2, 3, 1)
    create_match(client, team2, team3, 2, 2)
    create_match(client, team3, team1, 0, 1)

    response = client.get("/standings")
    standings = response.json()

    assert response.status_code == 200
    assert standings[0]["team"] == "Team 1"
    assert standings[0]["points"] == 6
    assert standings[1]["team"] == "Team 3"
    assert standings[1]["points"] == 1
    assert standings[2]["team"] == "Team 2"
    assert standings[2]["points"] == 1


def test_standings_update_after_new_match(client):
    # Checks that the cache is cleared when a match is recorded
    team1 = create_team(client, "Arsenal")
    team2 = create_team(client, "PSG", "France")

    before = client.get("/standings").json()
    assert before[0]["points"] == 0

    create_match(client, team1, team2, 2, 0)

    after = client.get("/standings").json()
    assert after[0]["team"] == "Arsenal"
    assert after[0]["points"] == 3


def test_standings_update_after_team_rename(client):
    team = create_team(client, "Arsenal")
    client.get("/standings")  # fill the cache

    client.patch(f"/teams/{team['id']}", json={"name": "Arsenal FC"})

    assert client.get("/standings").json()[0]["team"] == "Arsenal FC"
