import asyncio
import os
import re
import json
from dotenv import load_dotenv     
from browser_use import Agent, BrowserSession, BrowserProfile   # fixed import
from langchain_openai import ChatOpenAI
from models.schemas import GroceryItem, StoreOption, Meal
from agents.location_agent import find_nearby_stores
from typing import List

# Load .env right here, before anything reads env vars
load_dotenv()

# Disable browser-use telemetry (avoids noisy warnings)
os.environ['ANONYMIZED_TELEMETRY'] = 'false'
os.environ['BROWSER_USE_CLOUD_SYNC'] = 'false'

def get_llm():
    """
    Create LLM fresh each call so it always picks up the loaded API key.
    Avoids the module-level initialization timing problem.
    """
    return ChatOpenAI(
        model="asi1-mini",
        base_url="https://api.asi1.ai/v1",
        api_key=os.getenv("ASI_ONE_API_KEY"),
        temperature=0
    )


def extract_ingredients(meals: List[Meal]) -> List[str]:
    seen = set()
    ingredients = []
    units = {
        "lbs","lb","oz","g","kg","cup","cups","tbsp","tsp","ml",
        "bunch","can","clove","cloves","slice","slices","piece","pieces"
    }
    for meal in meals:
        for ing in meal.ingredients:
            words = ing.split()
            clean = [
                w for w in words
                if not w.replace('.','').replace('/','').replace('½','').replace('¼','').isnumeric()
                and w.lower() not in units
            ]
            name = " ".join(clean).lower().strip()
            if name and name not in seen:
                seen.add(name)
                ingredients.append(name)
    return ingredients


async def scrape_store_prices(ingredients: List[str], store: dict) -> dict:
    """
    Uses browser-use 0.1x API (BrowserSession + BrowserProfile) to scrape prices.
    """
    store_search_urls = {
        "trader joe's": "https://www.traderjoes.com/home/search?q=",
        "ralphs":        "https://www.ralphs.com/search?query=",
        "sprouts":       "https://shop.sprouts.com/search?search_term=",
        "vons":          "https://www.vons.com/shop/search-results.html?q=",
        "albertsons":    "https://www.albertsons.com/shop/search-results.html?q=",
        "walmart":       "https://www.walmart.com/search?q=",
        "target":        "https://www.target.com/s?searchTerm=",
        "whole foods":   "https://www.wholefoodsmarket.com/search?text=",
        "smart & final": "https://www.smartandfinal.com/search?q=",
        "food 4 less":   "https://www.food4less.com/search?query=",
    }

    store_name_lower = store["name"].lower()
    search_url = next(
        (url for key, url in store_search_urls.items() if key in store_name_lower),
        None
    )

    if not search_url:
        print(f"No URL known for {store['name']}, using price estimates")
        return _estimate_prices(ingredients)

    # Prioritise proteins and staples — they drive most of the cost
    priority_kws = ["chicken","beef","fish","tofu","egg","rice","pasta","bread","milk","cheese"]
    priority  = [i for i in ingredients if any(k in i for k in priority_kws)]
    rest      = [i for i in ingredients if i not in priority]
    sample    = (priority + rest)[:8]   # max 8 per store to stay fast

    task = f"""
                Visit {search_url}{sample[0].replace(' ', '+')} and find the price of "{sample[0]}".
                Then check prices for each of these items at {store['name']}:
                {', '.join(sample)}

                For each item find the cheapest available option.
                If an item is not found or needs login, estimate a reasonable grocery price.

                Return ONLY valid JSON with no explanation, like:
                {{"chicken breast": 5.99, "brown rice": 2.49, "spinach": 1.79}}
            """

    # --- 0.1x correct API ---
    browser_profile = BrowserProfile(headless=True)
    browser_session = BrowserSession(browser_profile=browser_profile)

    try:
        agent = Agent(
            task=task,
            llm=get_llm(),
            browser_session=browser_session   # pass session, not browser=
        )
        result = await agent.run(max_steps=15)

        # In 0.1x, final_result is a property, not a method
        text = result.final_result if hasattr(result, 'final_result') else str(result)

        match = re.search(r'\{[^{}]+\}', str(text), re.DOTALL)
        if match:
            scraped = json.loads(match.group())
            # Fill any missing items with estimates
            for ing in ingredients:
                if ing not in scraped:
                    scraped[ing] = _estimate_single_price(ing)
            return scraped

        return _estimate_prices(ingredients)

    except Exception as e:
        print(f"Scraping failed for {store['name']}: {e}")
        return _estimate_prices(ingredients)

    finally:
        # Always close the browser session to free memory
        try:
            await browser_session.close()
        except Exception:
            pass


def _estimate_single_price(ingredient: str) -> float:
    proteins = ["chicken","beef","pork","fish","salmon","tuna","shrimp","turkey","tofu","tempeh"]
    produce  = ["apple","banana","spinach","kale","broccoli","carrot","tomato","onion",
                "garlic","pepper","lettuce","avocado","lemon","mushroom","potato","zucchini"]
    grains   = ["rice","pasta","bread","oat","quinoa","flour","tortilla","cereal"]
    dairy    = ["milk","cheese","yogurt","butter","egg","cream"]

    ing = ingredient.lower()
    if any(p in ing for p in proteins): return round(4.99 + (hash(ingredient) % 400) / 100, 2)
    if any(p in ing for p in produce):  return round(0.99 + (hash(ingredient) % 200) / 100, 2)
    if any(p in ing for p in grains):   return round(1.99 + (hash(ingredient) % 150) / 100, 2)
    if any(p in ing for p in dairy):    return round(2.49 + (hash(ingredient) % 200) / 100, 2)
    return round(1.49 + (hash(ingredient) % 300) / 100, 2)


def _estimate_prices(ingredients: List[str]) -> dict:
    return {ing: _estimate_single_price(ing) for ing in ingredients}


def build_grocery_items(ingredients: List[str], meals: List[Meal]) -> List[GroceryItem]:
    category_map = {
        "Produce":            ["apple","banana","spinach","kale","broccoli","carrot","tomato",
                               "onion","garlic","pepper","lettuce","cucumber","zucchini","potato",
                               "sweet potato","avocado","lemon","lime","mango","berry","mushroom"],
        "Proteins":           ["chicken","beef","pork","fish","salmon","tuna","shrimp","egg",
                               "tofu","tempeh","edamame","turkey","lamb"],
        "Grains":             ["rice","pasta","bread","oat","quinoa","flour","tortilla","cereal"],
        "Dairy & Alternatives":["milk","cheese","yogurt","butter","cream","almond milk",
                                "oat milk","soy milk","cottage"],
        "Pantry":             ["oil","salt","pepper","sauce","vinegar","honey","syrup","spice",
                               "herb","broth","stock","canned","tomato paste","soy sauce","cumin"],
        "Frozen":             ["frozen"],
        "Snacks":             ["nut","almond","walnut","cashew","peanut","seed","granola"],
    }
    non_ebt = ["vitamin","supplement","alcohol","beer","wine","energy drink"]

    ing_with_qty = {}
    for meal in meals:
        for ing_str in meal.ingredients:
            for canonical in [i for cats in category_map.values() for i in cats]:
                if canonical in ing_str.lower() and canonical not in ing_with_qty:
                    ing_with_qty[canonical] = ing_str

    items = []
    for ing in ingredients:
        category = "Other"
        for cat, keywords in category_map.items():
            if any(kw in ing.lower() for kw in keywords):
                category = cat
                break
        ebt = not any(kw in ing.lower() for kw in non_ebt)
        items.append(GroceryItem(
            name=ing,
            quantity=ing_with_qty.get(ing, "as needed"),
            category=category,
            ebt_eligible=ebt
        ))
    return items

async def generate_grocery_list(
    meals: List[Meal],
    budget: float,
    location: str
):
    from models.schemas import GroceryItem, StorePrice, StoreOption

    ingredients = extract_ingredients(meals)
    nearby_stores = await find_nearby_stores(location)
    print(f"Stores near {location}: {[s['name'] for s in nearby_stores]}")

    # Scrape all stores in parallel
    all_prices = await asyncio.gather(*[
        scrape_store_prices(ingredients, store) for store in nearby_stores
    ])
    store_price_map = list(zip(nearby_stores, all_prices))

    # --- Build GroceryItems with prices array Lovable expects ---
    category_map = {
        "Produce":              ["apple","banana","spinach","kale","broccoli","carrot","tomato",
                                 "onion","garlic","pepper","lettuce","cucumber","zucchini","potato",
                                 "sweet potato","avocado","lemon","lime","mango","berry","mushroom"],
        "Proteins":             ["chicken","beef","pork","fish","salmon","tuna","shrimp","egg",
                                 "tofu","tempeh","edamame","turkey","lamb"],
        "Grains":               ["rice","pasta","bread","oat","quinoa","flour","tortilla","cereal"],
        "Dairy/Alternatives":   ["milk","cheese","yogurt","butter","cream","almond milk",
                                 "oat milk","soy milk","cottage"],
        "Pantry":               ["oil","salt","pepper","sauce","vinegar","honey","syrup","spice",
                                 "herb","broth","stock","canned","tomato paste","soy sauce","cumin"],
    }
    non_ebt = ["vitamin","supplement","alcohol","beer","wine","energy drink"]

    grocery_items = []
    for i, ing in enumerate(ingredients):
        # Find category
        category = "Other"
        for cat, keywords in category_map.items():
            if any(kw in ing.lower() for kw in keywords):
                category = cat
                break

        # Build prices array — one entry per nearby store
        prices = []
        for store, prices_dict in store_price_map:
            price = prices_dict.get(ing, _estimate_single_price(ing))
            prices.append(StorePrice(store=store["name"], price=round(price, 2)))

        ebt = not any(kw in ing.lower() for kw in non_ebt)

        # Get quantity from meal ingredients
        quantity = "as needed"
        for meal in meals:
            for meal_ing in meal.ingredients:
                if ing.lower() in meal_ing.name.lower():
                    quantity = meal_ing.amount
                    break

        grocery_items.append(GroceryItem(
            id=f"g{i+1}",
            name=ing.title(),
            quantity=quantity,
            category=category,
            prices=prices,
            ebtEligible=ebt,
            checked=False,
            alreadyHave=False
        ))

    # --- Build StoreOptions Lovable expects ---
    store_options = []

    # Single store options
    single_options = []
    for store, prices_dict in store_price_map:
        total = round(sum(prices_dict.values()), 2)
        single_options.append({
            "label": f"{store['name']} only",
            "stores": [store["name"]],
            "total_cost": total,
            "prices": prices_dict
        })

    # Two-store combo options
    combo_options = []
    for i in range(len(store_price_map)):
        for j in range(i + 1, len(store_price_map)):
            store_a, prices_a = store_price_map[i]
            store_b, prices_b = store_price_map[j]
            combo_total = round(sum(
                min(prices_a.get(ing, 999), prices_b.get(ing, 999))
                for ing in ingredients
            ), 2)
            combo_options.append({
                "label": f"{store_a['name']} + {store_b['name']}",
                "stores": [store_a["name"], store_b["name"]],
                "total_cost": combo_total,
                "prices": {}
            })

    all_options = sorted(single_options + combo_options, key=lambda x: x["total_cost"])

    final_options = [
        StoreOption(
            label=opt["label"],
            stores=opt["stores"],
            total_cost=opt["total_cost"],
            is_best_value=(i == 0)
        )
        for i, opt in enumerate(all_options)
    ]

    estimated_total = min(opt.total_cost for opt in final_options) if final_options else 0.0

    return grocery_items, final_options, estimated_total