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
    

@app.route('/diagnose_folder', methods=['GET'])
def diagnose_folder():
    try:

        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        user_id = session['user']['id']
        
        # Create folder structure information
        folder_info = {
            'user_id': user_id,
            'path_structure': {
                'main_image_path': f"{user_id}/main.png",
                'sample_character_path': f"{user_id}/people/sample-uuid.png"
            },
            'path_extraction': {
                'foldername_first_segment': storage_foldername_simulation(f"{user_id}/main.png"),
                'position_check': f"{user_id}/main.png".startswith(user_id)
            },
            'token_info': {
                'has_token': 'supabase_token' in session,
                'token_length': len(session.get('supabase_token', '')) if 'supabase_token' in session else 0
            }
        }
        
        # Check if we can create the folder directly with service role
        try:
            test_file = b"test content"
            test_path = f"{user_id}/.folder_test"
            
            result = supabase_admin.storage.from_('character-images').upload(
                path=test_path,
                file=test_file,
                file_options={"content-type": "text/plain", "upsert": True}
            )
            
            folder_info['admin_test'] = {
                'success': True,
                'message': 'Folder test file created with admin client'
            }
        except Exception as e:
            folder_info['admin_test'] = {
                'success': False,
                'error': str(e)
            }
        
        return jsonify(folder_info)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
# Simple simulation of storage.foldername function for diagnostic purposes
def storage_foldername_simulation(path):
    parts = path.split('/')
    if len(parts) <= 1:
        return []
    return parts[:-1]  # All parts except the last (filename)

@app.route('/test_auth', methods=['GET'])
def test_auth():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        user_id = session['user']['id']
        
        # Try to get the user's auth status
        user_info = {
            'session_user_id': user_id,
            'session_data': session.get('user', {})
        }
        
        # Check if we can access the users table
        try:
            result = supabase.table('users').select('*').eq('id', user_id).execute()
            user_info['database_user'] = result.data
        except Exception as e:
            user_info['database_error'] = str(e)
        
        # Try to list buckets to see if we have any permissions
        try:
            buckets = supabase.storage.list_buckets()
            user_info['storage_buckets'] = buckets
        except Exception as e:
            user_info['storage_error'] = str(e)
            
        return jsonify(user_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/test_bucket', methods=['GET'])
def test_bucket():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        # Try to list all buckets
        try:
            buckets = supabase.storage.list_buckets()
        except Exception as e:
            return jsonify({'error': f'Error listing buckets: {str(e)}'}), 500
            
        # Check if our bucket exists
        bucket_exists = False
        for bucket in buckets:
            if bucket.get('name') == 'character-images':
                bucket_exists = True
                break
                
        if not bucket_exists:
            return jsonify({
                'error': 'Bucket "character-images" not found',
                'available_buckets': buckets
            }), 404
            
        # Try to list objects in the bucket
        try:
            user_id = session['user']['id']
            files = supabase.storage.from_('character-images').list(user_id)
            return jsonify({
                'bucket_exists': True,
                'user_folder_contents': files
            })
        except Exception as e:
            return jsonify({
                'bucket_exists': True,
                'list_error': str(e)
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        user_id = session['user']['id']
        
        # Create a simple test file
        test_content = b"This is a test file"
        
        # Try using the service role key directly (for debugging only)
        import supabase
        supabase_admin = supabase.create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')  # Service role key
        )
        
        file_path = f"{user_id}/test.txt"
        
        # Try the upload
        try:
            result = supabase_admin.storage.from_('character-images').upload(
                path=file_path,
                file=test_content,
                file_options={"content-type": "text/plain"}
            )
            
            url = supabase_admin.storage.from_('character-images').get_public_url(file_path)
            
            return jsonify({
                'success': True,
                'message': 'Test upload with service role successful',
                'url': url
            })
        except Exception as e:
            return jsonify({
                'error': f'Service role upload failed: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/debug_tokens', methods=['GET'])
def debug_tokens():
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
    if 'user' in session:
        return render_template('dashboard.html', user=session['user'])
    return render_template('login.html')

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
        access_token = data.get('access_token')  # This is the Supabase JWT
        refresh_token = data.get('refresh_token')
        # Store the JWT token
        access_token = data.get('access_token')
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
        
        try:
            user_query = supabase.table('users').select('*').eq('id', user_id).execute()
            
            if not user_query.data:
                # User doesn't exist, try to create
                user_data = {
                    'id': user_id,
                    'email': data.get('email'),
                    'name': data.get('user_metadata', {}).get('full_name'),
                    'picture': data.get('user_metadata', {}).get('avatar_url'),
                    'google_id': data.get('user_metadata', {}).get('sub')
                }
                print(f"Creating new user: {user_data}")
                
                supabase.table('users').insert(user_data).execute()
        except Exception as e:
            print(f"Error checking/creating user: {e}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Auth error: {e}")
        return jsonify({'error': str(e)}), 500

def save_image_to_supabase(image_url, user_id, is_main=False, character_id=None):
    try:
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
        
        # Upload the image to Supabase
        result = supabase_client.storage.from_('character-images').upload(
            path=file_path,
            file=image_bytes,
            file_options={"content-type": "image/png"}
        )
        
        print(f"Upload result: {result}")
        
        # Get the public URL
        public_url = supabase_client.storage.from_('character-images').get_public_url(file_path)
        return public_url
        
    except Exception as e:
        print(f"Error saving image to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/test_storage_upload', methods=['GET'])
def test_storage_upload():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        # Path to a test image in your project
        test_image_path = os.path.join(os.path.dirname(__file__), 'static', 'test_image.png')
        
        # Check if test image exists
        if not os.path.exists(test_image_path):
            # Try an alternative path
            test_image_path = os.path.join('static', 'test_image.png')
            if not os.path.exists(test_image_path):
                return jsonify({
                    'error': 'Test image not found. Please place a test_image.png file in your static folder',
                    'paths_tried': [
                        os.path.join(os.path.dirname(__file__), 'static', 'test_image.png'),
                        os.path.join('static', 'test_image.png')
                    ]
                }), 404
        
        print(f"Using test image at: {test_image_path}")
        
        user_id = session['user']['id']
        
        # Use our updated function to upload the image
        supabase_image_url = save_image_to_supabase(test_image_path, user_id, is_main=True)
        
        if not supabase_image_url:
            return jsonify({'error': 'Failed to upload test image to storage'}), 500
            
        return jsonify({
            'success': True,
            'message': 'Test image uploaded successfully',
            'image_url': supabase_image_url
        })
        
    except Exception as e:
        print(f"Error in test upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Test upload failed: {str(e)}'}), 500
    

@app.route('/test_blank_image_upload', methods=['GET'])
def test_blank_image_upload():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        # Create a blank test image
        from PIL import Image
        import io
        
        # Create a small blank image
        img = Image.new('RGB', (100, 100), color = (73, 109, 137))
        
        # Save to a bytes buffer
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        user_id = session['user']['id']
        
        # Define the file path in Supabase storage
        file_path = f"{user_id}/test_blank.png"
        
        # Upload directly
        result = supabase.storage.from_('character-images').upload(
            path=file_path,
            file=img_byte_arr.getvalue(),
            file_options={"content-type": "image/png"}
        )
        
        # Get the public URL
        public_url = supabase.storage.from_('character-images').get_public_url(file_path)
        
        return jsonify({
            'success': True,
            'message': 'Blank test image created and uploaded successfully',
            'image_url': public_url
        })
        
    except Exception as e:
        print(f"Error in blank image test: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Blank image test failed: {str(e)}'}), 500
    

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