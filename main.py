from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Match Tracker API is running!"}