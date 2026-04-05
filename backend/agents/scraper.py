"""
GROCERY PRICE SCRAPER AGENT
=============================
Uses the browser-use Cloud SDK to scrape live grocery prices.
No OpenAI or Anthropic key needed — browser-use runs its own model.
 
HOW IT WORKS:
  1. Receives a GroceryRequest message (items + zip code)
  2. For each store, calls browser_use_sdk with a natural language task
  3. browser-use Cloud spins up a stealth browser, navigates the site,
     finds prices, and returns structured JSON
  4. Results are saved to grocery_prices.json
  5. Sends PriceSearchComplete to the optimizer agent
 
SETUP:
  pip install uagents browser-use-sdk python-dotenv
 
ENV VARS (.env):
  BROWSER_USE_API_KEY=bu-...     ← from cloud.browser-use.com/settings
  OPTIMIZER_AGENT_ADDRESS=agent1q...
  SCRAPER_SEED=any-phrase-you-like
"""

import json
import asyncio
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
 
from browser_use_sdk import AsyncBrowserUse   # pip install browser-use-sdk
from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
 
load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
 
PRICE_DB_PATH = Path("grocery_prices.json")
OPTIMIZER_ADDRESS = os.getenv("OPTIMIZER_AGENT_ADDRESS", "")
 
STORES = [
    {
        "name": "Walmart",
        "search_url": "https://www.walmart.com/search?q={item}&cat_id=976759",
    },
    {
        "name": "Kroger",
        "search_url": "https://www.kroger.com/search?query={item}",
    },
    {
        "name": "Whole Foods",
        "search_url": "https://www.wholefoodsmarket.com/search?text={item}",
    },
    {
        "name": "Target",
        "search_url": "https://www.target.com/s?searchTerm={item}&category=5xt1a",
    },
]

# ─── Message Models ───────────────────────────────────────────────────────────
 
class GroceryRequest(Model):
    items: list[str]      # ["milk", "eggs", "bread"]
    zip_code: str         # "92101"
    request_id: str       # unique short ID
 
class PriceSearchComplete(Model):
    request_id: str
    db_path: str
    item_count: int
    store_count: int
    timestamp: str

# ─── Database Helpers ─────────────────────────────────────────────────────────
 
def load_db() -> dict:
    if PRICE_DB_PATH.exists():
        with open(PRICE_DB_PATH) as f:
            return json.load(f)
    return {"sessions": {}}
 
def save_db(db: dict):
    with open(PRICE_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
 
def init_session(request_id: str, items: list[str], zip_code: str):
    db = load_db()
    db["sessions"][request_id] = {
        "request_id": request_id,
        "zip_code": zip_code,
        "items_requested": items,
        "created_at": datetime.now().isoformat(),
        "status": "searching",
        "stores": {}
    }
    save_db(db)
 
def save_store_prices(request_id: str, store_name: str, prices: dict):
    db = load_db()
    db["sessions"][request_id]["stores"][store_name] = {
        "scraped_at": datetime.now().isoformat(),
        "prices": prices
    }
    save_db(db)
 
def finalize_session(request_id: str):
    db = load_db()
    db["sessions"][request_id]["status"] = "complete"
    save_db(db)
 
# ─── browser-use Cloud Scraping ───────────────────────────────────────────────
 
async def scrape_store(store: dict, items: list[str], zip_code: str) -> dict:
    """
    Sends a natural-language task to browser-use Cloud.
    Their infrastructure handles the browser, stealth, CAPTCHA, and model.
    Returns a dict of { item_name: { price, brand, unit, in_stock, url } }
    """
    items_list = "\n".join(f"- {item}" for item in items)
    first_url = store["search_url"].format(item=items[0].replace(" ", "+"))
 
    task = f"""
Go to {store['name']}'s website and find grocery prices.
 
Start here: {first_url}
 
Steps:
1. If asked for a location or zip code, enter: {zip_code}
2. Dismiss any popups, cookie banners, or location prompts.
3. For EACH item in this list, search the site and find the CHEAPEST available option:
 
{items_list}
 
4. Return ONLY a valid JSON object — no markdown, no explanation — like this:
 
{{
  "milk": {{
    "price": 3.49,
    "brand": "Great Value",
    "unit": "1 gallon",
    "name": "Great Value Whole Milk 1 Gallon",
    "in_stock": true,
    "url": "https://www.walmart.com/ip/..."
  }},
  "eggs": {{
    "price": 3.98,
    "brand": "Great Value",
    "unit": "12 count",
    "name": "Great Value Large White Eggs 12 Count",
    "in_stock": true,
    "url": "https://www.walmart.com/ip/..."
  }}
}}
 
Use null for any item you cannot find. Output ONLY the JSON object, nothing else.
"""
 
    client = AsyncBrowserUse()  # picks up BROWSER_USE_API_KEY from env automatically
 
    try:
        result = await client.run(task)
        raw = result.output.strip()
 
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
 
        return json.loads(raw)
 
    except json.JSONDecodeError as e:
        print(f"  [{store['name']}] JSON parse error: {e}")
        print(f"  Raw output was: {result.output[:300]}")
        return {}
    except Exception as e:
        print(f"  [{store['name']}] Error: {e}")
        return {}
 
 
async def scrape_all_stores(request_id: str, items: list[str], zip_code: str, ctx: Context) -> int:
    """
    Scrapes stores sequentially to be polite and avoid rate limits.
    Each browser-use Cloud call is independent and stateless.
    """
    successful = 0
 
    for store in STORES:
        ctx.logger.info(f"[{request_id}] 🌐 Scraping {store['name']}...")
        prices = await scrape_store(store, items, zip_code)
 
        if prices:
            save_store_prices(request_id, store["name"], prices)
            found = sum(1 for v in prices.values() if v is not None)
            ctx.logger.info(f"[{request_id}] ✅ {store['name']}: {found}/{len(items)} items found")
            successful += 1
        else:
            ctx.logger.warning(f"[{request_id}] ⚠️  {store['name']}: no data returned")
 
        # Small delay between stores — not required but polite
        await asyncio.sleep(2)
 
    return successful
 
# ─── uAgent ───────────────────────────────────────────────────────────────────
 
scraper = Agent(
    name="grocery_price_scraper",
    seed=os.getenv("SCRAPER_SEED", "grocery-scraper-seed-phrase-change-me"),
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=True,
)
 
fund_agent_if_low(scraper.wallet.address())
 
@scraper.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("🛒 Grocery Scraper Agent ready  (browser-use Cloud)")
    ctx.logger.info(f"   Address  : {scraper.address}")
    ctx.logger.info(f"   Stores   : {[s['name'] for s in STORES]}")
    ctx.logger.info(f"   Optimizer: {OPTIMIZER_ADDRESS or '⚠️  NOT SET — add OPTIMIZER_AGENT_ADDRESS to .env'}")
    if not os.getenv("BROWSER_USE_API_KEY"):
        ctx.logger.error("   ❌ BROWSER_USE_API_KEY not set! Get one at cloud.browser-use.com/settings")
 
@scraper.on_message(model=GroceryRequest)
async def handle_request(ctx: Context, sender: str, msg: GroceryRequest):
    ctx.logger.info(f"📋 Request [{msg.request_id}]: {msg.items} @ zip {msg.zip_code}")
 
    init_session(msg.request_id, msg.items, msg.zip_code)
    store_count = await scrape_all_stores(msg.request_id, msg.items, msg.zip_code, ctx)
    finalize_session(msg.request_id)
 
    ctx.logger.info(f"[{msg.request_id}] 🏁 Done — {store_count}/{len(STORES)} stores scraped")
 
    if OPTIMIZER_ADDRESS:
        await ctx.send(OPTIMIZER_ADDRESS, PriceSearchComplete(
            request_id=msg.request_id,
            db_path=str(PRICE_DB_PATH.absolute()),
            item_count=len(msg.items),
            store_count=store_count,
            timestamp=datetime.now().isoformat(),
        ))
        ctx.logger.info(f"📨 Notified optimizer agent")
    else:
        ctx.logger.warning("Optimizer not notified — set OPTIMIZER_AGENT_ADDRESS in .env")
 
if __name__ == "__main__":
    scraper.run()
 


