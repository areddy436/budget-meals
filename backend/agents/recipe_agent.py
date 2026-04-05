import httpx
import json
import os
import uuid
from dotenv import load_dotenv
from datetime import datetime
from models.schemas import UserProfile, Meal, IngredientItem
from typing import List

load_dotenv()

ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"

def get_asi_key():
    return os.getenv("ASI_ONE_API_KEY")

def build_prompt(profile: UserProfile) -> str:
    month = datetime.now().strftime("%B")

    diet_desc = {
        "vegan": "strictly vegan, no animal products",
        "vegetarian": "vegetarian, no meat or fish",
        "plant_focused": f"plant-focused but eats: {', '.join(profile.meats_eaten) or 'some meats'}",
        "omnivore": f"omnivore, eats: {', '.join(profile.meats_eaten) or 'any meat'}"
    }.get(profile.diet_type, profile.diet_type)

    time_desc = {
        "under_15": "under 15 minutes",
        "15_30": "15–30 minutes",
        "30_45": "30–45 minutes",
        "45_60": "45–60 minutes",
        "no_limit": "any duration"
    }.get(profile.cook_time_max, "30 minutes")

    habits = []
    habit_map = {
        "skip_breakfast": "skips breakfast",
        "light_dinner": "prefers light dinners",
        "intermittent_fasting": "does intermittent fasting",
        "meal_prep_weekends": "meal preps on weekends",
    }
    for h in profile.eating_habits:
        if h in habit_map:
            habits.append(habit_map[h])

    total_meals = profile.meals_per_day * 7

    return f"""
You are a nutritionist creating a personalized 7-day meal plan.

USER:
- Name: {profile.name}, Age: {profile.age}, Weight: {profile.weight_lbs} lbs
- Location: {profile.location} (month: {month})
- Goal: {profile.fitness_goal}, Activity: {profile.activity_level}
- Nutrition goal: {profile.nutrition_goal}
- Diet: {diet_desc}
- Allergies: {', '.join(profile.allergies) or 'none'}
- Habits: {', '.join(habits) or 'none'}
- Max cook time: {time_desc}
- Meals per day: {profile.meals_per_day}
- Weekly budget: ${profile.budget_weekly}
- Kitchen: {profile.has_full_kitchen}

RULES:
1. Generate exactly {total_meals} meals covering 7 days
2. Respect all allergies and diet type strictly
3. Prefer seasonal produce in {profile.location} in {month}
4. Keep ingredients affordable for ${profile.budget_weekly}/week
5. Never repeat the same meal
6. Mark seasonal meals with seasonal: true
7. Write clear step-by-step instructions as one string

Return ONLY valid JSON, no markdown, no explanation:
{{
  "meals": [
    {{
      "name": "Meal Name",
      "type": "breakfast",
      "cookTime": 10,
      "calories": 380,
      "protein": 14,
      "carbs": 52,
      "fat": 10,
      "fiber": 5,
      "ingredients": [
        {{"name": "Rolled oats", "amount": "½ cup", "inPantry": false}}
      ],
      "instructions": "Step 1. Step 2. Step 3.",
      "seasonal": true
    }}
  ],
  "weeklySummary": "One sentence summary of the plan.",
  "prepTip": "One practical cooking tip for this person."
}}
"""

async def generate_meals(profile: UserProfile) -> tuple:
    """Returns (meals, weeklySummary, prepTip)"""
    prompt = build_prompt(profile)

    headers = {
        "Authorization": f"Bearer {get_asi_key()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "asi1-mini",
        "messages": [
            {"role": "system", "content": "You are a nutritionist. Respond with valid JSON only. No markdown."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4000
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(ASI_ONE_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw = data["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)

    meals = []
    for i, m in enumerate(parsed["meals"]):
        ingredients = [
            IngredientItem(
                name=ing["name"],
                amount=ing["amount"],
                inPantry=ing.get("inPantry", False)
            )
            for ing in m["ingredients"]
        ]
        meals.append(Meal(
            id=f"meal_{i}_{m['type'][0]}",
            name=m["name"],
            type=m["type"],
            cookTime=m["cookTime"],
            calories=m["calories"],
            protein=m["protein"],
            carbs=m["carbs"],
            fat=m["fat"],
            fiber=m.get("fiber"),
            ingredients=ingredients,
            instructions=m["instructions"],
            seasonal=m.get("seasonal", False)
        ))

    return meals, parsed.get("weeklySummary", ""), parsed.get("prepTip", "") 