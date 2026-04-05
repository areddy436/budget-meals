from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import onboarding, meal_plan, grocery

app = FastAPI(title="Budget Meals UCSD API")

# Allow your React Native app to call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding.router, prefix="/api")
app.include_router(meal_plan.router, prefix="/api")
app.include_router(grocery.router, prefix="/api")

@app.get("/")
def root():
    return {"status": "FoodSecure backend running"}