from pydantic import BaseModel
from typing import List, Optional

class UserProfile(BaseModel):
    name: str
    age: int
    weight_lbs: float
    location: str
    fitness_goal: str
    activity_level: str
    workout_duration: str
    nutrition_goal: str
    diet_type: str
    meats_eaten: List[str] = []
    allergies: List[str] = []
    eating_habits: List[str] = []
    budget_weekly: float
    cook_time_max: str
    meals_per_day: int = 3
    has_full_kitchen: str = "yes"
    is_ucsd_student: bool = False
    has_ebt: bool = False
    wants_benefits_info: bool = True

# Matches Lovable's ingredient shape exactly
class IngredientItem(BaseModel):
    name: str
    amount: str
    inPantry: Optional[bool] = False

# Matches Lovable's Meal interface exactly
class Meal(BaseModel):
    id: str
    name: str
    type: str          # 'breakfast' | 'lunch' | 'dinner' | 'snack'
    cookTime: int
    calories: int
    protein: int
    carbs: int
    fat: int
    fiber: Optional[int] = None
    ingredients: List[IngredientItem]
    instructions: str
    seasonal: Optional[bool] = False

# Matches Lovable's price shape
class StorePrice(BaseModel):
    store: str
    price: float

# Matches Lovable's GroceryItem interface exactly
class GroceryItem(BaseModel):
    id: str
    name: str
    quantity: str
    category: str
    prices: List[StorePrice]
    ebtEligible: bool
    checked: bool = False
    alreadyHave: bool = False

# Matches Lovable's storeOptions shape
class StoreOption(BaseModel):
    label: str
    stores: List[str]
    total_cost: float
    is_best_value: bool = False

# The full response — everything Lovable needs in one object
class MealPlanResponse(BaseModel):
    meals: List[Meal]
    groceryItems: List[GroceryItem]
    storeOptions: List[StoreOption]
    weeklyBudget: float
    estimatedTotal: float
    weeklySummary: str
    prepTip: str