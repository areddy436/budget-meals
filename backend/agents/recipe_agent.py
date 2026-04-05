import httpx
import json
import os
from models.schemas import UserProfile, MealPlan, Meal

ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"
ASI_ONE_KEY = os.getenv("ASI_ONE_API_KEY")

def build_recipe_prompt(profile: UserProfile) -> str:
    """
    Turns the user profile into a detailed prompt for ASI:One.
    The more specific this prompt, the better the output.
    """
    
    # Build diet restrictions string
    restrictions = []
    if profile.diet_type == "vegan":
        restrictions.append("strictly vegan (no animal products)")
    elif profile.diet_type == "vegetarian":
        restrictions.append("vegetarian (no meat or fish)")
    elif profile.diet_type == "plant_focused":
        meats = ", ".join(profile.meats_eaten) if profile.meats_eaten else "none"
        restrictions.append(f"plant-focused but eats these meats: {meats}")
    else:
        meats = ", ".join(profile.meats_eaten) if profile.meats_eaten else "any"
        restrictions.append(f"omnivore, eats: {meats}")
    
    if profile.allergies:
        restrictions.append(f"allergic to: {', '.join(profile.allergies)}")
    
    # Build eating habits string
    habits_map = {
        "skip_breakfast": "does not eat breakfast",
        "light_dinner": "prefers light dinners",
        "intermittent_fasting": "does intermittent fasting (skip breakfast)",
        "meal_prep_weekends": "meal preps on weekends, prefers batch-cookable recipes",
        "late_night": "sometimes eats late at night",
        "grazes": "prefers smaller portions spread throughout the day"
    }
    habits = [habits_map.get(h, h) for h in profile.eating_habits]
    
    # Build cook time string
    time_map = {
        "under_15": "under 15 minutes",
        "15_30": "15 to 30 minutes",
        "30_45": "30 to 45 minutes", 
        "45_60": "45 to 60 minutes",
        "no_limit": "any duration"
    }
    max_time = time_map.get(profile.cook_time_max, "30 minutes")
    
    # Current month for seasonal produce
    from datetime import datetime
    month = datetime.now().strftime("%B")
    
    prompt = f"""
You are a professional nutritionist and chef creating a personalized 7-day meal plan.

USER PROFILE:
- Age: {profile.age}, Weight: {profile.weight_lbs} lbs
- Location: {profile.location} (use this for seasonal produce — current month: {month})
- Fitness goal: {profile.fitness_goal}
- Activity level: {profile.activity_level}, workout duration: {profile.workout_duration}
- Nutrition goal: {profile.nutrition_goal}
- Diet: {', '.join(restrictions)}
- Eating habits: {', '.join(habits) if habits else 'no special habits'}
- Max cook time per meal: {max_time}
- Meals per day: {profile.meals_per_day}
- Kitchen access: {profile.has_full_kitchen}
- Weekly grocery budget: ${profile.budget_weekly}

REQUIREMENTS:
1. Create exactly {profile.meals_per_day * 7} meals covering 7 days
2. All meals must respect the diet restrictions and allergies strictly
3. Prioritize seasonal produce available in {profile.location} in {month}
4. Keep ingredients affordable and realistic for a ${profile.budget_weekly}/week budget
5. Each meal must be achievable in {max_time}
6. Vary the meals — do not repeat the same meal twice
7. For each meal, mark which ingredients are currently seasonal in {profile.location}

Respond ONLY with a valid JSON object in this exact format, no explanation, no markdown:
{{
  "meals": [
    {{
      "name": "Meal name",
      "day": "Monday",
      "meal_type": "breakfast",
      "ingredients": ["ingredient 1 with quantity", "ingredient 2 with quantity"],
      "recipe_steps": ["Step 1", "Step 2", "Step 3"],
      "cook_time_minutes": 20,
      "calories": 450,
      "protein_g": 30,
      "carbs_g": 40,
      "fat_g": 15,
      "is_seasonal": true,
      "seasonal_ingredients": ["ingredient name"]
    }}
  ],
  "weekly_summary": "One sentence describing the overall plan",
  "estimated_prep_tip": "One practical tip for this person"
}}
"""
    return prompt


async def generate_meal_plan(profile: UserProfile) -> MealPlan:
    """
    Calls ASI:One with the recipe prompt and parses the response.
    """
    prompt = build_recipe_prompt(profile)
    
    headers = {
        "Authorization": f"Bearer {ASI_ONE_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "asi1-mini",   # or "asi1" for the more powerful model
        "messages": [
            {
                "role": "system",
                "content": "You are a nutritionist. Always respond with valid JSON only. No markdown, no explanation."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(ASI_ONE_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        
        # Clean up in case ASI:One adds markdown code fences
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()
        
        parsed = json.loads(raw_text)
        
        # Convert to Pydantic models
        meals = [Meal(**m) for m in parsed["meals"]]
        return MealPlan(
            meals=meals,
            weekly_summary=parsed["weekly_summary"],
            estimated_prep_tip=parsed["estimated_prep_tip"]
        )