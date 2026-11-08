# Match Tracker API

A backend API for tracking soccer teams and matches. It calculates a league table automatically from match results.

I built this project to learn backend development step by step: REST APIs, databases, validation, and automated testing.

## Features

- Create, read, update, and delete teams
- Record matches between two teams with the final score
- Automatic league standings (win = 3 points, draw = 1 point)
- Standings sorted by points, then goal difference, then goals scored
- Input validation (no empty names, no negative scores, no duplicate teams)
- A team can't play against itself
- Teams that have played matches can't be deleted
- Automated tests with pytest

## Tech Stack

- **Python**
- **FastAPI** – web framework
- **SQLModel** – database models (built on SQLAlchemy and Pydantic)
- **SQLite** – database
- **pytest** – testing

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/Crouissane/match-tracker.git
   cd match-tracker
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

5. Open the interactive docs at http://127.0.0.1:8000/docs

## API Endpoints

### Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/teams` | Get all teams |
| GET | `/teams/{team_id}` | Get one team |
| POST | `/teams` | Create a team |
| PUT | `/teams/{team_id}` | Update a team |
| DELETE | `/teams/{team_id}` | Delete a team (only if it has no matches) |

### Matches

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/matches` | Get all matches |
| GET | `/matches/{match_id}` | Get one match |
| POST | `/matches` | Record a match |

### Standings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/standings` | Get the league table |

## Example

Create a team:

```json
POST /teams
{
  "name": "Arsenal",
  "country": "England"
}
```

Record a match:

```json
POST /matches
{
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 3,
  "away_score": 1
}
```

## Running Tests

```bash
python -m pytest -v
```

Each test uses its own in-memory database, so tests never touch your real data.

## What I Learned

- Building a REST API with FastAPI and choosing the right HTTP status codes (200, 201, 204, 400, 404, 409, 422)
- Validating input with Pydantic
- Storing data in a database instead of memory
- Linking tables with foreign keys
- Using dependency injection to swap in a test database
- Writing automated tests with pytest

## Future Improvements

- Cache the standings so they are not recalculated on every request
- Switch from SQLite to PostgreSQL
- Run the app with Docker
- Show team names in match responses instead of only idss