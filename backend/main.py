from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from models.schemas import UserProfile, MealPlanResponse
from agents.recipe_agent import generate_meals
from agents.grocery_agent import generate_grocery_list

app = FastAPI(title="Budget Meals API")

# CORS — allows your Lovable frontend to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://budget-meals-production.up.railway.app",  # your real Lovable URL
        "https://your-budget-meals.lovable.app",  # your real Lovable URL
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*" ],
)

@app.get("/")
def health():
    return {"status": "Budget Meals backend running"}


@app.post("/generate-plan", response_model=MealPlanResponse)
async def generate_plan(profile: UserProfile):
    try:
        print(f"Generating plan for {profile.name} in {profile.location}...")

        # Step 1: Generate meals from ASI:One
        meals, weekly_summary, prep_tip = await generate_meals(profile)
        print(f"Got {len(meals)} meals")

        # Step 2: Get grocery list with real nearby store prices
        grocery_items, store_options, estimated_total = await generate_grocery_list(
            meals=meals,
            budget=profile.budget_weekly,
            location=profile.location
        )
        print(f"Got {len(grocery_items)} grocery items across {len(store_options)} store options")

        return MealPlanResponse(
            meals=meals,
            groceryItems=grocery_items,
            storeOptions=store_options,
            weeklyBudget=profile.budget_weekly,
            estimatedTotal=estimated_total,
            weeklySummary=weekly_summary,
            prepTip=prep_tip
        )

    except Exception as e:
        print(f"Error generating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))