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
from PIL import Image
# Load environment variables
load_dotenv()

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

##spme testing for image uploading

def ensure_user_exists(user_id, supabase_client):
    """Ensure the user exists in the users table"""
    try:
        print(f"Checking if user {user_id} exists...")
        user_check = supabase_client.table('users').select('id').eq('id', user_id).execute()
        
        if not user_check.data:
            print(f"User {user_id} doesn't exist in users table. Creating user record...")
            # Get user data from session
            user_data = {
                'id': user_id,
                'email': session['user'].get('email'),
                'name': session['user'].get('name', 'Unknown User'),
                'profile_picture': session['user'].get('picture', '')
            }
            
            print(f"Inserting user with data: {user_data}")
            user_insert = supabase_client.table('users').insert(user_data).execute()
            print(f"User insert result: {user_insert}")
            return True
        else:
            print(f"User {user_id} exists in database")
            return True
    except Exception as e:
        print(f"Error ensuring user exists: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def get_authenticated_supabase(user_id=None):
    """Get a Supabase client with the user's authentication token"""
    try:
        # Create a fresh client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # If we have a user ID and both tokens in session
        if user_id and 'supabase_token' in session and 'supabase_refresh_token' in session:
            access_token = session.get('supabase_token')
            refresh_token = session.get('supabase_refresh_token')
            
            if access_token and refresh_token:
                # Set the session with both tokens
                supabase_client.auth.set_session(access_token, refresh_token)
                return supabase_client
                
        # Return the standard client if auth not possible
        return supabase_client
        
    except Exception as e:
        print(f"Error creating authenticated Supabase client: {e}")
        # Fall back to the default client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    



# @app.route('/debug_tokens', methods=['GET'])
# def debug_tokens():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    token_info = {
        'has_access_token': 'supabase_token' in session,
        'has_refresh_token': 'supabase_refresh_token' in session,
        'access_token_preview': session.get('supabase_token', '')[:10] + '...' if session.get('supabase_token') else None,
        'refresh_token_preview': session.get('supabase_refresh_token', '')[:10] + '...' if session.get('supabase_refresh_token') else None,
        'user_id': session.get('user', {}).get('id')
    }
    
    return jsonify(token_info)
##testig ends

@app.route('/api/supabase-credentials')
def supabase_credentials():
    return jsonify({
        'url': os.getenv('SUPABASE_URL'),
        'key': os.getenv('SUPABASE_KEY')
    })

@app.route('/')
def index():
    if 'user' not in session:
        return render_template('login.html')
    
    user_id = session['user']['id']
    user_data = session['user'].copy()  # Start with session data
    
    try:
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get user data including main character info
        user_result = supabase_client.table('users').select('*').eq('id', user_id).execute()
        
        if user_result.data:
            # Add database user data to session user data
            for key, value in user_result.data[0].items():
                user_data[key] = value
                
            print(f"Combined user data: {user_data}")
            
            # If user has a main character URL, ensure it's fresh
            if user_data.get('main_character_url') and 'sign' in user_data.get('main_character_url', ''):
                # Try to create a fresh signed URL
                try:
                    main_file_path = f"{user_id}/main.png"
                    signed_url = supabase_client.storage.from_('character-images').create_signed_url(
                        path=main_file_path,
                        expires_in=3600  # 1 hour
                    )
                    
                    if isinstance(signed_url, dict) and 'signedURL' in signed_url:
                        user_data['main_character_url'] = signed_url['signedURL']
                except Exception as url_error:
                    print(f"Error creating fresh signed URL for main character: {url_error}")
            
    except Exception as e:
        print(f"Error fetching user data: {e}")
        import traceback
        traceback.print_exc()
    
    # Check if main character exists
    has_main_character = user_data and user_data.get('main_character_url') and user_data.get('main_character_description')
    
    return render_template('dashboard.html', user=user_data, has_main_character=has_main_character)

@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/callback')
def callback():
    # This route handles the OAuth callback
    return render_template('callback.html')



@app.route('/auth', methods=['POST'])
def auth():
    try:
        print("Received auth request")
        data = request.json
        print(f"Auth data: {data}")
        
        # Extract user ID and access token from data
        user_id = data.get('id')
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        print(f"User ID from auth: {user_id}")
        print(f"User ID type: {type(user_id)}")
        
        # Store the JWT token
        if access_token and refresh_token:
            session['supabase_token'] = access_token
            session['supabase_refresh_token'] = refresh_token
            print(f"Stored tokens - Access: {access_token[:10]}..., Refresh: {refresh_token[:10]}...")
        else:
            print("Missing tokens - Access:", bool(access_token), "Refresh:", bool(refresh_token))
            
        # Store the session data from Supabase
        session['user'] = {
            'id': user_id,
            'email': data.get('email'),
            'name': data.get('user_metadata', {}).get('full_name'),
            'picture': data.get('user_metadata', {}).get('avatar_url')
        }
        
        print(f"Session user: {session['user']}")
        
        # Get an authenticated client for database operations
        supabase_client = get_authenticated_supabase(user_id)
        
        # Ensure the user exists in our database
        ensure_user_exists(user_id, supabase_client)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Auth error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def save_image_to_supabase(image_url, user_id, is_main=False, character_id=None):
    try:
        # Get authenticated Supabase client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Download the image or read from local file
        if isinstance(image_url, str):
            if image_url.startswith('http'):
                response = requests.get(image_url)
                if response.status_code != 200:
                    print(f"Failed to download image: Status code {response.status_code}")
                    return None
                image_bytes = response.content
            else:
                # If it's a local file path
                with open(image_url, 'rb') as f:
                    image_bytes = f.read()
        else:
            # If image_url is already file-like
            image_bytes = image_url.read()
        
        # Define the file path in Supabase storage
        if is_main:
            file_path = f"{user_id}/main.png"
        else:
            file_path = f"{user_id}/people/{character_id}.png"
        
        # Print debug info
        print(f"Uploading to path: {file_path}")
        print(f"Image bytes type: {type(image_bytes)}")
        print(f"Image bytes length: {len(image_bytes) if isinstance(image_bytes, bytes) else 'not bytes'}")
        
        try:
            # First try to update if the file exists
            print(f"Trying to update existing file...")
            result = supabase_client.storage.from_('character-images').update(
                path=file_path,
                file=image_bytes,
                file_options={"content-type": "image/png"}
            )
            print(f"Update result: {result}")
        except Exception as e:
            print(f"Update failed (likely file doesn't exist yet): {e}")
            # If update fails, try to upload as new file
            try:
                print(f"Trying to upload new file...")
                result = supabase_client.storage.from_('character-images').upload(
                    path=file_path,
                    file=image_bytes,
                    file_options={"content-type": "image/png"}
                )
                print(f"Upload result: {result}")
            except Exception as upload_error:
                if "The resource already exists" in str(upload_error) or "Duplicate" in str(upload_error):
                    # If we get here, both update and upload failed
                    # Let's try to remove and then upload
                    print(f"Both update and upload failed. Removing existing file and then uploading...")
                    try:
                        supabase_client.storage.from_('character-images').remove([file_path])
                        result = supabase_client.storage.from_('character-images').upload(
                            path=file_path,
                            file=image_bytes,
                            file_options={"content-type": "image/png"}
                        )
                        print(f"Remove and re-upload result: {result}")
                    except Exception as final_error:
                        print(f"Final attempt failed: {final_error}")
                        raise final_error
                else:
                    raise upload_error
        
        # Get the authenticated URL - using the signed URL method for private buckets
        try:
            # First, try to get a signed URL with a long expiration (1 week)
            signed_url = supabase_client.storage.from_('character-images').create_signed_url(
                path=file_path,
                expires_in=604800  # 7 days in seconds
            )
            print(f"Generated signed URL: {signed_url}")
            
            if isinstance(signed_url, dict) and 'signedURL' in signed_url:
                return signed_url['signedURL']
            else:
                # If signedURL not in expected format, create a placeholder URL for now
                # This URL will need to be refreshed on the client side
                return f"{SUPABASE_URL}/storage/v1/object/sign/character-images/{file_path}?token=sessionToken"
                
        except Exception as url_error:
            print(f"Error creating signed URL: {url_error}")
            # Fallback to creating a placeholder URL structure
            return f"{SUPABASE_URL}/storage/v1/object/sign/character-images/{file_path}?token=sessionToken"
        
    except Exception as e:
        print(f"Error saving image to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/get-signed-image-url', methods=['POST'])
def get_signed_image_url():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    user_id = session['user']['id']
    
    try:
        supabase_client = get_authenticated_supabase(user_id)
        
        # Create a new signed URL with a 15-minute expiration
        signed_url = supabase_client.storage.from_('character-images').create_signed_url(
            path=path,
            expires_in=900  # 15 minutes in seconds
        )
        
        if isinstance(signed_url, dict) and 'signedURL' in signed_url:
            return jsonify({'url': signed_url['signedURL']})
        else:
            return jsonify({'error': 'Failed to generate signed URL'}), 500
            
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to generate signed URL: {str(e)}'}), 500
    


# @app.route('/test_storage_upload', methods=['GET'])
# def test_storage_upload():
#     try:
#         if 'user' not in session:
#             return jsonify({'error': 'Not logged in'}), 401
            
#         # Path to a test image in your project
#         test_image_path = os.path.join(os.path.dirname(__file__), 'static', 'test_image.png')
        
#         # Check if test image exists
#         if not os.path.exists(test_image_path):
#             # Try an alternative path
#             test_image_path = os.path.join('static', 'test_image.png')
#             if not os.path.exists(test_image_path):
#                 return jsonify({
#                     'error': 'Test image not found. Please place a test_image.png file in your static folder',
#                     'paths_tried': [
#                         os.path.join(os.path.dirname(__file__), 'static', 'test_image.png'),
#                         os.path.join('static', 'test_image.png')
#                     ]
#                 }), 404
        
#         print(f"Using test image at: {test_image_path}")
        
#         user_id = session['user']['id']
        
#         # Use our updated function to upload the image
#         supabase_image_url = save_image_to_supabase(test_image_path, user_id, is_main=True)
        
#         if not supabase_image_url:
#             return jsonify({'error': 'Failed to upload test image to storage'}), 500
            
#         return jsonify({
#             'success': True,
#             'message': 'Test image uploaded successfully',
#             'image_url': supabase_image_url
#         })
        
#     except Exception as e:
#         print(f"Error in test upload: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': f'Test upload failed: {str(e)}'}), 500
    

# @app.route('/test_blank_image_upload', methods=['GET'])
# def test_blank_image_upload():
#     try:
#         if 'user' not in session:
#             return jsonify({'error': 'Not logged in'}), 401
            
#         # Create a blank test image
#         from PIL import Image
#         import io
        
#         # Create a small blank image
#         img = Image.new('RGB', (100, 100), color = (73, 109, 137))
        
#         # Save to a bytes buffer
#         img_byte_arr = io.BytesIO()
#         img.save(img_byte_arr, format='PNG')
#         img_byte_arr.seek(0)
        
#         user_id = session['user']['id']
        
#         # Define the file path in Supabase storage
#         file_path = f"{user_id}/test_blank.png"
        
#         # Upload directly
#         result = supabase.storage.from_('character-images').upload(
#             path=file_path,
#             file=img_byte_arr.getvalue(),
#             file_options={"content-type": "image/png"}
#         )
        
#         # Get the public URL
#         public_url = supabase.storage.from_('character-images').get_public_url(file_path)
        
#         return jsonify({
#             'success': True,
#             'message': 'Blank test image created and uploaded successfully',
#             'image_url': public_url
#         })
        
#     except Exception as e:
#         print(f"Error in blank image test: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': f'Blank image test failed: {str(e)}'}), 500
    

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
        
        user_id = session['user']['id']
        
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Ensure user exists in the database
        if not ensure_user_exists(user_id, supabase_client):
            return jsonify({'error': 'Failed to ensure user exists in database'}), 500
        
        # Save image to Supabase Storage
        supabase_image_url = save_image_to_supabase(image_url, user_id, is_main=True)
        
        if not supabase_image_url:
            return jsonify({'error': 'Failed to save image to storage'}), 500
        
        # Update user in Supabase
        supabase_client.table('users').update({
            'main_character_url': supabase_image_url,
            'main_character_description': description
        }).eq('id', user_id).execute()
        
        # Also add this as a character in the characters table
        character_id = str(uuid.uuid4())
        
        # Check if an existing main character exists
        existing_main = supabase_client.table('characters').select('id').eq('user_id', user_id).eq('is_main_character', True).execute()
        
        if existing_main.data:
            # Update the existing main character
            character_id = existing_main.data[0]['id']
            supabase_client.table('characters').update({
                'name': 'Main Character',
                'image_url': supabase_image_url,
                'description': description
            }).eq('id', character_id).execute()
        else:
            # Create a new character entry
            new_character = {
                'id': character_id,
                'user_id': user_id,
                'name': 'Main Character',
                'image_url': supabase_image_url,
                'description': description,
                'is_main_character': True
            }
            
            print(f"Inserting new main character: {new_character}")
            result = supabase_client.table('characters').insert(new_character).execute()
            print(f"Insert result: {result}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error saving main character: {e}")
        import traceback
        traceback.print_exc()
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
        user_id = session['user']['id']
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Ensure user exists in the database
        if not ensure_user_exists(user_id, supabase_client):
            return jsonify({'error': 'Failed to ensure user exists in database'}), 500
        
        # Step 1: Generate description from the uploaded image
        print("Generating description from image...")
        image.seek(0)  # Reset file pointer for reading
        description, error = process_image_with_gpt4o(image)
        
        if error:
            return jsonify({'error': f'Failed to generate description: {error}'}), 500
        
        # Step 2: Generate manga character image from the description
        print(f"Generating character image from description: {description[:100]}...")
        image_url, error = generate_character_with_dalle(description)
        
        if error:
            return jsonify({'error': f'Failed to generate character image: {error}'}), 500
        
        # Generate an ID for the character
        character_id = str(uuid.uuid4())
        
        # Count existing characters for this user (excluding main character)
        character_count = supabase_client.table('characters').select('id').eq('user_id', user_id).eq('is_main_character', False).execute()
        
        # Check if we already have 5 supporting characters
        if len(character_count.data) >= 5:
            return jsonify({'error': 'You can only add up to 5 supporting characters. Please delete some to add more.'}), 400
        
        # Save the AI-generated image to Supabase Storage
        supabase_image_url = save_image_to_supabase(
            image_url,  # Use the DALL-E generated image URL instead of the uploaded image
            user_id, 
            is_main=False, 
            character_id=character_id
        )
        
        if not supabase_image_url:
            return jsonify({'error': 'Failed to save image to storage'}), 500
        
        # Add new character to Supabase - use authenticated client
        new_character = {
            'id': character_id,
            'user_id': user_id,
            'name': name,
            'image_url': supabase_image_url,  # Make sure this matches the template's expected property name
            'description': description,
            'is_main_character': False
        }
        
        # Use authenticated client for the insert operation
        print(f"Inserting new character: {new_character}")
        result = supabase_client.table('characters').insert(new_character).execute()
        print(f"Insert result: {result}")
        
        return jsonify({'success': True, 'character': new_character})
        
    except Exception as e:
        print(f"Error adding character: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # First verify that this character belongs to the user
        character = supabase_client.table('characters').select('*').eq('id', character_id).eq('user_id', user_id).execute()
        
        if not character.data:
            return jsonify({'error': 'Character not found or does not belong to user'}), 404
        
        # Delete the character from the database
        supabase_client.table('characters').delete().eq('id', character_id).execute()
        
        # Delete the image from storage
        try:
            supabase_client.storage.from_('character-images').remove([f"{user_id}/people/{character_id}.png"])
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
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get all non-main characters first
        regular_chars_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', False).execute()
        
        # Print for debugging
        print(f"Retrieved regular characters: {regular_chars_result.data}")
        
        if regular_chars_result.data:
            characters.extend(regular_chars_result.data)
        
        # Get main character (either from characters table or users table)
        main_char_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', True).execute()
        
        if main_char_result.data:
            # If main character exists in characters table
            print(f"Main character found in characters table: {main_char_result.data[0]}")
            characters.insert(0, main_char_result.data[0])  # Add main character to the beginning
        else:
            # Try to get main character from users table
            user_info = supabase_client.table('users').select('main_character_url, main_character_description').eq('id', user_id).execute()
            
            if user_info.data and user_info.data[0].get('main_character_url'):
                # Create a character object from user data
                main_char = {
                    'id': 'main',
                    'name': 'Main Character',
                    'image_url': user_info.data[0].get('main_character_url'),
                    'description': user_info.data[0].get('main_character_description'),
                    'is_main_character': True
                }
                print(f"Main character created from user data: {main_char}")
                characters.insert(0, main_char)  # Add main character to the beginning
    except Exception as e:
        print(f"Error fetching characters: {e}")
        import traceback
        traceback.print_exc()
    
    return render_template('people.html', user=session['user'], people=characters)


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