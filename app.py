import os
import requests  
import googlemaps
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize the Flask app and Google Maps client
app = Flask(__name__)

# Enable CORS
CORS(app)

# Google Maps API Key from environment variable
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

# Using ollama to use mistral momdel
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Assuming origin location
DEFAULT_CITY = "Jakarta, Indonesia"

# Configure logging
logging.basicConfig(level=logging.INFO)

def query_mistral(prompt: str):
    headers = {"Content-Type": "application/json"}
    data = {"model": "mistral", "prompt": prompt, "role": "user", "stream": False}

    try:
        response = requests.post(OLLAMA_API_URL, json=data, headers=headers, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json().get('response', 'No response from model.')
    except requests.exceptions.RequestException as e:
        logging.error(f"Request to Ollama API failed: {str(e)}")
        return "Error querying Ollama API"

# get geolocation from origin location
def get_lat_lng_from_city(city_name):
    geocode_result = gmaps.geocode(city_name)
    if geocode_result:
        lat = geocode_result[0]['geometry']['location']['lat']
        lng = geocode_result[0]['geometry']['location']['lng']
        return {'lat': lat, 'lng': lng}
    return None

@app.route('/find-places', methods=['POST'])
def find_places_and_query_llm():
    data = request.json
    user_query = data.get('query')

    if not user_query:
        abort(400, description="Query cannot be empty")

    city_name = data.get('city', DEFAULT_CITY)
    user_location = get_lat_lng_from_city(city_name)

    if not user_location:
        abort(400, description="Invalid city name")

    try:
        places_result = gmaps.places(query=user_query, location=user_location, radius=5000)
        if not places_result['results']:
            return jsonify({"error": "No places found for your query."}), 400
        
        place = places_result['results'][3]
        place_name = place['name']
        place_address = place.get('vicinity', 'Address not available')
        place_lat = place['geometry']['location']['lat']
        place_lng = place['geometry']['location']['lng']
        
        origin_lat = user_location['lat']
        origin_lng = user_location['lng']
        directions_link = f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={place_lat},{place_lng}"
        embed_link = f"https://www.google.com/maps/embed/v1/directions?key={os.getenv('GOOGLE_MAPS_API_KEY')}&origin={origin_lat},{origin_lng}&destination={place_lat},{place_lng}"

        # Hit LLM 
        prompt = f"Provide a short description for a place named '{place_name}'."
        llm_response = query_mistral(prompt)

        return jsonify({
            "place_name": place_name,
            "place_description": llm_response,
            "google_maps_link": directions_link,
            "embed_link": embed_link
        }), 200

    except googlemaps.exceptions.ApiError as e:
        logging.error(f"Google Maps API error: {str(e)}")
        return jsonify({"error": f"Google Maps API error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
