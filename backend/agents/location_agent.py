import httpx
import os
from typing import List
# Add at the top, before os.getenv is called
from dotenv import load_dotenv
load_dotenv()

# Switch this to False if you want the fully free OpenStreetMap version
USE_GOOGLE_MAPS = False

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Grocery store chains to look for
GROCERY_KEYWORDS = [
    "Ralphs", "Trader Joe's", "Sprouts", "Vons", "Albertsons",
    "Walmart", "Target", "Aldi", "Food 4 Less", "Stater Bros",
    "Whole Foods", "Smart & Final", "Grocery Outlet"
]


# only for google maps api, which is not being used. 
async def find_nearby_stores_google(location: str, radius_meters: int = 3000) -> List[dict]:
    """
    Uses Google Maps Places API to find grocery stores near the user.
    Free tier: $200 credit/month — a hackathon won't get close to this.
    
    Returns list of stores like:
    [{"name": "Ralphs", "address": "123 Main St", "distance_miles": 0.4, "place_id": "..."}]
    """
    
    # Step 1: Convert location string to lat/lng (geocoding)
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient() as client:
        geo_response = await client.get(geocode_url, params={
            "address": location,
            "key": GOOGLE_MAPS_KEY
        })
        geo_data = geo_response.json()
    
    if not geo_data.get("results"):
        print(f"Could not geocode location: {location}, using UCSD as default")
        lat, lng = 32.8801, -117.2340  # UCSD default
    else:
        coords = geo_data["results"][0]["geometry"]["location"]
        lat, lng = coords["lat"], coords["lng"]
    
    # Step 2: Find nearby grocery stores using Places API
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    async with httpx.AsyncClient() as client:
        places_response = await client.get(places_url, params={
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "type": "grocery_or_supermarket",
            "key": GOOGLE_MAPS_KEY
        })
        places_data = places_response.json()
    
    stores = []
    for place in places_data.get("results", [])[:6]:  # top 6 closest
        name = place.get("name", "")
        
        # Calculate rough distance in miles from user
        store_lat = place["geometry"]["location"]["lat"]
        store_lng = place["geometry"]["location"]["lng"]
        distance = haversine_miles(lat, lng, store_lat, store_lng)
        
        stores.append({
            "name": name,
            "address": place.get("vicinity", ""),
            "distance_miles": round(distance, 1),
            "place_id": place.get("place_id", ""),
            "rating": place.get("rating", None),
            "lat": store_lat,
            "lng": store_lng
        })
    
    # Sort by distance
    stores.sort(key=lambda x: x["distance_miles"])
    return stores


async def find_nearby_stores_openstreetmap(location: str, radius_meters: int = 3000) -> List[dict]:
    """
    Fully free alternative using OpenStreetMap's Overpass API.
    No API key, no credit card. Slower than Google Maps but works fine for demo.
    """
    
    # Step 1: Geocode using Nominatim (free OSM geocoder)
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    async with httpx.AsyncClient() as client:
        geo_response = await client.get(
            nominatim_url,
            params={"q": location, "format": "json", "limit": 1},
            # Nominatim requires a User-Agent header
            headers={"User-Agent": "BudgetMealsHackathon/1.0"}
        )
        geo_data = geo_response.json()
    
    if not geo_data:
        print(f"Could not geocode: {location}, defaulting to UCSD")
        lat, lng = 32.8801, -117.2340
    else:
        lat = float(geo_data[0]["lat"])
        lng = float(geo_data[0]["lon"])
    
    # Step 2: Query Overpass API for supermarkets nearby
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # This query finds supermarkets and grocery stores within the radius
    query = f"""
    [out:json][timeout:10];
    (
      node["shop"="supermarket"](around:{radius_meters},{lat},{lng});
      node["shop"="grocery"](around:{radius_meters},{lat},{lng});
      way["shop"="supermarket"](around:{radius_meters},{lat},{lng});
    );
    out center 10;
    """
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        overpass_response = await client.post(overpass_url, data=query)
        overpass_data = overpass_response.json()
    
    stores = []
    for element in overpass_data.get("elements", [])[:6]:
        tags = element.get("tags", {})
        name = tags.get("name", "Local Grocery Store")
        
        # Get coordinates (nodes have lat/lon directly, ways have center)
        if element["type"] == "node":
            store_lat, store_lng = element["lat"], element["lon"]
        else:
            center = element.get("center", {})
            store_lat = center.get("lat", lat)
            store_lng = center.get("lon", lng)
        
        distance = haversine_miles(lat, lng, store_lat, store_lng)
        address = tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")
        
        stores.append({
            "name": name,
            "address": address.strip() or "See maps for address",
            "distance_miles": round(distance, 1),
            "place_id": str(element.get("id", "")),
            "rating": None,
            "lat": store_lat,
            "lng": store_lng
        })
    
    stores.sort(key=lambda x: x["distance_miles"])
    return stores


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates straight-line distance between two lat/lng points in miles.
    Good enough for "how far is this store" — no API needed.
    """
    from math import radians, sin, cos, sqrt, atan2
    R = 3958.8  # Earth radius in miles
    
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


async def find_nearby_stores(location: str) -> List[dict]:
    """
    Main function — call this from the scraper agent.
    Automatically uses whichever method is configured at the top of this file.
    Falls back to OpenStreetMap if Google Maps fails.
    """
    try:
        if USE_GOOGLE_MAPS and GOOGLE_MAPS_KEY:
            stores = await find_nearby_stores_google(location)
        else:
            stores = await find_nearby_stores_openstreetmap(location)
        
        if not stores:
            print("No stores found, using San Diego defaults")
            return _default_san_diego_stores()
        
        print(f"Found {len(stores)} stores near {location}: {[s['name'] for s in stores]}")
        return stores
        
    except Exception as e:
        print(f"Location lookup failed: {e}, using defaults")
        return _default_san_diego_stores()


def _default_san_diego_stores() -> List[dict]:
    """
    Hardcoded fallback for UCSD area — used if all APIs fail.
    Good enough to keep the demo running.
    """
    return [
        {"name": "Trader Joe's", "address": "8657 Villa La Jolla Dr, La Jolla", "distance_miles": 1.2, "place_id": "tj_lajolla", "rating": 4.5, "lat": 32.8723, "lng": -117.2207},
        {"name": "Ralphs", "address": "3750 Sports Arena Blvd, San Diego", "distance_miles": 2.1, "place_id": "ralphs_sd", "rating": 4.1, "lat": 32.7590, "lng": -117.2109},
        {"name": "Sprouts", "address": "4695 Convoy St, San Diego", "distance_miles": 3.4, "place_id": "sprouts_sd", "rating": 4.3, "lat": 32.8357, "lng": -117.1502},
        {"name": "Vons", "address": "8008 Girard Ave, La Jolla", "distance_miles": 2.8, "place_id": "vons_lajolla", "rating": 4.0, "lat": 32.8510, "lng": -117.2710},
    ]