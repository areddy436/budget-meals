from pydantic import BaseModel
from typing import List, Optional

# What the frontend sends after onboarding
class UserProfile(BaseModel):
    name: str
    age: int
    weight_lbs: float
    location: str                    # e.g. "San Diego, CA"
    fitness_goal: str                # "lose_fat" | "gain_muscle" | "maintain"
    activity_level: str              # "sedentary" | "light" | "moderate" | "active"
    workout_duration: str            # "under_30" | "30_60" | "over_60" | "none"
    nutrition_goal: str              # "high_protein" | "low_carb" | "balanced" etc
    diet_type: str                   # "vegan" | "vegetarian" | "plant_focused" | "omnivore"
    meats_eaten: List[str]           # ["chicken", "fish"] — empty if vegan/veg
    allergies: List[str]             # ["gluten", "dairy"] etc
    eating_habits: List[str]         # ["skip_breakfast", "light_dinner"] etc
    budget_weekly: float             # in dollars
    cook_time_max: str               # "under_15" | "15_30" | "30_45" | "45_60" | "no_limit"
    meals_per_day: int               # 2, 3, 4, 5
    has_full_kitchen: str            # "yes" | "shared" | "limited"
    is_ucsd_student: bool
    has_ebt: bool
    wants_benefits_info: bool

# A single meal
class Meal(BaseModel):
    name: str
    day: str                         # "Monday", "Tuesday" etc
    meal_type: str                   # "breakfast" | "lunch" | "dinner"
    ingredients: List[str]
    recipe_steps: List[str]
    cook_time_minutes: int
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    is_seasonal: bool
    seasonal_ingredients: List[str]  # which ingredients are seasonal

# The full 7-day meal plan
class MealPlan(BaseModel):
    meals: List[Meal]
    weekly_summary: str
    estimated_prep_tip: str

# One item in the grocery list
class GroceryItem(BaseModel):
    name: str
    quantity: str                    # e.g. "2 lbs", "1 bunch"
    category: str                    # "Produce" | "Proteins" | "Grains" etc
    ebt_eligible: bool               # whether EBT/SNAP covers it

# One store option with prices
class StoreOption(BaseModel):
    stores: List[str]                # ["Ralphs"] or ["Ralphs", "Trader Joe's"]
    total_cost: float
    is_best_value: bool
    item_prices: List[dict]          # [{"item": "chicken breast", "store": "Ralphs", "price": 5.99}]

# The grocery list with store comparisons
class GroceryList(BaseModel):
    items: List[GroceryItem]
    store_options: List[StoreOption]

# What the backend sends back to the frontend — everything in one response
class MealPlanResponse(BaseModel):
    meal_plan: MealPlan
    grocery_list: GroceryList