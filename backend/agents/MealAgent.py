import openai

def generate_meal_plan(user_input):
    prompt = f"""
    Generate a 3-day meal plan.

    Budget: {user_input['budget']}
    TimePerMeal: {user_input['time_per_meal']}
    MeatPreference: {user_input['meat_preference']}
    Diet: {user_input['diet']}
    FitnessGoal: {user_input['fitness_goal']}

    Return JSON:
    {{
      "meals": [{{"name": "", "ingredients": [], "cost": 0}}],
      "grocery_list": [],
      "total_cost": 0
    }}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]