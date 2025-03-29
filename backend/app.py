# this app.py
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import os
from dotenv import load_dotenv
import requests
import json
import base64
from io import BytesIO
from PIL import Image
import uuid
import tempfile
from datetime import datetime
from supabase import create_client, Client
# Load environment variables
load_dotenv()

# Debug: Print environment variables
print(f"SUPABASE_URL from env: {os.getenv('SUPABASE_URL')}")
print(f"SUPABASE_KEY from env: {os.getenv('SUPABASE_KEY')}")
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')


# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase initialized successfully")
except Exception as e:
    print(f"Supabase initialization error: {e}")
    supabase = None


@app.route('/')
def index():
    if 'user' in session:
        return render_template('dashboard.html', user=session['user'])
    return render_template('login.html')

@app.route('/login')
def login():
    # Print the values to verify they're available
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY: {SUPABASE_KEY}")
    
    return render_template('login.html', supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

@app.route('/callback')
def callback():
    # This route handles the OAuth callback
    # Print the values to verify they're available
    print(f"SUPABASE_URL callback: {SUPABASE_URL}")
    print(f"SUPABASE_KEY callback: {SUPABASE_KEY}")
    
    return render_template('callback.html', supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

@app.route('/auth', methods=['POST'])
def auth():
    try:
        print("Received auth request")
        data = request.json
        print(f"Auth data: {data}")
        
        # Store the session data from Supabase
        session['user'] = {
            'id': data.get('id'),
            'email': data.get('email'),
            'name': data.get('user_metadata', {}).get('full_name'),
            'picture': data.get('user_metadata', {}).get('avatar_url')
        }
        
        print(f"Session user: {session['user']}")
        
        # Check if user exists in our database, create if not
        user_id = data.get('id')
        user_query = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_query.data:
            # Create user in our database
            user_data = {
                'id': user_id,
                'email': data.get('email'),
                'name': data.get('user_metadata', {}).get('full_name'),
                'picture': data.get('user_metadata', {}).get('avatar_url'),
                'google_id': data.get('user_metadata', {}).get('sub')
            }
            print(f"Creating new user: {user_data}")
            supabase.table('users').insert(user_data).execute()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Auth error: {e}")
        return jsonify({'error': str(e)}), 500


def save_image_to_supabase(image_url, user_id, is_main=False, character_id=None):
    try:
        # Download the image
        response = requests.get(image_url)
        if response.status_code != 200:
            print(f"Failed to download image: Status code {response.status_code}")
            return None
        
        # Define the file path in Supabase storage
        if is_main:
            file_path = f"{user_id}/main.png"
        else:
            file_path = f"{user_id}/people/{character_id}.png"
        
        # Upload the image directly to Supabase storage
        result = supabase.storage.from_('character-images').upload(
            file_path,
            response.content,
            file_options={"content-type": "image/png"}
        )
        
        # Get the public URL
        public_url = supabase.storage.from_('character-images').get_public_url(file_path)
        return public_url
        
    except Exception as e:
        print(f"Error saving image to Supabase: {e}")
        return None

@app.route('/save_main_character', methods=['POST'])
def save_main_character():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.json
        image_url = data.get('imageUrl')
        description = data.get('description')
        
        if not image_url or not description:
            return jsonify({'error': 'Missing image URL or description'}), 400
        
        # Save the main character data to Supabase
        user_id = session['user']['id']
        
        # Save image to Supabase Storage
        supabase_image_url = save_image_to_supabase(image_url, user_id, is_main=True)
        
        if not supabase_image_url:
            return jsonify({'error': 'Failed to save image to storage'}), 500
        
        # Update user in Supabase
        supabase.table('users').update({
            'main_character_url': supabase_image_url,
            'main_character_description': description
        }).eq('id', user_id).execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error saving main character: {e}")
        return jsonify({'error': f'Failed to save main character: {str(e)}'}), 500

@app.route('/add_person', methods=['POST'])
def add_person():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        if 'name' not in request.form:
            return jsonify({'error': 'No name provided'}), 400
            
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        name = request.form['name']
        image = request.files['image']
        
        # Process the image with GPT-4o
        description, error = process_image_with_gpt4o(image)
        if error:
            return jsonify({'error': error}), 500
        
        # Generate the character image with DALL-E
        image_url, error = generate_character_with_dalle(description)
        if error:
            return jsonify({'error': error}), 500
        
        # Save the character data to Supabase
        user_id = session['user']['id']
        character_id = str(uuid.uuid4())
        
        # Save image to Supabase Storage
        supabase_image_url = save_image_to_supabase(
            image_url, 
            user_id, 
            is_main=False, 
            character_id=character_id
        )
        
        if not supabase_image_url:
            return jsonify({'error': 'Failed to save image to storage'}), 500
        
        # Count existing characters for this user
        character_count = supabase.table('characters').select('id').eq('user_id', user_id).execute()
        
        # Check if we already have 5 characters
        if len(character_count.data) >= 5:
            return jsonify({'error': 'You can only add up to 5 characters. Please delete some to add more.'}), 400
        
        # Add new character to Supabase
        new_character = {
            'id': character_id,
            'user_id': user_id,
            'name': name,
            'image_url': supabase_image_url,
            'description': description
        }
        
        supabase.table('characters').insert(new_character).execute()
        
        return jsonify({'success': True, 'character': new_character})
        
    except Exception as e:
        print(f"Error adding character: {e}")
        return jsonify({'error': f'Failed to add character: {str(e)}'}), 500

@app.route('/delete_person', methods=['POST'])
def delete_person():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.json
        character_id = data.get('personId')
        
        if not character_id:
            return jsonify({'error': 'No character ID provided'}), 400
        
        user_id = session['user']['id']
        
        # First verify that this character belongs to the user
        character = supabase.table('characters').select('*').eq('id', character_id).eq('user_id', user_id).execute()
        
        if not character.data:
            return jsonify({'error': 'Character not found or does not belong to user'}), 404
        
        # Delete the character from the database
        supabase.table('characters').delete().eq('id', character_id).execute()
        
        # Delete the image from storage
        try:
            supabase.storage.from_('character-images').remove([f"{user_id}/people/{character_id}.png"])
        except Exception as e:
            print(f"Warning: Could not delete image from storage: {e}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error deleting character: {e}")
        return jsonify({'error': f'Failed to delete character: {str(e)}'}), 500
            
@app.route('/people')
def people():
    if 'user' not in session:
        return redirect('/login')
    
    # Fetch user's characters from Supabase
    user_id = session['user']['id']
    characters = []
    
    try:
        result = supabase.table('characters').select('*').eq('user_id', user_id).execute()
        characters = result.data
    except Exception as e:
        print(f"Error fetching characters: {e}")
    
    return render_template('people.html', user=session['user'], people=characters)
   
# Refactor process_image and generate_character to separate the core functionality

def process_image_with_gpt4o(image):
    """Process an image with GPT-4o and return the description"""
    try:
        img_str = base64.b64encode(image.read()).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a creative art description assistant that helps translate visual elements into written descriptions for artistic recreation. Focus on stylistic elements, composition, and artistic techniques rather than specific identities."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please provide a detailed artistic description of this fictional illustration in terms of composition, style, mood, and visual elements. Focus on artistic techniques, stylization, and design elements that would be helpful for creating a black and white sketch interpretation. Describe the artistic choices, poses, expressions, attire, and distinctive stylistic features. Avoid any content that could be inappropriate for general audiences."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_str}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        
        if 'choices' not in result:
            return None, f"Failed to process image description: {result.get('error', 'Unknown error')}"
        
        description = result['choices'][0]['message']['content']
        return description, None
        
    except Exception as e:
        return None, f"Error processing image: {str(e)}"

def generate_character_with_dalle(description):
    """Generate a character image using DALL-E based on the description"""
    try:
        # Check the description with OpenAI's moderation API
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        moderation_payload = {"input": description}
        moderation_response = requests.post(
            "https://api.openai.com/v1/moderations",
            headers=headers,
            json=moderation_payload
        )
        moderation_result = moderation_response.json()
        
        if moderation_result['results'][0]['flagged']:
            return None, "The generated description was flagged by the content moderation system. Please try a different image."
        
        # If the description passes moderation, proceed to DALL-E
        dall_e_prompt = f"Create a BLACK AND WHITE ONLY image in a MANGA style animation, THE IMAGE NEEDS TO LOOK LIKE IT WAS SKETCHED the character(s) described below in a frontal pose with a neutral background: {description}. The image should be suitable for all audiences and faithfully represent the provided description without adding extra elements. Pay extra attention to making sure it looks like a manga character."
        
        payload = {
            "model": "dall-e-3",
            "prompt": dall_e_prompt,
            "n": 1,
            "size": "1024x1024",
            "quality": "standard"
        }
        
        response = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
        result = response.json()
        
        if 'error' in result:
            error_message = result['error']['message']
            return None, f"DALL-E API Error: {error_message}"
        
        image_url = result['data'][0]['url']
        return image_url, None
        
    except Exception as e:
        return None, f"Error generating character image: {str(e)}"

# Update the existing routes to use these functions
@app.route('/process_image', methods=['POST'])
def process_image():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image = request.files['image']
        description, error = process_image_with_gpt4o(image)
        
        if error:
            return jsonify({'error': error}), 500
            
        return jsonify({'description': description})
    
    except Exception as e:
        print(f"Error processing image: {e}")
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500

@app.route('/generate_character', methods=['POST'])
def generate_character():
    try:
        data = request.json
        description = data.get('description')
        
        if not description:
            return jsonify({'error': 'No description provided'}), 400
        
        image_url, error = generate_character_with_dalle(description)
        
        if error:
            return jsonify({'error': error}), 400
            
        return jsonify({'image_url': image_url})
    
    except Exception as e:
        print(f"Error generating character image: {e}")
        return jsonify({'error': f'Failed to generate character image: {str(e)}'}), 500



@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)