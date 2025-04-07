# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from grocery import (get_recipe_ingredients, add_ingredients_to_grocery_list,
                    show_grocery_list, show_pantry, add_to_pantry,
                    remove_from_grocery_list, save_grocery_list,
                    gemini_nlp_analysis, grocery_list, pantry_items,
                    get_ingredient_image)


SPOONACULAR_API_KEY = "7349df0f8e3e45d49294fecf92ed56de"
SPOONACULAR_API_URL = "https://api.spoonacular.com/recipes"


app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes

@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '').strip()
    if not user_input:
        return jsonify({"error": "Empty message"}), 400
    
    nlp_result = gemini_nlp_analysis(user_input)
    
    response = {
        "intent": nlp_result["intent"],
        "text": "",
        "products": [],
        "productsTitle": "",
        "recipe_image": None,
        "ingredients": []
    }
    
    if nlp_result["intent"] == "add_recipe":
        food_item = nlp_result.get("food_item", "")
        servings = nlp_result.get("servings", 2)
        ingredients, recipe_title, recipe_image = get_recipe_ingredients(food_item, servings)
        
        if ingredients:
            response["text"] = f"Found recipe: {recipe_title}\nIngredients required for {servings} servings:"
            response["recipe_image"] = recipe_image
            response["recipe_title"] = recipe_title
            
            for ingredient in ingredients:
                response["ingredients"].append({
                    "name": ingredient["name"],
                    "amount": ingredient["amount"],
                    "unit": ingredient["unit"],
                    "image": ingredient.get("image")
                })
                response["text"] += f"\n- {ingredient['amount']:.2f} {ingredient['unit']} of {ingredient['name']}"
            
            added_items = add_ingredients_to_grocery_list(ingredients)
            if added_items:
                response["text"] += "\n\nAdded to grocery list:"
                for item in added_items:
                    response["text"] += f"\n- {item}"
    
    elif nlp_result["intent"] == "add_item":
        item = nlp_result.get("item", "")
        amount = nlp_result.get("amount", 1)
        unit = nlp_result.get("unit", "unit")
        
        image_url = get_ingredient_image(item)  # Use the imported function
        
        if item in grocery_list:
            grocery_list[item]["amount"] += amount
            if image_url and "image" not in grocery_list[item]:
                grocery_list[item]["image"] = image_url
            response["text"] = f"Added more {item} to your grocery list."
        else:
            grocery_list[item] = {
                "amount": amount, 
                "unit": unit,
                "image": image_url
            }
            response["text"] = f"Added {amount} {unit} of {item} to your grocery list."
        
        response["products"].append({
            "name": item,
            "amount": amount,
            "unit": unit,
            "image": image_url
        })
    
    elif nlp_result["intent"] == "add_pantry":
        item = nlp_result.get("item", "")
        amount = nlp_result.get("amount", 1)
        unit = nlp_result.get("unit", "unit")
        
        add_to_pantry(item, amount, unit)
        response["text"] = f"Added {amount} {unit} of {item} to your pantry."
        
        if item in grocery_list:
            if grocery_list[item]["unit"] == unit:
                if grocery_list[item]["amount"] <= amount:
                    del grocery_list[item]
                    response["text"] += f"\nRemoved {item} from your grocery list since you now have it in your pantry."
                else:
                    grocery_list[item]["amount"] -= amount
                    response["text"] += f"\nUpdated grocery list: now you need {grocery_list[item]['amount']:.2f} {unit} of {item}."
    
    elif nlp_result["intent"] == "remove_item":
        item = nlp_result.get("item", "")
        amount = nlp_result.get("amount", None)
        response["text"] = remove_from_grocery_list(item, amount)
    
    elif nlp_result["intent"] == "show_list":
        response["text"] = show_grocery_list()
        # Add all grocery list items to products array for frontend display
        for item, details in grocery_list.items():
            response["products"].append({
                "name": item,
                "amount": details["amount"],
                "unit": details["unit"],
                "image": details.get("image", None)
            })
        response["productsTitle"] = "Your Grocery List"
    
    elif nlp_result["intent"] == "show_pantry":
        response["text"] = show_pantry()
    
    elif nlp_result["intent"] == "save_list":
        response["text"] = save_grocery_list()
    
    elif nlp_result["intent"] == "exit":
        response["text"] = "Thank you for using the Grocery AI Chatbot! Goodbye!"
    
    return jsonify(response)


@app.route('/api/grocery-list', methods=['GET'])
def get_grocery_list():
    return jsonify(grocery_list)

@app.route('/api/pantry', methods=['GET'])
def get_pantry():
    return jsonify(pantry_items)

@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    item_data = request.json
    item = item_data.get('item', '')
    amount = item_data.get('amount', 1)
    unit = item_data.get('unit', 'unit')
    
    if item in grocery_list:
        grocery_list[item]["amount"] += amount
    else:
        grocery_list[item] = {"amount": amount, "unit": unit}
    
    return jsonify({"status": "success", "grocery_list": grocery_list})

@app.route('/api/clear-list', methods=['POST'])
def clear_list():
    global grocery_list
    grocery_list = {}
    return jsonify({"status": "success", "message": "Grocery list cleared"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)