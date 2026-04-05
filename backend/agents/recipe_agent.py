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
        "Vegan": "strictly vegan, no animal products",
        "Vegetarian": "vegetarian, no meat or fish",
        "Plant-focused (not plant only)": "plant-focused but includes some animal products",
        "Omnivore": "omnivore, eats any meat or animal products"
    }.get(profile.diet_type, profile.diet_type)

    time_desc = {
        "Under 15 min": "under 15 minutes",
        "15–30 min": "15–30 minutes",
        "30–45 min": "30–45 minutes",
        "45–60 min": "45–60 minutes",
        "No limit": "any duration"
    }.get(profile.cook_time_max, "30 minutes")

    # Meal counts from the MealCounts model
    mc = profile.meal_counts
    total_meals = mc.breakfasts + mc.lunches + mc.dinners + mc.snacks + mc.juices

    nutrient_line = ""
    if profile.nutrition_goal == "Focus on vitamins/micronutrients" and profile.nutrient_focus:
        nutrient_line = f"- Key nutrients to prioritize: {', '.join(profile.nutrient_focus)}"

    ebt_line = ""
    if profile.has_ebt:
        ebt_line = "- User has EBT/CalFresh — prioritize EBT-eligible whole foods"

    ucsd_line = ""
    if profile.is_ucsd_student:
        ucsd_line = "- User is a UCSD student — mention campus food pantry where relevant"

    height_line = f"- Height: {profile.height} inches" if profile.height else ""

    return f"""
                You are a nutritionist creating a personalized meal plan.

                USER:
                - Name: {profile.name}, Age: {profile.age}, Weight: {profile.weight_lbs} lbs
                {height_line}
                - Location: {profile.location} (month: {month})
                - Activity level: {profile.activity_level}
                - Nutrition goal: {profile.nutrition_goal}
                {nutrient_line}
                - Diet: {diet_desc}
                - Allergies: {', '.join(profile.allergies) or 'none'}
                - Max cook time: {time_desc}
                - Weekly budget: ${profile.budget_weekly}
                - Kitchen access: {profile.has_full_kitchen}
                {ebt_line}
                {ucsd_line}

                MEAL COUNTS FOR THE WEEK:
                - Breakfasts: {mc.breakfasts}
                - Lunches: {mc.lunches}
                - Dinners: {mc.dinners}
                - Snacks: {mc.snacks}
                - Juices / Smoothies: {mc.juices}
                - Total meals: {total_meals}

                RULES:
                1. Generate exactly {total_meals} meals matching the counts above
                2. Meal type must be one of: breakfast, lunch, dinner, snack, juice
                3. Respect all allergies and diet type strictly
                4. Prefer seasonal produce in {profile.location} in {month}
                5. Keep ingredients affordable for ${profile.budget_weekly}/week
                6. Never repeat the same meal
                7. Mark seasonal meals with seasonal: true
                8. Write clear step-by-step instructions as one string

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