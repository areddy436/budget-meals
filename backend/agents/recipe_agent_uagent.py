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
from typing import Optional
from uagents import Agent, Context, Model
 
# ── 1. Import your existing logic (file stays untouched) ──────────────────────
from backend.agents.recipe_agent import generate_meal_plan
from backend.models.schemas import UserProfile
 
 
# ── 2. Message schemas ────────────────────────────────────────────────────────
#    These are the "envelopes" other agents (e.g. from Lovable) send you.
#    Mirror the fields of UserProfile so the caller can pass everything in.
print("script started")
 
class MealPlanRequest(Model):
    name: str = ""
    height: Optional[float] = None
    nutrient_focus: list[str] = []
    meal_counts: dict = {}
    has_full_kitchen: str = "Yes"  # str not bool
    food_assistance: list[str] = []
    has_ebt: bool = False
    is_ucsd_student: bool = False
    wants_benefits_info: bool = True
 
 
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
            name=msg.name,
            height=msg.height,
            nutrient_focus=msg.nutrient_focus,
            meal_counts=msg.meal_counts,
            food_assistance=msg.food_assistance,
            has_ebt=msg.has_ebt,
            is_ucsd_student=msg.is_ucsd_student,
            wants_benefits_info=msg.wants_benefits_info
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