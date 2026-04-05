"""
recipe_agent_uagent.py — Fetch.ai uAgent wrapper for recipe_agent.py
 
File structure:
  backend/
    agents/
      recipe_agent.py          ← your existing file, untouched
      recipe_agent_uagent.py   ← this file (run this one)
 
Install:  pip install uagents
Run:      python -m backend.agents.recipe_agent_uagent
"""
 
import os
from uagents import Agent, Context, Model
 
# ── 1. Import your existing logic (file stays untouched) ──────────────────────
from backend.agents.recipe_agent import generate_meal_plan
from backend.models.schemas import UserProfile
 
 
# ── 2. Message schemas ────────────────────────────────────────────────────────
#    These are the "envelopes" other agents (e.g. from Lovable) send you.
#    Mirror the fields of UserProfile so the caller can pass everything in.
print("script started")
 
class MealPlanRequest(Model):
    age: int
    weight_lbs: float
    location: str
    fitness_goal: str
    activity_level: str
    workout_duration: str
    nutrition_goal: str
    diet_type: str
    meats_eaten: list[str] = []
    allergies: list[str] = []
    eating_habits: list[str] = []
    cook_time_max: str
    meals_per_day: int
    has_full_kitchen: bool
    budget_weekly: float
 
 
class MealPlanResponse(Model):
    success: bool
    meal_plan_json: str   # serialized MealPlan, parse on the receiving end
    error: str = ""
 
 
# ── 3. Create the Agent ───────────────────────────────────────────────────────
 
agent = Agent(
    name="recipe_agent",
    seed=os.getenv("RECIPE_AGENT_SEED", "recipe_agent_secret_seed_change_me"),
    port=8001,
    #endpoint=["http://127.0.0.1:8001/submit"],
    mailbox=True,   # enables Agentverse mailbox — connect it via the inspector link
    network="testnet"
)
 
print(f"Recipe agent address: {agent.address}")
# ↑ Share this address with your partner so Lovable knows where to send requests
 
 
# ── 4. Startup / shutdown ─────────────────────────────────────────────────────
 
@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"[recipe_agent] online — address: {agent.address}")
 
 
@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    ctx.logger.info("[recipe_agent] shutting down.")
 
 
# ── 5. Main handler — receives request, calls your existing code, replies ──────
 
@agent.on_message(model=MealPlanRequest, replies=MealPlanResponse)
async def handle_meal_plan_request(
    ctx: Context,
    sender: str,
    msg: MealPlanRequest,
):
    ctx.logger.info(f"[recipe_agent] request from {sender} for {msg.location} / {msg.diet_type}")
 
    try:
        # Build the UserProfile your existing code already expects
        profile = UserProfile(
            age=msg.age,
            weight_lbs=msg.weight_lbs,
            location=msg.location,
            fitness_goal=msg.fitness_goal,
            activity_level=msg.activity_level,
            workout_duration=msg.workout_duration,
            nutrition_goal=msg.nutrition_goal,
            diet_type=msg.diet_type,
            meats_eaten=msg.meats_eaten,
            allergies=msg.allergies,
            eating_habits=msg.eating_habits,
            cook_time_max=msg.cook_time_max,
            meals_per_day=msg.meals_per_day,
            has_full_kitchen=msg.has_full_kitchen,
            budget_weekly=msg.budget_weekly,
        )
 
        # Call generate_meal_plan() from your existing recipe_agent.py
        meal_plan = await generate_meal_plan(profile)
 
        await ctx.send(sender, MealPlanResponse(
            success=True,
            meal_plan_json=meal_plan.model_dump_json(),
        ))
 
    except Exception as e:
        ctx.logger.error(f"[recipe_agent] error: {e}")
        await ctx.send(sender, MealPlanResponse(
            success=False,
            meal_plan_json="",
            error=str(e),
        ))
 
 
# ── 6. Run ────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    agent.run()