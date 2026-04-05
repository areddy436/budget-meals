from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
load_dotenv()

from models.schemas import UserProfile, MealPlanResponse
from agents.recipe_agent import generate_meal_plan #! change name according to what was written
from agents.grocery_scraper_agent import generate_grocery_list #! change name according to what was written 

app = FastAPI(title="Budget Meals API")

# CORS — this lets your Lovable frontend (different URL) talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this after hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "Budget Meals backend is running"}


@app.post("/generate-plan", response_model=MealPlanResponse)
async def generate_plan(profile: UserProfile):
    """
    Main endpoint. Frontend calls this once with the full user profile.
    Returns meal plan + grocery list with store prices in one response.
    """
    try:
        # Step 1: Generate meal plan from ASI:One
        print(f"Generating meal plan for {profile.name}...")
        meal_plan = await generate_meal_plan(profile)
        print(f"Got {len(meal_plan.meals)} meals")
        
        # Step 2: Generate grocery list with Browser Use scraping
        # Run this after meal plan since we need the ingredient list
        print("Scraping grocery prices...")
        grocery_list = await generate_grocery_list(
            meals=meal_plan.meals,
            budget=profile.budget_weekly,
            location=profile.location
        )
        print(f"Got {len(grocery_list.items)} grocery items, {len(grocery_list.store_options)} store options")
        
        return MealPlanResponse(
            meal_plan=meal_plan,
            grocery_list=grocery_list
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/onboarding")
async def save_onboarding(profile: UserProfile):
    """
    Optional: save the profile before generating.
    Useful if you want to store it and generate asynchronously.
    """
    # For the hackathon, just return success — no DB needed
    return {"status": "ok", "message": f"Profile saved for {profile.name}"}