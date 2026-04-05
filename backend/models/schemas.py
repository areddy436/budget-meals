from pydantic import BaseModel
from typing import Optional, List

class UserProfile(BaseModel):
    # Nutrition
    nutrition_goal: str          # "protein_focused", "low_carb", "balanced", etc.
    target_vitamins: List[str]   # ["vitamin_d", "iron"] etc.
    cooking_time_per_meal: float   # minutes willing to cook
    
    # Fitness
    activity_level: str          # "sedentary", "lightly_active", "active", "very_active"
    age: int
    weight: float                # lbs
    
    # Diet
    diet_type: str               # "vegan", "vegetarian", "omnivore", "plant_focused"
    allergies: List[str]         # ["gluten", "nuts"] etc.
    
    # Budget & location
    weekly_budget: float
    location: str                # "La Jolla, CA" — used for seasonal + stores
    has_ebt: bool
    is_student: bool

class MealPlanRequest(BaseModel):
    user_profile: UserProfile
    days: int = 7                # how many days to plan for

class GroceryItem(BaseModel):
    name: str
    quantity: str
    estimated_price: float
    store: str
    seasonal: bool

class StoreOption(BaseModel):
    stores: List[str]            # ["Ralphs"] or ["Ralphs", "Trader Joe's"]
    total_cost: float
    items: List[GroceryItem]

class MealPlanResponse(BaseModel):
    meal_plan: dict              # structured meal plan from ASI one
    grocery_options: List[StoreOption]   # options: one store each + combo
    seasonal_highlights: List[str]
    benefits_suggestions: List[str]      # CalFresh, food pantry etc.