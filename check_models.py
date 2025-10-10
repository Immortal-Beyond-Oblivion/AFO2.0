# check_models.py
# Helper script to list available Gemini models for the provided API key
# Run Independently to see which models you can use
import google.generativeai as genai
from config import GOOGLE_API_KEY

# Configure the API key
genai.configure(api_key=GOOGLE_API_KEY)

print("Listing available Gemini models for your API key...")

# List all models
for model in genai.list_models():
  # We check if 'generateContent' is a supported method for the model
  if 'generateContent' in model.supported_generation_methods:
    print(f"- {model.name}")