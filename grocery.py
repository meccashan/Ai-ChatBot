import requests
import re
import os
import base64
from datetime import datetime
from google import genai
from google.genai import types

# Replace with your Spoonacular API key
SPOONACULAR_API_KEY = "7349df0f8e3e45d49294fecf92ed56de"
SPOONACULAR_API_URL = "https://api.spoonacular.com/recipes"

# Set Gemini API key - make sure to store this securely in production
os.environ["GEMINI_API_KEY"] = "AIzaSyDW-L9Wr_pUpx-cEO93oA4bhJliS6Kxqkk"

# In-memory storage for the grocery list
grocery_list = {}
# In-memory storage for available ingredients (pantry)
pantry_items = {}

def get_recipe_ingredients(food_item, servings):
    """Get the list of ingredients for a given food item and servings."""
    url = f"{SPOONACULAR_API_URL}/complexSearch"
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "query": food_item,
        "number": 1,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        recipes = response.json()["results"]
        if recipes:
            recipe_id = recipes[0]["id"]
            recipe_image = recipes[0].get("image", None)
            
            url = f"{SPOONACULAR_API_URL}/{recipe_id}/information"
            params = {"apiKey": SPOONACULAR_API_KEY}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                recipe_details = response.json()
                if "servings" in recipe_details:
                    recipe_servings = recipe_details["servings"]
                    ingredients = recipe_details["extendedIngredients"]
                    scaled_ingredients = []
                    for ingredient in ingredients:
                        name = ingredient["name"]
                        amount = ingredient["amount"]
                        unit = ingredient["unit"]
                        image = f"https://spoonacular.com/cdn/ingredients_100x100/{ingredient['image']}" if ingredient.get('image') else None
                        scaled_amount = (amount / recipe_servings) * servings
                        scaled_ingredients.append({
                            "name": name,
                            "amount": scaled_amount,
                            "unit": unit,
                            "image": image
                        })
                    return scaled_ingredients, recipe_details["title"], recipe_image
    return None, None, None

def get_ingredient_image(ingredient_name):
    """Helper function to get image URL for an ingredient"""
    try:
        url = f"{SPOONACULAR_API_URL}/food/ingredients/search"
        params = {
            "apiKey": SPOONACULAR_API_KEY,
            "query": ingredient_name,
            "number": 1
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results and "image" in results[0]:
                return f"https://spoonacular.com/cdn/ingredients_100x100/{results[0]['image']}"
    except Exception as e:
        print(f"Error fetching image for {ingredient_name}: {e}")
    return None

def add_ingredients_to_grocery_list(ingredients):
    """Add ingredients to the grocery list, considering what's already in the pantry."""
    added_items = []
    for ingredient in ingredients:
        item = ingredient["name"]
        amount = ingredient["amount"]
        unit = ingredient["unit"]
        
        # Check if the item is already in the pantry
        if item in pantry_items:
            # If we have enough, don't add to grocery list
            if pantry_items[item]["amount"] >= amount:
                pantry_items[item]["amount"] -= amount
                if pantry_items[item]["amount"] <= 0:
                    del pantry_items[item]
                continue
            else:
                # If we have some but not enough
                amount_needed = amount - pantry_items[item]["amount"]
                del pantry_items[item]
        else:
            amount_needed = amount
            
        # Add to grocery list
        if item in grocery_list:
            grocery_list[item]["amount"] += amount_needed
        else:
            grocery_list[item] = {
                "amount": amount_needed,
                "unit": unit
            }
        added_items.append(f"{amount_needed:.2f} {unit} of {item}")
    
    return added_items

def show_grocery_list():
    """Display the final grocery list."""
    if not grocery_list:
        return "Your grocery list is empty."
    
    result = "\nGrocery List:"
    for item, details in grocery_list.items():
        amount = details["amount"]
        unit = details["unit"]
        result += f"\n- {item.capitalize()}: {amount:.2f} {unit}"
    
    return result

def show_pantry():
    """Display the current pantry items."""
    if not pantry_items:
        return "Your pantry is empty."
    
    result = "\nPantry Items:"
    for item, details in pantry_items.items():
        amount = details["amount"]
        unit = details["unit"]
        result += f"\n- {item.capitalize()}: {amount:.2f} {unit}"
    
    return result

def add_to_pantry(item, amount, unit):
    """Add an item to the pantry."""
    if item in pantry_items:
        # If the units match, add to existing amount
        if pantry_items[item]["unit"] == unit:
            pantry_items[item]["amount"] += amount
        else:
            # If units don't match, convert or keep separate (simplified approach)
            pantry_items[item] = {
                "amount": amount,
                "unit": unit
            }
    else:
        pantry_items[item] = {
            "amount": amount,
            "unit": unit
        }

def remove_from_grocery_list(item, amount=None):
    """Remove an item from the grocery list."""
    if item in grocery_list:
        if amount is None or amount >= grocery_list[item]["amount"]:
            del grocery_list[item]
            return f"Removed {item} from your grocery list."
        else:
            grocery_list[item]["amount"] -= amount
            return f"Reduced {item} by {amount} {grocery_list[item]['unit']}."
    else:
        return f"{item} is not in your grocery list."

def save_grocery_list(filename="grocery_list.txt"):
    """Save the grocery list to a file."""
    with open(filename, "w") as f:
        f.write(f"Grocery List - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("="*40 + "\n")
        for item, details in grocery_list.items():
            amount = details["amount"]
            unit = details["unit"]
            f.write(f"{item.capitalize()}: {amount:.2f} {unit}\n")
    return f"Grocery list saved to {filename}"

def process_natural_language(user_input):
    """Process natural language input and determine the user's intent (backup method)."""
    user_input = user_input.lower()
    
    # Define pattern matching for common intents
    add_recipe_patterns = [
        r"(make|cook|prepare|add recipe for|recipe for) (.*?)(?: for (\d+) people)?$",
        r"i want to (make|cook|prepare) (.*?)(?: for (\d+) people)?$",
        r"how do i (make|cook|prepare) (.*?)(?: for (\d+) people)?$"
    ]
    
    add_item_patterns = [
        r"add (.*?) to (grocery list|list)",
        r"i need (.*)",
        r"buy (.*)",
        r"get (.*) from (store|shop|market)"
    ]
    
    add_pantry_patterns = [
        r"i have (.*)",
        r"add (.*) to pantry",
        r"already have (.*)"
    ]
    
    remove_patterns = [
        r"remove (.*) from (grocery list|list)",
        r"delete (.*) from (grocery list|list)",
        r"don't need (.*)"
    ]
    
    # Check for recipe patterns
    for pattern in add_recipe_patterns:
        match = re.search(pattern, user_input)
        if match:
            food_item = match.group(2).strip()
            servings = 2  # Default
            if match.group(3):
                servings = int(match.group(3))
            return {"intent": "add_recipe", "food_item": food_item, "servings": servings}
    
    # Check for add item to grocery list patterns
    for pattern in add_item_patterns:
        match = re.search(pattern, user_input)
        if match:
            item = match.group(1).strip()
            # Extract quantity if present
            quantity_match = re.search(r"(\d+\.?\d*)\s*(oz|lb|kg|g|cups?|tbsp|tsp|ml|l) of (.*)", item)
            if quantity_match:
                amount = float(quantity_match.group(1))
                unit = quantity_match.group(2)
                item = quantity_match.group(3)
                return {"intent": "add_item", "item": item, "amount": amount, "unit": unit}
            else:
                return {"intent": "add_item", "item": item, "amount": 1, "unit": "unit"}
    
    # Check for add to pantry patterns
    for pattern in add_pantry_patterns:
        match = re.search(pattern, user_input)
        if match:
            item = match.group(1).strip()
            # Extract quantity if present
            quantity_match = re.search(r"(\d+\.?\d*)\s*(oz|lb|kg|g|cups?|tbsp|tsp|ml|l) of (.*)", item)
            if quantity_match:
                amount = float(quantity_match.group(1))
                unit = quantity_match.group(2)
                item = quantity_match.group(3)
                return {"intent": "add_pantry", "item": item, "amount": amount, "unit": unit}
            else:
                return {"intent": "add_pantry", "item": item, "amount": 1, "unit": "unit"}
    
    # Check for remove patterns
    for pattern in remove_patterns:
        match = re.search(pattern, user_input)
        if match:
            item = match.group(1).strip()
            return {"intent": "remove_item", "item": item}
    
    # Check for view list/pantry intents
    if any(phrase in user_input for phrase in ["show list", "view list", "what's on my list", "what is on my list", "grocery list"]):
        return {"intent": "show_list"}
    
    if any(phrase in user_input for phrase in ["show pantry", "view pantry", "what's in my pantry", "what do i have"]):
        return {"intent": "show_pantry"}
    
    if any(phrase in user_input for phrase in ["save list", "export list", "download list"]):
        return {"intent": "save_list"}
    
    if any(phrase in user_input for phrase in ["exit", "quit", "goodbye", "bye", "thank you", "thanks"]):
        return {"intent": "exit"}
    
    # If no pattern matches
    return {"intent": "unknown"}

def gemini_nlp_analysis(user_input):
    """
    Use Gemini API for NLP analysis of user input.
    Returns structured intent and entities.
    """
    try:
        # Initialize Gemini client
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        model = "gemini-2.5-pro-exp-03-25"
        
        # Craft a prompt that instructs Gemini to extract intents and entities
        system_prompt = """
        You are a grocery assistant AI. Parse the user input and extract the following information:
        1. Intent: One of [add_recipe, add_item, add_pantry, remove_item, show_list, show_pantry, save_list, exit, unknown]
        2. Entities: Depending on the intent, extract relevant entities like food_item, servings, item, amount, unit
        
        Return the result as a JSON object with the format:
        {"intent": "intent_type", "entities": {...}}
        
        Examples:
        Input: "I want to make pasta for 4 people"
        Output: {"intent": "add_recipe", "food_item": "pasta", "servings": 4}
        
        Input: "I need 2 cups of flour"
        Output: {"intent": "add_item", "item": "flour", "amount": 2, "unit": "cups"}
        
        Input: "I have 3 onions in my pantry"
        Output: {"intent": "add_pantry", "item": "onions", "amount": 3, "unit": "unit"}
        """
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"{system_prompt}\n\nUser input: {user_input}"),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
        )
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Try to parse the response as a JSON object
        try:
            import json
            # Extract the JSON part from the response
            response_text = response.text
            # Find JSON-like structure in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                
                # Handle the response format to ensure compatibility with our existing code
                intent = result.get("intent", "unknown")
                
                # Build a response that matches our expected format
                nlp_result = {"intent": intent}
                
                # Add all other keys from the result
                for key, value in result.items():
                    if key != "intent":
                        nlp_result[key] = value
                
                # If there's an "entities" key, flatten it
                if "entities" in result:
                    for entity_key, entity_value in result["entities"].items():
                        nlp_result[entity_key] = entity_value
                    
                    # Remove the entities key
                    if "entities" in nlp_result:
                        del nlp_result["entities"]
                
                return nlp_result
            else:
                print("Warning: Could not find JSON in Gemini response")
                return process_natural_language(user_input)  # Fall back to regex
        except json.JSONDecodeError:
            print("Warning: Could not parse Gemini response as JSON")
            return process_natural_language(user_input)  # Fall back to regex
            
    except Exception as e:
        print(f"Error using Gemini API: {e}")
        # Fallback to the basic pattern matching if Gemini API fails
        return process_natural_language(user_input)

def run_nlp_chatbot():
    """Run the grocery chatbot with NLP capabilities powered by Gemini."""
    print("Welcome to the Gemini-Powered Grocery AI Chatbot!")
    print("You can tell me naturally what you want to do. For example:")
    print("- 'I want to make lasagna for 6 people'")
    print("- 'Add 2 cups of sugar to my grocery list'")
    print("- 'I already have 3 onions in my pantry'")
    print("- 'Show me my grocery list'")
    print("- 'Remove milk from my list'")
    
    while True:
        user_input = input("\nHow can I help with your grocery needs? (Type 'exit' to quit): ")
        
        # Process the user input with Gemini NLP
        nlp_result = gemini_nlp_analysis(user_input)
        
        # Debug info
        # print(f"DEBUG: NLP Result: {nlp_result}")
        
        if nlp_result["intent"] == "add_recipe":
            food_item = nlp_result.get("food_item", "")
            servings = nlp_result.get("servings", 2)
            print(f"Finding a recipe for {food_item} (servings: {servings})...")
            
            ingredients, recipe_title = get_recipe_ingredients(food_item, servings)
            if ingredients:
                print(f"\nFound recipe: {recipe_title}")
                print(f"Ingredients required for {recipe_title} (servings: {servings}):")
                for ingredient in ingredients:
                    print(f"- {ingredient['amount']:.2f} {ingredient['unit']} of {ingredient['name']}")
                
                added_items = add_ingredients_to_grocery_list(ingredients)
                if added_items:
                    print("\nAdded to grocery list:")
                    for item in added_items:
                        print(f"- {item}")
                else:
                    print("\nAll ingredients were already in your pantry. Nothing added to grocery list.")
            else:
                print(f"Could not find a recipe for {food_item}.")
        
        elif nlp_result["intent"] == "add_item":
            item = nlp_result.get("item", "")
            amount = nlp_result.get("amount", 1)
            unit = nlp_result.get("unit", "unit")
            
            if item in grocery_list:
                grocery_list[item]["amount"] += amount
                print(f"Added more {item} to your grocery list. Now you need {grocery_list[item]['amount']:.2f} {grocery_list[item]['unit']}.")
            else:
                grocery_list[item] = {"amount": amount, "unit": unit}
                print(f"Added {amount} {unit} of {item} to your grocery list.")
        
        elif nlp_result["intent"] == "add_pantry":
            item = nlp_result.get("item", "")
            amount = nlp_result.get("amount", 1)
            unit = nlp_result.get("unit", "unit")
            
            add_to_pantry(item, amount, unit)
            print(f"Added {amount} {unit} of {item} to your pantry.")
            
            # Check if this item is on the grocery list and update if necessary
            if item in grocery_list:
                if grocery_list[item]["unit"] == unit:
                    if grocery_list[item]["amount"] <= amount:
                        del grocery_list[item]
                        print(f"Removed {item} from your grocery list since you now have it in your pantry.")
                    else:
                        grocery_list[item]["amount"] -= amount
                        print(f"Updated grocery list: now you need {grocery_list[item]['amount']:.2f} {unit} of {item}.")
        
        elif nlp_result["intent"] == "remove_item":
            item = nlp_result.get("item", "")
            amount = nlp_result.get("amount", None)
            result = remove_from_grocery_list(item, amount)
            print(result)
        
        elif nlp_result["intent"] == "show_list":
            result = show_grocery_list()
            print(result)
        
        elif nlp_result["intent"] == "show_pantry":
            result = show_pantry()
            print(result)
        
        elif nlp_result["intent"] == "save_list":
            result = save_grocery_list()
            print(result)
        
        elif nlp_result["intent"] == "exit":
            print("Thank you for using the Grocery AI Chatbot! Goodbye!")
            break
        
        elif nlp_result["intent"] == "unknown":
            print("I'm not sure what you want to do. Try asking me to add a recipe, add items to your list or pantry, or view your lists.")

if __name__ == "__main__":
    run_nlp_chatbot()
