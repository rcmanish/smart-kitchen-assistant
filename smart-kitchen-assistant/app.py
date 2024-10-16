import streamlit as st
from PIL import Image
import io
import base64
import os
from dotenv import load_dotenv
import google.generativeai as genai
import hashlib
import pandas as pd
from fpdf import FPDF
import urllib.parse
from amazon_paapi import AmazonApi
import datetime

# Load environment variables
load_dotenv()

# Set up Google Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Set up the model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
}
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

# Set page config
st.set_page_config(page_title="smart-kitchen-assistant", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    /* Light mode background */
    .main .block-container {
        padding: 2rem;
        background-color: #EFF6FB;  /* Light background */
        border-radius: 12px;
    }

    /* Dark mode background */
    body[data-theme="dark"] .main .block-container {
        background-color: #EAE7DC;  /* Dark background */
    }

    /* Headings */
    h1, h2, h3 {
        color: #A8D0E6;  /* Heading color for light mode */
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
    }

    body[data-theme="dark"] h1, 
    body[data-theme="dark"] h2, 
    body[data-theme="dark"] h3 {
        color: #8E8D8A;  /* Heading color for dark mode */
    }

    /* General text styling */
    .main p, .main li {
        color: #A8D0E6;  /* Text color for light mode */
        font-family: 'Poppins', sans-serif;
    }

    body[data-theme="dark"] .main p, 
    body[data-theme="dark"] .main li {
        color: #8E8D8A;  /* Text color for dark mode */
    }

    /* Buttons in light mode */
    .stButton>button {
        border-radius: 30px;
        font-weight: bold;
        background-color: #A8D0E6;  /* Button background for light mode */
        color: #24305E;  /* Button text color for light mode */
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        border: none;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .stButton>button:hover {
        background-color: #EFF6FB;  /* Hover color similar to white */
        color: #24305E;  /* Hover text color */
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }

    /* Buttons in dark mode */
    body[data-theme="dark"] .stButton>button {
        background-color: #E85A4F;  /* Button background for dark mode */
        color: white;  /* Button text color for dark mode */
    }

    body[data-theme="dark"] .stButton>button:hover {
        background-color: #E98074;  /* Hover color for dark mode */
        color: white;  /* Hover text color */
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }

    /* Recipe Container Styling for light mode */
    .recipe-container {
        background-color: #24305E;  /* Light mode background */
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        color: #A8D0E6;  /* Text color for light mode */
    }

    /* Recipe Container Styling for dark mode */
    body[data-theme="dark"] .recipe-container {
        background-color: #EAE7DC;  /* Dark mode background */
        color: #8E8D8A;  /* Text color for dark mode */
    }

    </style>
    """, unsafe_allow_html=True)


# Helper functions
def image_to_bytes(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return buffered.getvalue()

def image_hash(image):
    return hashlib.md5(image_to_bytes(image)).hexdigest()

def is_duplicate(new_image, existing_images):
    new_hash = image_hash(new_image)
    for img in existing_images:
        if image_hash(img) == new_hash:
            return True
    return False

def identify_items(images):
    all_items = []
    for image in images:
        base64_image = base64.b64encode(image_to_bytes(image)).decode('utf-8')

        try:
            response = model.generate_content([
                "List all the food items you can see in this image. Provide the list in a comma-separated format.",
                {"mime_type": "image/jpeg", "data": base64_image}
            ])

            items = response.text.split(',')
            all_items.extend([item.strip() for item in items])
        except Exception as e:
            st.error(f"An error occurred while identifying items: {str(e)}")

    return list(set(all_items))  # Remove duplicates

def generate_recipe(items, diet_preference, cuisine_preference):
    try:
        diet_instruction = f"The recipe should be {diet_preference.lower()}." if diet_preference != "None" else ""
        cuisine_instruction = f"The recipe should be {cuisine_preference} cuisine." if cuisine_preference != "Any" else ""

        prompt = f"Create a recipe using these ingredients: {', '.join(items)}. {diet_instruction} {cuisine_instruction} Provide the recipe name, ingredients with quantities, and step-by-step instructions."

        response = model.generate_content(prompt)

        return response.text
    except Exception as e:
        st.error(f"An error occurred while generating the recipe: {str(e)}")
        return "Unable to generate recipe. Please try again."

def generate_multiple_recipes(items, diet_preference, cuisine_preference, num_recipes):
    recipes = []
    for _ in range(num_recipes):
        recipe = generate_recipe(items, diet_preference, cuisine_preference)
        recipes.append(recipe)
    return recipes

def get_pdf_download_link(recipes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Use a default font
    pdf.set_font("Arial", size=12)

    for i, recipe in enumerate(recipes, 1):
        pdf.cell(200, 10, txt=f"Recipe {i}", ln=True, align="C")
        pdf.multi_cell(0, 10, txt=recipe)
        pdf.ln(10)

    pdf_output = pdf.output(dest="S").encode("latin-1", errors="ignore")
    b64 = base64.b64encode(pdf_output).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="recipes.pdf">Download PDF File</a>'
    return href

# Initialize session state
def init_session_state():
    if 'page' not in st.session_state:
        st.session_state.page = 'Home'
    if 'images' not in st.session_state:
        st.session_state.images = []
    if 'ingredients' not in st.session_state:
        st.session_state.ingredients = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'shelf' not in st.session_state:
        # Initialize shelf with permanent pantry items
        st.session_state.shelf = [
            {"Ingredient": "Salt", "Quantity": 0},
            {"Ingredient": "Pepper", "Quantity": 0},
            {"Ingredient": "Olive Oil", "Quantity": 0},
            {"Ingredient": "Garlic", "Quantity": 0}
        ]


# Tooltip helper
def tooltip(text, help_text):
    return f'<div class="tooltip">{text}<span class="tooltiptext">{help_text}</span></div>'


# Full recipe list with instructions
recipes = {
    "Spicy Tomato Rice with Crispy Bread Crumbs": {
        "Yields": "4 Servings",
        "Prep Time": "15 minutes",
        "Cook Time": "25 minutes",
        "Ingredients": [
            "1 cup Rice (Basmati or long grain)",
            "2 tablespoons Atta",
            "1 medium Onion, finely chopped",
            "2 medium Tomatoes, diced",
            "1 teaspoon Green Chilli Powder",
            "Salt, to taste",
            "1 teaspoon Sugar",
            "2 tablespoons + 1 tablespoon Olive Oil",
            "2 slices Bread, processed into breadcrumbs",
            "A pinch of Pepper (optional)"
        ],
        "Instructions": [
            "Rinse the rice under cold water until the water runs clear.",
            "In a pot, combine rice with 2 cups of water and a pinch of salt. Bring to a boil, reduce heat to low, cover, and simmer for 15-20 minutes until rice is cooked.",
            "Heat 2 tablespoons of olive oil in a pan, add onions, and cook until soft and translucent.",
            "Stir in green chili powder and cook for 1 minute until fragrant.",
            "Add tomatoes, salt, and sugar. Cook for 5-7 minutes until tomatoes soften and release their juices.",
            "Whisk atta with 2-3 tablespoons of water to form a smooth slurry.",
            "Pour the slurry into the tomato mixture and cook for 2-3 minutes until the sauce thickens slightly.",
            "In a separate pan, heat the remaining olive oil and toast the breadcrumbs until golden and crispy. Season with salt and pepper.",
            "Fluff the rice and pour the tomato sauce over it. Top with crispy breadcrumbs."
        ]
    },
    "Coconut Curry Rice with Toasted Almonds": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "30 minutes",
        "Ingredients": [
            "1 cup Rice (Basmati or Jasmine)",
            "1 cup Coconut Milk",
            "1 cup Water",
            "1 tablespoon Ginger, minced",
            "2 cloves Garlic, minced",
            "1 teaspoon Curry Powder",
            "Salt, to taste",
            "2 tablespoons Olive Oil",
            "1/4 cup Almonds, sliced and toasted",
            "Fresh Cilantro, for garnish"
        ],
        "Instructions": [
            "In a pot, combine rice, coconut milk, water, and a pinch of salt. Bring to a boil, then reduce heat, cover, and simmer for 15-20 minutes until the rice is cooked.",
            "Heat olive oil in a pan over medium heat. Add minced ginger and garlic, sauté for 1-2 minutes until fragrant.",
            "Stir in curry powder and cook for another minute.",
            "Fluff the cooked rice and mix it into the ginger-garlic mixture. Season with salt if needed.",
            "Top with toasted almonds and garnish with cilantro."
        ]
    },
    "Lemon Herb Quinoa with Roasted Vegetables": {
        "Yields": "4 Servings",
        "Prep Time": "15 minutes",
        "Cook Time": "30 minutes",
        "Ingredients": [
            "1 cup Quinoa, rinsed",
            "2 cups Water",
            "1 Zucchini, diced",
            "1 Red Bell Pepper, diced",
            "1 cup Cherry Tomatoes, halved",
            "2 tablespoons Lemon Juice",
            "3 tablespoons Olive Oil",
            "1/4 cup Fresh Parsley, chopped",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "In a pot, bring quinoa and water to a boil. Reduce heat, cover, and simmer for 15 minutes until quinoa is tender.",
            "Preheat oven to 400°F (200°C). Toss zucchini, bell pepper, and cherry tomatoes with 2 tablespoons olive oil. Spread on a baking sheet and roast for 20 minutes until tender.",
            "Fluff quinoa with a fork and toss with roasted vegetables, lemon juice, remaining olive oil, parsley, salt, and pepper."
        ]
    },
    "Garlicky Spinach and Mushroom Risotto": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "40 minutes",
        "Ingredients": [
            "1 cup Arborio Rice",
            "4 cups Vegetable Broth",
            "2 tablespoons Olive Oil",
            "1 small Onion, diced",
            "3 cloves Garlic, minced",
            "1 cup Mushrooms, sliced",
            "2 cups Fresh Spinach",
            "1/4 cup Parmesan Cheese, grated",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "In a pot, warm the vegetable broth over low heat.",
            "In a large pan, heat olive oil over medium heat. Add onions and cook until softened.",
            "Add garlic and mushrooms, cook for another 5-7 minutes until mushrooms are browned.",
            "Stir in the Arborio rice and cook for 1-2 minutes to toast the rice.",
            "Add 1 cup of broth to the rice, stirring constantly until absorbed. Continue adding broth 1/2 cup at a time until the rice is creamy and fully cooked (about 18-20 minutes).",
            "Stir in spinach and Parmesan cheese. Season with salt and pepper."
        ]
    },
    "Creamy Broccoli and Cheddar Rice Bake": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "40 minutes",
        "Ingredients": [
            "1 cup Rice (Basmati or long grain)",
            "2 cups Broccoli florets",
            "1 cup Cheddar cheese, grated",
            "1 cup Milk",
            "2 tablespoons Butter",
            "2 tablespoons All-purpose flour",
            "1/2 teaspoon Garlic powder",
            "Salt and Pepper, to taste",
            "1/4 cup Bread crumbs for topping"
        ],
        "Instructions": [
            "Preheat the oven to 375°F (190°C).",
            "Cook the rice according to package instructions and set aside.",
            "Steam the broccoli florets until tender, about 5-7 minutes.",
            "In a saucepan, melt the butter over medium heat. Stir in the flour and cook for 1-2 minutes until lightly browned.",
            "Slowly whisk in the milk and cook until the sauce thickens, about 3-5 minutes.",
            "Remove from heat and stir in the grated Cheddar cheese, garlic powder, salt, and pepper.",
            "Combine the cooked rice, steamed broccoli, and cheese sauce. Transfer to a greased baking dish.",
            "Sprinkle the top with bread crumbs and bake for 15-20 minutes, until the topping is golden and crispy."
        ]
    },
    "Turmeric Rice with Grilled Tofu": {
    "Yields": "4 Servings",
    "Prep Time": "15 minutes",
    "Cook Time": "30 minutes",
    "Ingredients": [
        "1 cup Basmati Rice",
        "2 cups Water",
        "1 teaspoon Turmeric powder",
        "1/2 teaspoon Cumin seeds",
        "2 tablespoons Olive Oil",
        "1 block Tofu, pressed and cubed",
        "1 tablespoon Soy Sauce",
        "1 teaspoon Paprika",
        "1 tablespoon Lemon Juice",
        "Salt and Pepper, to taste",
        "Fresh Cilantro, for garnish"
    ],
    "Instructions": [
        "Rinse the basmati rice until the water runs clear. In a pot, bring 2 cups of water to a boil.",
        "Add the turmeric powder and a pinch of salt to the water, then stir in the rice. Reduce heat to low, cover, and simmer for 15-20 minutes until the rice is fully cooked.",
        "While the rice is cooking, prepare the tofu by tossing it in soy sauce, paprika, lemon juice, salt, and pepper.",
        "Heat olive oil in a pan over medium heat and add cumin seeds. Once they start to sizzle, add the tofu cubes and cook for 7-10 minutes, turning occasionally, until crispy and golden brown on all sides.",
        "Fluff the cooked rice and mix in the grilled tofu cubes. Garnish with fresh cilantro and serve."
    ]
}
}
# Adding new recipes to the existing recipe dictionary
recipes.update({
    "Coconut Rice with Mango Salsa": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "20 minutes",
        "Ingredients": [
            "1 cup Rice (Jasmine or Basmati)",
            "1 can (13.5 oz) Coconut Milk",
            "1 cup Water",
            "1 teaspoon Salt",
            "1 ripe Mango, diced",
            "1/4 Red Onion, finely chopped",
            "1/4 cup Fresh Cilantro, chopped",
            "1 tablespoon Lime Juice",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "In a pot, combine rice, coconut milk, water, and salt. Bring to a boil, then reduce heat to low, cover, and simmer for 15-20 minutes until rice is cooked and liquid is absorbed.",
            "While the rice is cooking, prepare the mango salsa. In a bowl, combine diced mango, red onion, cilantro, lime juice, and season with salt and pepper to taste.",
            "Once the rice is done, fluff it with a fork and serve topped with mango salsa."
        ]
    },
    "Peanut Butter Fried Rice": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "15 minutes",
        "Ingredients": [
            "2 cups Cooked Rice (preferably day-old)",
            "2 tablespoons Peanut Butter",
            "2 tablespoons Soy Sauce",
            "1 tablespoon Sesame Oil",
            "1 cup Mixed Vegetables (carrots, peas, bell peppers)",
            "2 cloves Garlic, minced",
            "1/2 teaspoon Ginger, minced",
            "2 Green Onions, sliced",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "In a small bowl, mix peanut butter, soy sauce, and sesame oil until well combined. Set aside.",
            "In a large pan or wok, heat a little oil over medium-high heat. Add garlic and ginger, and sauté for 1-2 minutes until fragrant.",
            "Add the mixed vegetables and stir-fry for about 3-4 minutes until tender.",
            "Add the cooked rice and pour the peanut butter mixture over it. Stir well to combine and cook for an additional 3-4 minutes until heated through.",
            "Garnish with sliced green onions and serve."
        ]
    },
    "Spiced Cauliflower Rice with Chickpeas": {
        "Yields": "4 Servings",
        "Prep Time": "15 minutes",
        "Cook Time": "20 minutes",
        "Ingredients": [
            "1 head Cauliflower, grated or processed into rice-sized pieces",
            "1 can (15 oz) Chickpeas, drained and rinsed",
            "1 tablespoon Olive Oil",
            "1 teaspoon Cumin",
            "1 teaspoon Coriander",
            "1/2 teaspoon Turmeric",
            "Salt and Pepper, to taste",
            "1/4 cup Fresh Parsley, chopped",
            "Juice of 1 Lemon"
        ],
        "Instructions": [
            "In a large skillet, heat olive oil over medium heat. Add grated cauliflower and cook for 5-7 minutes until tender.",
            "Stir in the chickpeas, cumin, coriander, turmeric, salt, and pepper. Cook for another 5-7 minutes until heated through.",
            "Remove from heat and stir in fresh parsley and lemon juice before serving."
        ]
    },
    "Saffron Rice with Roasted Chicken": {
        "Yields": "4 Servings",
        "Prep Time": "15 minutes",
        "Cook Time": "45 minutes",
        "Ingredients": [
            "1 1/2 cups Basmati Rice",
            "3 cups Chicken Broth",
            "1/4 teaspoon Saffron Threads",
            "1 tablespoon Olive Oil",
            "2 cloves Garlic, minced",
            "1 teaspoon Cumin",
            "Salt and Pepper, to taste",
            "4 Chicken Thighs (bone-in, skin-on)",
            "Fresh Cilantro, for garnish"
        ],
        "Instructions": [
            "Preheat the oven to 425°F (220°C). In a small bowl, soak saffron threads in a few tablespoons of warm water for about 10 minutes.",
            "In an oven-safe pot, heat olive oil over medium heat. Add garlic and cumin, and sauté for 1-2 minutes.",
            "Add rice, chicken broth, saffron (with soaking water), salt, and pepper. Bring to a boil, then reduce heat, cover, and simmer for 15 minutes.",
            "While the rice is cooking, season chicken thighs with salt and pepper. Place them skin-side up on a baking sheet and roast for 25-30 minutes until cooked through.",
            "Serve saffron rice topped with roasted chicken and garnish with fresh cilantro."
        ]
    },
    "Mexican Rice with Black Beans": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "20 minutes",
        "Ingredients": [
            "1 cup Rice (long grain or Basmati)",
            "1 can (15 oz) Black Beans, drained and rinsed",
            "1 cup Chicken or Vegetable Broth",
            "1 cup Diced Tomatoes (canned or fresh)",
            "1 teaspoon Cumin",
            "1 teaspoon Chili Powder",
            "Salt and Pepper, to taste",
            "1 tablespoon Olive Oil",
            "1/4 cup Fresh Cilantro, chopped",
            "Lime wedges for serving"
        ],
        "Instructions": [
            "In a pot, heat olive oil over medium heat. Add rice and toast for 2-3 minutes until lightly golden.",
            "Stir in the broth, diced tomatoes, cumin, chili powder, salt, and pepper. Bring to a boil, then reduce heat, cover, and simmer for 15 minutes until rice is cooked.",
            "Stir in black beans and cook for an additional 2-3 minutes until heated through.",
            "Garnish with fresh cilantro and serve with lime wedges."
        ]
    },
    "Mediterranean Rice with Feta and Olives": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "20 minutes",
        "Ingredients": [
            "1 cup Rice (Basmati or Jasmine)",
            "2 cups Vegetable or Chicken Broth",
            "1/2 cup Feta Cheese, crumbled",
            "1/4 cup Kalamata Olives, pitted and sliced",
            "1/4 cup Cherry Tomatoes, halved",
            "1/4 cup Cucumber, diced",
            "1 tablespoon Olive Oil",
            "1 teaspoon Oregano",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "In a pot, combine rice and broth. Bring to a boil, then reduce heat, cover, and simmer for 15 minutes until rice is cooked.",
            "In a large bowl, combine cooked rice with feta, olives, cherry tomatoes, cucumber, olive oil, oregano, salt, and pepper. Mix well.",
            "Serve warm or at room temperature."
        ]
    },
    "Ginger Garlic Fried Rice": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "10 minutes",
        "Ingredients": [
            "2 cups Cooked Rice (preferably day-old)",
            "2 tablespoons Oil (vegetable or sesame)",
            "3 cloves Garlic, minced",
            "1 tablespoon Ginger, minced",
            "1 cup Mixed Vegetables (peas, carrots, bell peppers)",
            "2 tablespoons Soy Sauce",
            "2 Green Onions, sliced",
            "Salt and Pepper, to taste"
        ],
        "Instructions": [
            "Heat oil in a large skillet over medium-high heat. Add minced garlic and ginger, and sauté for 1-2 minutes until fragrant.",
            "Add mixed vegetables and stir-fry for about 3-4 minutes until tender.",
            "Add the cooked rice and soy sauce. Stir well to combine and cook for an additional 3-4 minutes until heated through.",
            "Garnish with sliced green onions and serve."
        ]
    },
    "Pumpkin Risotto": {
        "Yields": "4 Servings",
        "Prep Time": "10 minutes",
        "Cook Time": "30 minutes",
        "Ingredients": [
            "1 cup Arborio Rice",
            "4 cups Vegetable Broth (heated)",
            "1 cup Pumpkin Puree (canned or fresh)",
            "1/2 cup Onion, finely chopped",
            "2 cloves Garlic, minced",
            "1/2 cup Parmesan Cheese, grated",
            "2 tablespoons Olive Oil",
            "Salt and Pepper, to taste",
            "Fresh Sage or Parsley, for garnish"
        ],
        "Instructions": [
            "In a large skillet, heat olive oil over medium heat. Add onion and garlic, and sauté until soft and translucent.",
            "Add Arborio rice and stir for 1-2 minutes until the rice is lightly toasted.",
            "Gradually add warm vegetable broth, one ladle at a time, stirring constantly until absorbed before adding more.",
            "After about 15 minutes, stir in pumpkin puree. Continue adding broth and stirring until the rice is creamy and al dente, about 20-25 minutes.",
            "Remove from heat, stir in Parmesan cheese, and season with salt and pepper.",
            "Garnish with fresh sage or parsley before serving."
        ]
    }
})


# Days of the week
days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Weekly recipe schedule
weekly_recipes = [
    ["Spicy Tomato Rice with Crispy Bread Crumbs", "Coconut Curry Rice with Toasted Almonds"],
    ["Lemon Herb Quinoa with Roasted Vegetables", "Garlicky Spinach and Mushroom Risotto"],
    ["Creamy Broccoli and Cheddar Rice Bake", "Turmeric Rice with Grilled Tofu"],
    ["Coconut Rice with Mango Salsa", "Peanut Butter Fried Rice"],
    ["Spiced Cauliflower Rice with Chickpeas", "Saffron Rice with Roasted Chicken"],
    ["Mexican Rice with Black Beans", "Mediterranean Rice with Feta and Olives"],
    ["Ginger Garlic Fried Rice", "Pumpkin Risotto"]
]

# Get the current day of the week from the system
current_day = datetime.datetime.now().strftime("%A")

# Find the index of the current day
if current_day in days_of_week:
    day_index = days_of_week.index(current_day)
else:
    raise ValueError(f"Invalid day of the week: {current_day}")

# Get recipes for today
recipes_for_today = weekly_recipes[day_index]

# Function to display full recipe instructions
def display_recipe(recipe_name):
    recipe = recipes[recipe_name]
    st.markdown(f"## {recipe_name}")
    st.markdown(f"Yields: **{recipe['Yields']}**")
    st.markdown(f"Prep Time: **{recipe['Prep Time']}**")
    st.markdown(f"Cook Time: **{recipe['Cook Time']}**")
    
    st.markdown("### Ingredients:")
    for ingredient in recipe["Ingredients"]:
        st.markdown(f"- {ingredient}")
    
    st.markdown("### Instructions:")
    for i, instruction in enumerate(recipe["Instructions"], 1):
        st.markdown(f"{i}. {instruction}")

# Main function
def home_page():
    st.title("Smart-Kitchen-Assistant")
    st.markdown("""
    Welcome to your Smart Kitchen Assistant! Here's how the app works:

    1. Upload Images of your fridge contents.
    2. Identify Ingredients using AI.
    3. Update your pantry with identified ingredients.
    4. Generate recipes based on the ingredients.
    5. Automatic grocery shopping for low-stock items.
    6. Download your favorite recipes for later use.
    
    Click 'Lets Gooo' to begin!
    """)
    if st.button('Lets Gooo', key='start_button', use_container_width=True):
        st.session_state.page = 'Upload Images'
        st.rerun()

    # Display the recipes for the current day
    st.header(f"Today's Recipes ({current_day}):")
    for recipe_name in recipes_for_today:
        if recipe_name in recipes:
            display_recipe(recipe_name)
        else:
            st.error(f"Recipe '{recipe_name}' is missing!")


def upload_images_page():
    st.header("📸 Upload your pantry Images")
    st.markdown(tooltip("Instructions:", "\nFollow these steps to add images of your pantry."), unsafe_allow_html=True)
    st.markdown("""
    1. Choose an option to either upload images or take pictures.
    2. Add images of your pantry.
    3. Proceed to the next step to identify ingredients.
    """)

    image_option = st.radio("Choose an option:", ("Upload Images", "Take Pictures"), horizontal=True)

    if image_option == "Take Pictures":
        camera_image = st.camera_input("📷 Take a picture of your fridge contents")
        if camera_image:
            new_image = Image.open(camera_image)
            if not is_duplicate(new_image, st.session_state.images):
                st.session_state.images.append(new_image)
                st.success("Image added successfully! 🎉")
            else:
                st.warning("This image is a duplicate and was not added.")
    else:
        uploaded_files = st.file_uploader("📤 Upload your pantry images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if uploaded_files:
            new_images = 0
            duplicates = 0
            for uploaded_file in uploaded_files:
                new_image = Image.open(uploaded_file)
                if not is_duplicate(new_image, st.session_state.images):
                    st.session_state.images.append(new_image)
                    new_images += 1
                else:
                    duplicates += 1

            if new_images > 0:
                st.success(f"{new_images} new image(s) added successfully! 🎉")
            if duplicates > 0:
                st.info(f"{duplicates} duplicate image(s) were not added.")

    if st.session_state.images:
        st.subheader("Captured/Uploaded Images")
        cols = st.columns(3)
        for i, img in enumerate(st.session_state.images):
            cols[i % 3].image(img, caption=f'Image {i+1}', use_column_width=True)

        if st.button('🗑 Clear All Images', use_container_width=True):
            st.session_state.images = []
            st.rerun()

    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button('⬅ Back to Home', key='back_to_home', use_container_width=True):
            st.session_state.page = 'Home'
            st.rerun()
    with col2:
        if st.button('Next ➡', key='to_identify', use_container_width=True):
            if not st.session_state.images:
                st.error("Please upload at least one image before proceeding.")
            else:
                st.session_state.page = 'Identify Ingredients'
                st.rerun()

def identify_ingredients_page():
    st.header("🔍 Identify Ingredients")
    st.markdown("Follow these steps to identify ingredients from your fridge images.")

    if not st.session_state.images:
        st.warning("Please upload images of your fridge contents first.")
        return

    if st.button('🔍 Identify Ingredients'):
        with st.spinner('Analyzing fridge contents...'):
            identified_items = identify_items(st.session_state.images)
            st.session_state.ingredients = identified_items

    if st.session_state.ingredients:
        st.subheader("Identified Ingredients")
        ingredients = st.text_area("✏ Edit, add, or remove ingredients:",
                                   value='\n'.join(st.session_state.ingredients),
                                   height=200)
        st.session_state.ingredients = [item.strip() for item in ingredients.split('\n') if item.strip()]

        st.subheader("Add ingredeants to shelf")
        ingredient_to_add = st.selectbox("Select an ingredient to add to the shelf", st.session_state.ingredients)

        default_expiry = datetime.date.today() + datetime.timedelta(days=7)
# Inside the identify_ingredients_page function

# Add quantity input
        quantity = st.number_input("Quantity", min_value=1, step=1)

# Add expiry date input
        expiry_date = st.date_input("Expiry Date")

# Add to shelf button
        if st.button("Add to shelf"):
            if 'shelf' not in st.session_state:
                st.session_state.shelf = []

    # Check if the item is already in the shelf and update the quantity/expiry
            existing_item = next((item for item in st.session_state.shelf if item['Ingredient'] == ingredient_to_add), None)
            if existing_item:
                existing_item['Quantity'] += quantity
                existing_item['Expiry'] = expiry_date  # Update expiry date if changed
            else:
                st.session_state.shelf.append({
                "Ingredient": ingredient_to_add,
                "Quantity": quantity,
                "Expiry": expiry_date
        })

    st.success(f"Added {ingredient_to_add} (Quantity: {quantity}, Expiry: {expiry_date}) to the shelf.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button('⬅️ Back to Upload'):
            st.session_state.page = 'Upload Images'
            st.rerun()
    with col2:
        if st.button('Next to shelf ➡️'):
            st.session_state.page = 'shelf'
            st.rerun()

def search_amazon_url(query):
    search_url = "https://www.amazon.com/s?k=" + urllib.parse.quote(query)
    return search_url

def shelf_page():
    st.header("🗄️ Shelf")
    st.markdown("Here you can view and manage the items in your shelf.")
    
    # Notification thresholds
    LOW_QUANTITY_THRESHOLD = 2  # You can adjust this value
    TODAY = datetime.date.today()

    if 'shelf' not in st.session_state or not st.session_state.shelf:
        st.warning("Your shelf is empty. Add items from the Identify items page.")
        return

    # Ensure each item has an 'Expiry' field, if missing, set a default expiry
    for item in st.session_state.shelf:
        if 'Expiry' not in item:
            item['Expiry'] = TODAY + datetime.timedelta(days=7)  # Set default expiry as 7 days from today
    
        # Show notifications for expired or low quantity items with Amazon link
    for item in st.session_state.shelf:
        search_url = search_amazon_url(item['Ingredient'])

        # Check for low quantity
        if item['Quantity'] < LOW_QUANTITY_THRESHOLD:
            st.warning(f"⚠️ Low quantity for **{item['Ingredient']}**: Only {item['Quantity']} left! [Buy on Amazon]({search_url})")

        # Check if the item is expired or close to expiry
        if item['Expiry'] < TODAY:
            st.error(f"❌ **{item['Ingredient']}** has expired (Expired on {item['Expiry']}). [Buy on Amazon]({search_url})")
        elif item['Expiry'] <= TODAY + datetime.timedelta(days=2):
            st.warning(f"⚠️ **{item['Ingredient']}** is expiring soon (Expiry: {item['Expiry']}). [Buy on Amazon]({search_url})")

    # Create a multi-select box for selecting items for the recipe
    shelf_items = [item['Ingredient'] for item in st.session_state.shelf]
    selected_items = st.multiselect("Select items for the recipe:", shelf_items)

    # Display the shelf contents
    if 'shelf' in st.session_state and st.session_state.shelf:
        shelf_df = pd.DataFrame(st.session_state.shelf)
        shelf_df['Quantity'] = shelf_df['Quantity'].astype(str)  # Convert Quantity to string for display
        shelf_df['Expiry'] = shelf_df['Expiry'].astype(str)      # Convert Expiry to string for display
        st.dataframe(shelf_df)

    # Display shelf contents with Amazon search links
    for item in st.session_state.shelf:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{item['Ingredient']}** (Quantity: {item['Quantity']}, Expiry: {item['Expiry']})")
        with col2:
            search_url = search_amazon_url(item['Ingredient'])
            st.markdown(f"[Buy on Amazon]( {search_url} )", unsafe_allow_html=True)

    # Option to remove items or clear the shelf
    ingredient_to_remove = st.selectbox("Select an ingredient to remove", shelf_df['Ingredient'].tolist())
    if st.button("Remove Ingredient"):
        st.session_state.shelf = [item for item in st.session_state.shelf if item['Ingredient'] != ingredient_to_remove]
        st.success(f"Removed {ingredient_to_remove} from the shelf.")
        st.rerun()

    if st.button('Clear Shelf', use_container_width=True):
        st.session_state.shelf = []
        st.success("Shelf cleared!")
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button('⬅️ Back to items', use_container_width=True):
            st.session_state.page = 'Identify items'
            st.rerun()
    with col2:
        if st.button('Next ➡️ Generate Recipe', use_container_width=True):
            st.session_state.selected_items = selected_items
            st.session_state.page = 'Generate Recipe'
            st.rerun()


def generate_recipe_page():
    st.header("🍲 Generate Recipes")
    st.markdown("Use the ingredients in your shelf to generate recipes.")

    if 'shelf' not in st.session_state or not st.session_state.shelf:
        st.warning("Your shelf is empty. Please add ingredients to your shelf first.")
        return

    # Get selected items from shelf
    selected_items = st.session_state.get('selected_items', [])

    if not selected_items:
        st.warning("Please select ingredients from the shelf.")
        return

    st.subheader("Selected Ingredients for Recipe")
    st.write(", ".join(selected_items))

    col1, col2, col3 = st.columns(3)
    with col1:
        diet_options = ["None", "Vegetarian", "Vegan", "Gluten-Free", "Keto", "Low-Carb", "Paleo"]
        diet_preference = st.selectbox("🥗 Select dietary preference:", diet_options)
    with col2:
        cuisine_options = ["Any", "Italian", "Mexican", "Asian", "Mediterranean", "American", "Indian", "French"]
        cuisine_preference = st.selectbox("🌍 Select cuisine preference:", cuisine_options)
    with col3:
        num_recipes = st.slider("🔢 Number of recipes:", min_value=1, max_value=5, value=1)

    if st.button('🧑‍🍳 Generate Recipes'):
        with st.spinner(f'Generating {num_recipes} recipe(s)...'):
            recipes = generate_multiple_recipes(selected_items, diet_preference, cuisine_preference, num_recipes)
            st.session_state.recipes = recipes
            # Remove selected items from the shelf after generating the recipe
            st.session_state.shelf = [item for item in st.session_state.shelf if item['Ingredient'] not in selected_items]

    if st.session_state.recipes:
        st.subheader("Your Recipes")
        for i, recipe in enumerate(st.session_state.recipes, 1):
            st.markdown(f'<div class="recipe-container"><h3>Recipe {i}</h3>{recipe}</div>', unsafe_allow_html=True)

        st.markdown(get_pdf_download_link(st.session_state.recipes), unsafe_allow_html=True)

        st.subheader("Buy the Pantry ingredeants Used in Recipe")
        for item in selected_items:
            search_url = search_amazon_url(item)
            st.markdown(f"[buy {item} on Amazon]( {search_url} )", unsafe_allow_html=True)

    if st.button('⬅ Back to shelf'):
        st.session_state.page = 'shelf'
        st.rerun()



def main():
    init_session_state()

    # Create horizontal navigation using columns for the new pages
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("Home"):
            st.session_state.page = "Home"
    with col2:
        if st.button("Upload Images"):
            st.session_state.page = "Upload Images"
    with col3:
        if st.button("Identify Ingredients"):
            st.session_state.page = "Identify Ingredients"
    with col4:
        if st.button("shelf"):
            st.session_state.page = "shelf"
    with col5:
        if st.button("Generate Recipe"):
            st.session_state.page = "Generate Recipe"

    # Display the corresponding page content
    if st.session_state.page == "Home":
        home_page()
    elif st.session_state.page == "Upload Images":
        upload_images_page()
    elif st.session_state.page == "Identify Ingredients":
        identify_ingredients_page()
    elif st.session_state.page == "shelf":
        shelf_page()  # New shelf page function
    elif st.session_state.page == "Generate Recipe":
        generate_recipe_page()




if __name__ == "__main__":
    main()