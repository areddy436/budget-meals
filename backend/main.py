from fastapi import FastAPI
from .agents.pipeline import run_pipeline

app = FastAPI()

@app.post("/plan")
async def create_plan(user_input: dict):
    return run_pipeline(user_input)