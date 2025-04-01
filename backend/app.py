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
from apscheduler.schedulers.background import BackgroundScheduler
import time
import struct

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
@app.template_filter('datetime')
def format_datetime(value, format='%B %d, %Y at %I:%M %p'):
    """Format a datetime to a pretty string format."""
    if value is None:
        return ""
    
    # If the value is a string, try to parse it
    if isinstance(value, str):
        try:
            from dateutil import parser
            value = parser.parse(value)
        except Exception as e:
            print(f"Error parsing datetime: {e}")
            return value
    
    # Now format the datetime
    try:
        return value.strftime(format)
    except Exception as e:
        print(f"Error formatting datetime: {e}")
        return str(value)
    
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
    
def create_wav_file(sample_rate, audio_data):
    """
    Create a WAV file from raw audio bytes.
    
    Args:
        sample_rate (int): Audio sample rate (e.g., 16000)
        audio_data (bytes): Raw audio bytes from Omi device
        
    Returns:
        bytes: Complete WAV file with proper headers
    """
    num_channels = 1  # Mono audio
    bits_per_sample = 16
    bytes_per_sample = bits_per_sample // 8
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    
    # Create WAV header
    partial_header = (
        b'RIFF' + b'\x00\x00\x00\x00' + b'WAVE' +
        b'fmt ' + struct.pack('<I', 16) + struct.pack('<HHIIHH', 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample) +
        b'data' + struct.pack('<I', len(audio_data))
    )
    
    # Calculate total file size and RIFF chunk size
    total_file_size = len(partial_header) + len(audio_data)
    riff_chunk_size = total_file_size - 8
    
    # Update header with correct RIFF chunk size
    header = partial_header[:4] + struct.pack('<I', riff_chunk_size) + partial_header[8:]
    
    return header + audio_data
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
        dall_e_prompt = f"Create a COLORFUL, PLAYFUL, and WARM animation-style illustration of the character(s) described below in a friendly pose with a cheerful background: {description}. The image should be suitable for all audiences and faithfully represent the provided description with a pleasant, inviting aesthetic."
        
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
    
    
@app.route('/audio_stream', methods=['POST'])
def receive_audio():
    """
    Endpoint to receive audio data from Omi device.
    Enhanced with better debugging and error handling.
    
    Expected query parameters:
    - sample_rate: The audio sample rate in Hz
    - uid: The Omi device unique identifier
    
    Request body contains raw audio bytes
    """
    # Get query parameters
    sample_rate = int(request.args.get('sample_rate', 16000))
    omi_uid = request.args.get('uid')
    
    print(f"Received audio request with sample_rate={sample_rate}, uid={omi_uid}")
    
    if not omi_uid:
        print("Error: Missing uid parameter")
        return 'Missing uid parameter', 400
    
    # Get audio data from request body
    audio_data = request.data
    
    if not audio_data:
        print("Error: No audio data received")
        return 'No audio data received', 400
    
    print(f"Received {len(audio_data)} bytes of audio data")
    
    # Find user's ID based on omi_uid
    try:
        print(f"Querying users table for omi_uid={omi_uid}")
        
        # Try a case-insensitive query first
        result = supabase.table('users').select('id, email, name').ilike('omi_uid', omi_uid).execute()
        
        # If no results, try with exact match
        if not result.data:
            print(f"No users found with case-insensitive match, trying exact match")
            result = supabase.table('users').select('id, email, name').eq('omi_uid', omi_uid).execute()
        
        # Check if we have any results and print them for debugging
        if result.data:
            print(f"Found matching user: {result.data[0]}")
            user_id = result.data[0]['id']
        else:
            # Debug: Print all users with any omi_uid value to help diagnose
            all_users = supabase.table('users').select('id, email, name, omi_uid').not_.is_('omi_uid', None).execute()
            print(f"No users found with omi_uid={omi_uid}. All users with omi_uid: {all_users.data}")
            
            # Debug: Check if column exists and table structure
            try:
                table_info = supabase.table('users').select('*').limit(1).execute()
                print(f"Sample user record columns: {table_info.data[0].keys() if table_info.data else 'No users found'}")
            except Exception as col_err:
                print(f"Error checking table structure: {col_err}")
            
            return 'User not found for the provided uid', 404
    except Exception as e:
        print(f"Error finding user: {e}")
        import traceback
        traceback.print_exc()
        return 'Error processing user information', 500
    
    # Create the WAV file
    try:
        print(f"Creating WAV file from {len(audio_data)} bytes of raw audio")
        wav_file = create_wav_file(sample_rate, audio_data)
        print(f"Generated WAV file of {len(wav_file)} bytes")
    except Exception as e:
        print(f"Error creating WAV file: {e}")
        import traceback
        traceback.print_exc()
        return 'Error processing audio data', 500
    
    # Generate a unique filename using timestamp
    timestamp = datetime.now().isoformat().replace(':', '-')
    file_path = f"{user_id}/{timestamp}.wav"
    print(f"File will be stored at: {file_path}")
    
    # Upload to Supabase storage
    try:
        # Check if bucket exists
        try:
            print("Checking if audio-files bucket exists")
            bucket_info = supabase.storage.list_buckets()
            bucket_names = [bucket.get('name') for bucket in bucket_info]
            print(f"Available buckets: {bucket_names}")
            
            if 'audio-files' not in bucket_names:
                print("WARNING: audio-files bucket doesn't exist!")
        except Exception as bucket_err:
            print(f"Error checking buckets: {bucket_err}")
            
        # Make sure the directory exists in storage
        try:
            print(f"Uploading file to storage at {file_path}")
            
            # Upload file to storage
            upload_result = supabase.storage.from_('audio-files').upload(
                path=file_path,
                file=wav_file,
                file_options={"content-type": "audio/wav"}
            )
            print(f"File upload successful: {upload_result}")
        except Exception as upload_err:
            print(f"Error uploading file: {upload_err}")
            import traceback
            traceback.print_exc()
            return 'Error uploading audio file to storage', 500
        
        # Insert record into audio_files table
        try:
            print("Creating record in audio_files table")
            insert_result = supabase.table('audio_files').insert({
                'user_id': user_id,
                'file_path': file_path,
                'transcription': None,
                'created_at': datetime.now().isoformat()
            }).execute()
            print(f"Record creation successful: {insert_result.data}")
        except Exception as db_err:
            print(f"Error creating database record: {db_err}")
            import traceback
            traceback.print_exc()
            # Even if record creation fails, the file is uploaded, so don't return error
            return 'Audio received and stored, but failed to create database record', 200
        
        return 'Audio received and stored successfully', 200
    except Exception as e:
        print(f"Unexpected error saving audio to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return 'Error storing audio file', 500
@app.route('/my_mangas')
def my_mangas():
    if 'user' not in session:
        return redirect('/login')
    
    user_id = session['user']['id']
    
    try:
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get all mangas for the user
        mangas_result = supabase_client.table('mangas').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        
        mangas = []
        if mangas_result.data:
            print(f"Retrieved {len(mangas_result.data)} mangas for user {user_id}")
            
            # For each manga, get the panels
            for manga in mangas_result.data:
                manga_id = manga['id']
                
                # Get panels for this manga
                panels_result = supabase_client.table('panels').select('*').eq('manga_id', manga_id).order('panel_number').execute()
                
                # Add panels to the manga
                manga['panels'] = panels_result.data if panels_result.data else []
                
                # Get a cover image (first panel's image)
                if manga['panels']:
                    manga['cover_image'] = manga['panels'][0]['image_url']
                else:
                    manga['cover_image'] = None
                
                mangas.append(manga)
        else:
            print(f"Retrieved 0 mangas for user {user_id}")
                
    except Exception as e:
        print(f"Error fetching mangas: {e}")
        import traceback
        traceback.print_exc()
        mangas = []
    
    return render_template('my_mangas.html', user=session['user'], mangas=mangas)

@app.route('/view_manga/<manga_id>')
def view_manga(manga_id):
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        user_id = session['user']['id']
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Verify the manga belongs to the user
        manga_result = supabase_client.table('mangas').select('*').eq('id', manga_id).eq('user_id', user_id).execute()
        
        if not manga_result.data:
            return jsonify({'error': 'Manga not found or does not belong to user'}), 404
        
        manga = manga_result.data[0]
        
        # Get all panels for this manga
        panels_result = supabase_client.table('panels').select('*').eq('manga_id', manga_id).order('panel_number').execute()
        
        if not panels_result.data:
            return jsonify({'error': 'No panels found for this manga'}), 404
        
        # Get the index of this manga in the user's collection (for display purposes)
        manga_index_result = supabase_client.table('mangas').select('id').eq('user_id', user_id).order('created_at', desc=True).execute()
        manga_index = 0
        
        if manga_index_result.data:
            manga_ids = [m['id'] for m in manga_index_result.data]
            try:
                manga_index = manga_ids.index(manga_id) + 1  # 1-based index for display
            except ValueError:
                manga_index = 0
        
        # Return the panels and manga info
        return jsonify({
            'success': True,
            'manga': manga,
            'panels': panels_result.data,
            'index': manga_index
        })
        
    except Exception as e:
        print(f"Error viewing manga: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to view manga: {str(e)}'}), 500
    
def generate_manga_panels_with_dalle(panels, dialogues):
    """Generate panel images using DALL-E with improved error handling and rate limits"""
    try:
        print("=== Starting DALL-E image generation ===")
        
        if not OPENAI_API_KEY:
            print("Error: OpenAI API key is not set")
            return None
        
        # Add panel_number to each panel
        for i, panel in enumerate(panels):
            panel["panel_number"] = i
        
        # Function to generate a single image with DALL-E
        def generate_panel_image(panel):
            try:
                panel_number = panel.get("panel_number")
                description = panel.get("description", "")
                
                # Build the prompt by combining panel description with character descriptions
                prompt_parts = [description]
                
                # Add character descriptions if available
                for key, value in panel.items():
                    if key not in ["description", "panel_number"] and isinstance(value, str):
                        prompt_parts.append(f"{key}: {value}")
                
                # Combine into a final prompt with playful animation style instructions
                prompt = "Create a COLORFUL and WARM animation-style illustration. " + \
                         "The image should be PLAYFUL and PLEASANT with cheerful colors and a positive mood. " + \
                         "Scene: " + " ".join(prompt_parts)
                
                # Limit prompt to a reasonable length for DALL-E
                if len(prompt) > 3800:  # DALL-E has a limit around 4000 chars
                    prompt = prompt[:3800]
                
                print(f"Generating image for panel {panel_number}...")
                print(f"Prompt (truncated): {prompt[:200]}...")
                
                headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "quality": "standard",
                    "style": "vivid"  # Using vivid for more vibrant, colorful imagery
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_data = response.json().get('error', {})
                    error_code = error_data.get('code', '')
                    error_message = error_data.get('message', response.text)
                    
                    print(f"Error generating image for panel {panel_number}: {error_message}")
                    
                    return {
                        "panel_number": panel_number,
                        "image_url": None,
                        "error": error_code,
                        "error_message": error_message
                    }
                
                result = response.json()
                image_url = result['data'][0]['url']
                
                print(f"Successfully generated image for panel {panel_number}")
                
                return {
                    "panel_number": panel_number,
                    "image_url": image_url,
                    "error": None
                }
            
            except Exception as e:
                print(f"Error generating image for panel {panel_number}: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "panel_number": panel.get("panel_number"),
                    "image_url": None,
                    "error": "exception",
                    "error_message": str(e)
                }
        
        # Process panels in smaller batches to avoid rate limits
        max_concurrent = 4  # Reduced from 5 to be safe with rate limits
        batch_results = []
        
        # Process first batch
        first_batch = panels[:max_concurrent]
        print(f"Processing first batch of {len(first_batch)} panels...")
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = [executor.submit(generate_panel_image, panel) for panel in first_batch]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    batch_results.append(result)
        
        # Wait for rate limit to reset
        if len(panels) > max_concurrent:
            print("Waiting 60 seconds for rate limit to reset before processing next batch...")
            import time
            time.sleep(60)
        
        # Process remaining panels in batches
        remaining_panels = panels[max_concurrent:]
        while remaining_panels:
            current_batch = remaining_panels[:max_concurrent]
            remaining_panels = remaining_panels[max_concurrent:]
            
            print(f"Processing next batch of {len(current_batch)} panels...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                futures = [executor.submit(generate_panel_image, panel) for panel in current_batch]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        batch_results.append(result)
            
            # Wait for rate limit to reset if more panels remain
            if remaining_panels:
                print("Waiting 60 seconds for rate limit to reset before processing next batch...")
                import time
                time.sleep(60)
        
        # Check for failed panels
        failed_panels = [result for result in batch_results if result.get("error")]
        
        # Retry failed panels with content policy violations
        content_policy_failures = [p for p in failed_panels if p.get("error") == "content_policy_violation"]
        if content_policy_failures:
            print(f"Retrying {len(content_policy_failures)} panels that failed due to content policy violations...")
            
            for failed in content_policy_failures:
                panel_number = failed.get("panel_number")
                panel = next((p for p in panels if p.get("panel_number") == panel_number), None)
                
                if panel:
                    # Modify the prompt to avoid policy violations
                    # This is a simplified approach - in a real implementation, 
                    # you might want to use GPT-4 to modify the prompt
                    description = panel.get("description", "")
                    
                    # Create a sanitized version with less specific details
                    sanitized_description = "A cheerful animated scene showing character in a simple, pleasant setting."
                    
                    # Create a new panel with sanitized description
                    sanitized_panel = panel.copy()
                    sanitized_panel["description"] = sanitized_description
                    
                    print(f"Retrying panel {panel_number} with sanitized description...")
                    
                    # Wait to avoid rate limits
                    time.sleep(5)
                    
                    result = generate_panel_image(sanitized_panel)
                    if result and not result.get("error"):
                        # Replace the failed result with the successful one
                        for i, r in enumerate(batch_results):
                            if r.get("panel_number") == panel_number:
                                batch_results[i] = result
                                break
        
        # Sort results by panel_number to maintain original order
        sorted_results = sorted(batch_results, key=lambda x: x.get("panel_number", 0))
        
        # Create the final manga data structure
        manga_data = []
        for i, result in enumerate(sorted_results):
            panel_number = result.get("panel_number")
            dialogue = dialogues[panel_number] if panel_number < len(dialogues) else ""
            
            manga_data.append({
                "panel_number": panel_number,
                "image_url": result.get("image_url"),
                "dialogue": dialogue,
                "error": result.get("error"),
                "error_message": result.get("error_message", "")
            })
        
        print(f"Completed generating {len(manga_data)} story panels")
        return manga_data
        
    except Exception as e:
        print(f"Error in generate_manga_panels_with_dalle: {e}")
        import traceback
        traceback.print_exc()
        return None
        
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

@app.route('/debug_auth', methods=['GET'])
def debug_auth():
    if 'user' not in session:
        return jsonify({'status': 'Not logged in'}), 401
    
    user_id = session['user']['id']
    has_token = 'supabase_token' in session and session['supabase_token']
    has_refresh = 'supabase_refresh_token' in session and session['supabase_refresh_token']
    
    # Test the token
    auth_status = 'Unknown'
    user_data = None
    
    try:
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Try to get user data to verify authentication
        if has_token:
            try:
                user_result = supabase_client.auth.get_user()
                auth_status = 'Valid'
                user_data = {
                    'id': user_result.user.id,
                    'email': user_result.user.email
                }
            except Exception as auth_err:
                auth_status = f'Invalid: {str(auth_err)}'
        
        # Try to get user from database
        try:
            db_result = supabase_client.table('users').select('*').eq('id', user_id).execute()
            db_access = {
                'success': True,
                'found': len(db_result.data) > 0,
                'data': db_result.data[0] if db_result.data else None
            }
        except Exception as db_err:
            db_access = {
                'success': False, 
                'error': str(db_err)
            }
            
        return jsonify({
            'user_id': user_id,
            'has_token': has_token, 
            'has_refresh_token': has_refresh,
            'auth_status': auth_status,
            'user_data': user_data,
            'database_access': db_access
        })
        
    except Exception as e:
        return jsonify({
            'user_id': user_id,
            'error': str(e),
            'has_token': has_token,
            'has_refresh_token': has_refresh
        }), 500
        
@app.route('/debug_user', methods=['GET'])
def debug_user():
    """Debug endpoint to check a specific user"""
    try:
        # Use the specific user ID we know exists
        user_id = "38bb84dc-bc8a-44f5-8e26-8ad312ea519a"
        
        # Direct query for this user
        result = supabase.table('users').select('id, email, name, omi_uid').eq('id', user_id).execute()
        
        return jsonify({
            'user_id': user_id,
            'user_data': result.data,
            'found': len(result.data) > 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

# Add these functions to your app.py file

def create_manga(user_id):
    """Create a new manga entry for the user and return it"""
    try:
        print(f"Creating new manga for user {user_id}")
        result = supabase.table("mangas").insert({"user_id": user_id}).execute()
        print(f"Created manga with ID: {result.data[0]['id']}")
        return result.data[0]
    except Exception as e:
        print(f"Error creating manga: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_panels(manga_id, panels_data):
    """
    Save panel data to the database
    panels_data should be a list of dicts with: panel_number, image_url, dialogue
    """
    try:
        print(f"Saving {len(panels_data)} panels for manga {manga_id}")
        
        # Format the panels for database insert
        panel_records = []
        for panel in panels_data:
            panel_records.append({
                "manga_id": manga_id,
                "panel_number": panel.get("panel_number", 0),
                "image_url": panel.get("image_url", ""),
                "dialogue": panel.get("dialogue", "")
            })
        
        if not panel_records:
            print("No panel data to save")
            return []
            
        result = supabase.table("panels").insert(panel_records).execute()
        print(f"Saved {len(result.data)} panels to database")
        return result.data
    except Exception as e:
        print(f"Error saving panels: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_manga_count(user_id):
    """Get the count of mangas for a user"""
    try:
        result = supabase.table("mangas").select("id", count="exact").eq("user_id", user_id).execute()
        count = result.count
        print(f"User {user_id} has {count} mangas")
        return count
    except Exception as e:
        print(f"Error getting manga count: {e}")
        return 0

def get_panel_count(manga_id):
    """Get the count of panels for a manga"""
    try:
        result = supabase.table("panels").select("id", count="exact").eq("manga_id", manga_id).execute()
        count = result.count
        print(f"Manga {manga_id} has {count} panels")
        return count
    except Exception as e:
        print(f"Error getting panel count: {e}")
        return 0

def get_user_mangas(user_id, limit=10):
    """Get the user's mangas with their panels"""
    try:
        # Get the mangas
        manga_result = supabase.table("mangas").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        
        mangas = []
        for manga in manga_result.data:
            # Get panels for this manga
            panels_result = supabase.table("panels").select("*").eq("manga_id", manga["id"]).order("panel_number").execute()
            
            # Add panels to manga
            manga_with_panels = {
                **manga,
                "panels": panels_result.data
            }
            mangas.append(manga_with_panels)
            
        print(f"Retrieved {len(mangas)} mangas for user {user_id}")
        return mangas
    except Exception as e:
        print(f"Error getting user mangas: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_manga_by_id(manga_id):
    """Get a specific manga with its panels"""
    try:
        # Get the manga
        manga_result = supabase.table("mangas").select("*").eq("id", manga_id).execute()
        
        if not manga_result.data:
            print(f"Manga {manga_id} not found")
            return None
            
        manga = manga_result.data[0]
        
        # Get panels for this manga
        panels_result = supabase.table("panels").select("*").eq("manga_id", manga_id).order("panel_number").execute()
        
        # Add panels to manga
        manga_with_panels = {
            **manga,
            "panels": panels_result.data
        }
        
        print(f"Retrieved manga {manga_id} with {len(panels_result.data)} panels")
        return manga_with_panels
    except Exception as e:
        print(f"Error getting manga: {e}")
        import traceback
        traceback.print_exc()
        return None

# Update your route handlers to use these functions

# Add this code to your app.py file
# Modify the save_manga route to provide better debugging

@app.route('/save_manga', methods=['POST'])
def save_manga():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.json
        print("Received data keys:", data.keys())
        
        # Check for manga_panels or panels key
        manga_panels = data.get('manga_panels')
        if not manga_panels:
            # Try the 'panels' key as a fallback
            manga_panels = data.get('panels')
            
        if not manga_panels:
            print("No manga panels data found in request")
            print("Request data:", data)
            return jsonify({'error': 'No manga panels provided'}), 400
        
        print(f"Processing {len(manga_panels)} manga panels")
        
        user_id = session['user']['id']
        print(f"Creating new manga for user {user_id}")
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Create manga record
        try:
            manga_insert = supabase_client.table('mangas').insert({
                'user_id': user_id,
                'created_at': datetime.now().isoformat()
            }).execute()
            
            if not manga_insert.data:
                return jsonify({'error': 'Failed to create manga record'}), 500
                
            manga_id = manga_insert.data[0]['id']
            print(f"Created manga with ID: {manga_id}")
        except Exception as e:
            print(f"Error creating manga: {e}")
            return jsonify({'error': f'Failed to create manga: {str(e)}'}), 500
        
        # Process each panel
        panels_data = []
        for panel in manga_panels:
            panel_number = panel.get('panel_number', 0)
            image_url = panel.get('image_url')
            dialogue = panel.get('dialogue', '')
            
            print(f"Processing panel {panel_number}")
            
            if not image_url:
                print(f"Skipping panel {panel_number} due to missing image URL")
                continue
                
            try:
                # Download the image
                response = requests.get(image_url)
                if response.status_code != 200:
                    print(f"Error downloading image for panel {panel_number}: Status {response.status_code}")
                    continue
                    
                # Generate a file path for the panel
                file_path = f"{user_id}/manga/{manga_id}/panel_{panel_number}.png"
                
                print(f"Uploading to path: {file_path}")
                
                # Make sure the directory exists in the storage
                try:
                    # Upload to Supabase storage
                    supabase_client.storage.from_('manga-panels').upload(
                        path=file_path,
                        file=response.content,
                        file_options={"content-type": "image/png"}
                    )
                    print(f"Successfully uploaded panel {panel_number}")
                except Exception as upload_error:
                    print(f"Upload error for panel {panel_number}: {upload_error}")
                    # If error is that the file already exists, we can continue
                    if "The resource already exists" not in str(upload_error):
                        continue
                
                # Get the URL for the panel image
                try:
                    signed_url = supabase_client.storage.from_('manga-panels').create_signed_url(
                        path=file_path,
                        expires_in=31536000  # 1 year in seconds
                    )
                    
                    storage_url = signed_url['signedURL'] if isinstance(signed_url, dict) and 'signedURL' in signed_url else None
                    
                    if not storage_url:
                        print(f"Failed to get storage URL for panel {panel_number}")
                        continue
                    
                    print(f"Got storage URL for panel {panel_number}")
                except Exception as url_error:
                    print(f"Error getting signed URL for panel {panel_number}: {url_error}")
                    continue
                
                # Create panel record
                panel_data = {
                    'manga_id': manga_id,
                    'panel_number': panel_number,
                    'image_url': storage_url,
                    'dialogue': dialogue
                }
                
                panels_data.append(panel_data)
                print(f"Added panel {panel_number} to panels_data")
                
            except Exception as e:
                print(f"Error processing panel {panel_number}: {e}")
                import traceback
                traceback.print_exc()
        
        # Insert all panels
        if panels_data:
            try:
                print(f"Inserting {len(panels_data)} panels into database")
                panels_insert = supabase_client.table('panels').insert(panels_data).execute()
                print(f"Inserted {len(panels_insert.data)} panels")
            except Exception as e:
                print(f"Error inserting panels: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Failed to save panels: {str(e)}'}), 500
        else:
            print("No panels data to insert")
        
        return jsonify({
            'success': True,
            'manga_id': manga_id,
            'panel_count': len(panels_data)
        })
        
    except Exception as e:
        print(f"Error in save_manga: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to save manga: {str(e)}'}), 500
       
@app.route('/get_mangas', methods=['GET'])
def get_mangas():
    """Get the user's mangas"""
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        user_id = session['user']['id']
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get user's mangas
        mangas = get_user_mangas(user_id)
        
        return jsonify({
            'success': True,
            'mangas': mangas,
            'count': len(mangas)
        })
        
    except Exception as e:
        print(f"Error fetching mangas: {e}")
        return jsonify({'error': f'Failed to fetch mangas: {str(e)}'}), 500

@app.route('/get_manga/<manga_id>', methods=['GET'])
def get_manga(manga_id):
    """Get a specific manga"""
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
            
        user_id = session['user']['id']
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get the manga
        manga = get_manga_by_id(manga_id)
        
        if not manga:
            return jsonify({'error': 'Manga not found'}), 404
            
        # Check if the manga belongs to the user
        if manga['user_id'] != user_id:
            return jsonify({'error': 'Unauthorized access to manga'}), 403
            
        return jsonify({
            'success': True,
            'manga': manga
        })
        
    except Exception as e:
        print(f"Error fetching manga: {e}")
        return jsonify({'error': f'Failed to fetch manga: {str(e)}'}), 500

# Modify your generate_manga route to optionally save manga directly
@app.route('/generate_manga', methods=['POST'])
def generate_manga():
    try:
        print("=== Starting generate_manga route ===")
        
        if 'user' not in session:
            print("Error: User not logged in")
            return jsonify({'error': 'Not logged in'}), 401
        
        print(f"User authenticated: {session['user'].get('id')}")
        
        data = request.json
        if not data:
            print("Error: No JSON data in request")
            return jsonify({'error': 'No data provided'}), 400
            
        script = data.get('script')
        print(f"Received script: {script[:100]}...")  # Print first 100 chars of script
        
        if not script:
            print("Error: No script provided in request data")
            return jsonify({'error': 'No script provided'}), 400
        
        # Request parameters
        generate_images = data.get('generate_images', False)
        save_to_database = data.get('save_to_database', False)
        
        user_id = session['user']['id']
        print(f"Processing for user ID: {user_id}")
        
        # Get authenticated client
        print("Getting authenticated Supabase client...")
        try:
            supabase_client = get_authenticated_supabase(user_id)
            print("Successfully got Supabase client")
        except Exception as e:
            print(f"Error getting Supabase client: {e}")
            return jsonify({'error': f'Authentication error: {str(e)}'}), 500
        
        # Get user's characters
        print("Fetching user's characters...")
        characters = []
        
        # Get main character
        try:
            print("Fetching main character...")
            main_char_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', True).execute()
            print(f"Main character query result: {main_char_result.data}")
            
            main_character = None
            if main_char_result.data:
                main_character = main_char_result.data[0]
                print(f"Found main character: {main_character.get('name')}")
            else:
                # Try to get main character from users table
                print("No main character in characters table, checking users table...")
                user_info = supabase_client.table('users').select('main_character_url, main_character_description').eq('id', user_id).execute()
                print(f"User info result: {user_info.data}")
                
                if user_info.data and user_info.data[0].get('main_character_description'):
                    main_character = {
                        'name': 'Main Character',
                        'description': user_info.data[0].get('main_character_description')
                    }
                    print(f"Created main character from user data: {main_character}")
            
            if main_character:
                characters.append(main_character)
                print("Added main character to characters list")
            else:
                print("No main character found for user")
                
        except Exception as e:
            print(f"Error fetching main character: {e}")
            import traceback
            traceback.print_exc()
        
        # Get supporting characters
        try:
            print("Fetching supporting characters...")
            supporting_chars_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', False).execute()
            print(f"Found {len(supporting_chars_result.data)} supporting characters")
            
            if supporting_chars_result.data:
                characters.extend(supporting_chars_result.data)
                print(f"Added supporting characters to characters list. Total characters: {len(characters)}")
        except Exception as e:
            print(f"Error fetching supporting characters: {e}")
            import traceback
            traceback.print_exc()
        
        # Process the script with GPT-4o
        print("Processing script with GPT-4o...")
        manga_data = process_script_with_gpt4o(script, characters)
        
        if not manga_data:
            print("Error: GPT-4o processing returned no data")
            return jsonify({'error': 'Failed to generate manga panels'}), 500
        
        # Extract panels and dialogues from the processed data
        panels = manga_data.get('panels', [])
        dialogues = manga_data.get('dialogues', [])
        
        print(f"Successfully processed data: {len(panels)} panels and {len(dialogues)} dialogues")
        
        # If generate_images is True, generate images with DALL-E
        manga_panels = None
        if generate_images:
            print("Generating images with DALL-E...")
            manga_panels = generate_manga_panels_with_dalle(panels, dialogues)
            
            if not manga_panels:
                print("Error: DALL-E processing returned no data")
                return jsonify({
                    'success': True,
                    'panels': panels,
                    'dialogues': dialogues,
                    'error': 'Image generation failed'
                })
            
            # If save_to_database is True, save the manga and panels
            if save_to_database and manga_panels:
                try:
                    print("Saving manga to database...")
                    # Create a new manga entry
                    manga = create_manga(user_id)
                    
                    if manga:
                        # Save panels
                        saved_panels = create_panels(manga['id'], manga_panels)
                        
                        # Get counts for logging
                        manga_count = get_manga_count(user_id)
                        panel_count = get_panel_count(manga['id'])
                        
                        print(f"Saved manga with ID: {manga['id']}")
                        print(f"Total mangas for user: {manga_count}")
                        print(f"Total panels for this manga: {panel_count}")
                        
                        return jsonify({
                            'success': True,
                            'manga_panels': manga_panels,
                            'manga_id': manga['id'],
                            'saved': True,
                            'manga_count': manga_count,
                            'panel_count': panel_count
                        })
                except Exception as e:
                    print(f"Error saving manga to database: {e}")
                    # Continue without saving - just return the generated panels
            
            return jsonify({
                'success': True,
                'manga_panels': manga_panels  # Combined data with images and dialogues
            })
        else:
            # Return just the panels and dialogues without images
            return jsonify({
                'success': True,
                'panels': panels,
                'dialogues': dialogues
            })
        
    except Exception as e:
        print(f"Unexpected error in generate_manga: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to generate manga: {str(e)}'}), 500


# Modify your generate_manga route to optionally save manga directly

def enhance_panels_with_character_info(panels, character_descriptions):
    """
    Process panels to:
    1. Extract dialogues into a separate array
    2. Keep complete character descriptions
    3. Remove dialogue field from panel objects
    """
    enhanced_panels = []
    dialogues = []
    
    for panel in panels:
        # Extract dialogue to separate array
        dialogue = panel.get("dialogue", "")
        dialogues.append(dialogue)
        
        # Create a new panel object without the dialogue property
        enhanced_panel = {
            "description": panel.get("description", "")
        }
        
        # Find which characters are mentioned in this panel
        description = panel.get("description", "")
        mentioned_characters = []
        
        for character_name in character_descriptions.keys():
            # Check if character is mentioned in the description or dialogue
            # Using case-insensitive search
            if (character_name.lower() in description.lower() or 
                character_name.lower() in dialogue.lower()):
                mentioned_characters.append(character_name)
        
        # If no specific characters were detected, include the main character
        if not mentioned_characters and "Main Character" in character_descriptions:
            mentioned_characters.append("Main Character")
        
        # Add only relevant character descriptions to the panel - use full descriptions
        for character_name in mentioned_characters:
            full_desc = character_descriptions.get(character_name, "")
            enhanced_panel[character_name] = full_desc
        
        enhanced_panels.append(enhanced_panel)
    
    # Print the final payload structure
    print("\n=== FINAL PROCESSING RESULTS ===")
    print(f"Extracted {len(dialogues)} dialogues:")
    print(json.dumps(dialogues, indent=2))
    
    print(f"\nProcessed {len(enhanced_panels)} panels with character descriptions:")
    # Print a sample panel to avoid overwhelming the console
    sample_panel = json.dumps(enhanced_panels[0], indent=2)
    print(f"Sample panel (1 of {len(enhanced_panels)}):")
    print(sample_panel)
    
    # Return both the enhanced panels and dialogues
    return {
        "panels": enhanced_panels,
        "dialogues": dialogues
    }
def process_script_with_gpt4o(script, characters):
    """Process a day script with GPT-4o and return separated story panels and dialogues"""
    try:
        print("=== Starting process_script_with_gpt4o ===")
        
        # Create character context
        character_context = ""
        character_descriptions = {}  # Dictionary to store character name: description pairs
        
        if characters:
            character_context = "Available characters:\n"
            for char in characters:
                char_name = char.get('name', 'Unknown')
                char_desc = char.get('description', 'No description')
                
                # Store the full description for later use
                character_descriptions[char_name] = char_desc
                
                # Use truncated description for the prompt to save tokens
                character_context += f"- Name: {char_name}\n  Description: {char_desc[:100]}...\n\n"
            print(f"Created character context with {len(characters)} characters")
        else:
            print("No characters available for context")
        
        # Check for API key
        if not OPENAI_API_KEY:
            print("Error: OpenAI API key is not set")
            return None
        
        print("Preparing API request to OpenAI...")
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": f"""You are a storyboard artist who creates playful, warm, and pleasant animated stories based on real-life events.
                    
{character_context}

Your task is to select one significant event from the user's script and create a short animated story depicting that event through 8-12 panels (2-3 pages with 4 panels each).

FORMAT YOUR RESPONSE AS A JSON OBJECT with an array of panel objects. Each panel object must have these two properties:
- 'dialogue': A short, one-line dialogue involving the characters
- 'description': A detailed visual description of the scene suitable for generating a colorful, warm, and playful animated illustration

Example JSON format:
```json
{{
  "panels": [
    {{
      "dialogue": "I can't believe it's our anniversary today!",
      "description": "Close-up of main character's joyful face with bright eyes and big smile, surrounded by warm golden light"
      
    }},
    {{
      "dialogue": "I've planned something special!",
      "description": "Wide shot of character standing proudly next to a decorated table with colorful balloons, flowers, and a beautiful cake"
    }}
  ]
}}
```

Guidelines:
- The story should follow a coherent narrative about the chosen event
- Use characters mentioned in the script if their names appear; otherwise, use the main character
- Keep the style consistent with playful, pleasant animation with warm colors
- Ensure scene descriptions are detailed enough for image generation
- Make the dialogue authentic, engaging and positive
- Focus on creating cheerful, uplifting scenes when possible

Make sure descriptions focus on composition, expressions, colors, mood, and animation-specific visual elements.

Remember to format your entire response as a valid JSON object.
"""
                },
                {
                    "role": "user",
                    "content": f"Here is my script describing my day. Please create an animated story based on one significant event from it and format your response as JSON:\n\n{script}"
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        print("Sending request to OpenAI GPT-4o API...")
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            print(f"OpenAI API response status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"API Error: {response.text}")
                return None
                
            result = response.json()
            print("Successfully received response from OpenAI")
        except Exception as e:
            print(f"Error making request to OpenAI API: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        if 'choices' not in result:
            print(f"Unexpected API response format: {result}")
            return None
        
        content = result['choices'][0]['message']['content']
        print(f"Received content from GPT-4o: {content[:200]}...")  # First 200 chars
        
        # Parse the JSON response
        try:
            print("Parsing JSON response...")
            manga_data = json.loads(content)
            
            # Extract panels array if it exists, otherwise use the entire response as panels
            panels = manga_data.get('panels', [])
            if not panels and isinstance(manga_data, list):
                panels = manga_data
                
            if panels:
                print(f"Successfully parsed {len(panels)} panels")
                
                # Process panels to separate dialogues and add character information
                processed_data = enhance_panels_with_character_info(panels, character_descriptions)
                
                return processed_data
            else:
                print("No panels found in the response")
                return None
                
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response from GPT-4o: {e}")
            print(f"Raw content: {content}")
            return None
        
    except Exception as e:
        print(f"Unexpected error in process_script_with_gpt4o: {e}")
        import traceback
        traceback.print_exc()
        return None
      
def filter_panel_characters_simple(panel, character_descriptions):
    """Simple method to filter characters based on text matching"""
    dialogue = panel.get("dialogue", "")
    description = panel.get("description", "")
    
    # Create a new panel object with the original properties
    filtered_panel = {
        "dialogue": dialogue,
        "description": description
    }
    
    # Find which characters are mentioned in this panel
    mentioned_characters = []
    for character_name in character_descriptions.keys():
        # Check if character is mentioned in the description or dialogue
        # Using case-insensitive search
        if (character_name.lower() in description.lower() or 
            character_name.lower() in dialogue.lower()):
            mentioned_characters.append(character_name)
    
    # If no specific characters were detected, include the main character
    if not mentioned_characters and "Main Character" in character_descriptions:
        mentioned_characters.append("Main Character")
    
    # Add only relevant character descriptions to the panel
    for character_name in mentioned_characters:
        description = character_descriptions.get(character_name, "")
        # Create a shortened version of the character description
        short_desc = description[:150] + "..." if len(description) > 150 else description
        filtered_panel[character_name] = short_desc
    
    return filtered_panel

@app.route('/auth', methods=['POST'])
def auth():
    try:
        print("Received auth request")
        data = request.json
        
        # Extract user ID and access token from data
        user_id = data.get('id')
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        if not user_id or not access_token or not refresh_token:
            print("Missing required auth data")
            return jsonify({'error': 'Missing required authentication data'}), 400
        
        # Store tokens in session
        session['supabase_token'] = access_token
        session['supabase_refresh_token'] = refresh_token
        session['user'] = {
            'id': user_id,
            'email': data.get('email'),
            'name': data.get('user_metadata', {}).get('full_name'),
            'picture': data.get('user_metadata', {}).get('avatar_url')
        }
        
        print(f"Successfully authenticated user: {user_id}")
        
        # Create an authenticated client and ensure user exists in DB
        supabase_client = get_authenticated_supabase(user_id)
        
        # Test if authentication works by getting the user's data
        try:
            # This query should succeed if authentication is working
            test_result = supabase_client.auth.get_user()
            print(f"Token verification success: {test_result.user.id}")
            
            # Ensure the user exists in our database
            ensure_user_exists(user_id, supabase_client)
            
            return jsonify({
                'success': True,
                'auth_verified': True,
                'user_id': user_id
            })
        except Exception as auth_error:
            print(f"Token verification failed: {auth_error}")
            return jsonify({
                'success': True,  # Still consider login successful
                'auth_verified': False,
                'error': str(auth_error)
            })
            
    except Exception as e:
        print(f"Auth error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@app.route('/get-signed-image-url', methods=['POST'])
def get_signed_image_url():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    path = data.get('path')
    bucket = data.get('bucket', 'character-images')  # Default to character-images bucket
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    user_id = session['user']['id']
    
    try:
        supabase_client = get_authenticated_supabase(user_id)
        
        # Create a new signed URL with a 15-minute expiration
        signed_url = supabase_client.storage.from_(bucket).create_signed_url(
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
                    "content": "You are a creative art description assistant that helps translate visual elements into written descriptions for artistic recreation. Focus on creating warm, playful, and pleasant descriptions that highlight cheerful and positive aspects of the subject."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please provide a detailed artistic description of this person or character in a warm, playful, and pleasant style. Focus on creating a description that would work well for a colorful, cheerful animated character. Highlight positive qualities, friendly expressions, distinctive features, and colorful elements that would translate well to a warm animation style. Avoid any content that could be inappropriate for general audiences."
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
    
def retry_with_backoff(func, panel, max_retries=3, base_delay=60):
    """Retry a function with exponential backoff for rate limit errors"""
    for attempt in range(max_retries):
        result = func(panel)
        
        # If successful or not a rate limit error, return the result
        if not result.get("error") or result.get("error") != "rate_limit_exceeded":
            return result
        
        # Calculate delay with exponential backoff (60s, 120s, 240s, etc.)
        delay = base_delay * (2 ** attempt)
        print(f"Rate limit exceeded. Retrying in {delay} seconds (attempt {attempt + 1}/{max_retries})...")
        
        import time
        time.sleep(delay)
    
    # If we've exhausted all retries, return the last result
    return result

@app.route('/retry_panel_image', methods=['POST'])
def retry_panel_image():
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.json
        panel_number = data.get('panel_number')
        script = data.get('script')
        
        if panel_number is None or script is None:
            return jsonify({'error': 'Missing panel number or script'}), 400
        
        user_id = session['user']['id']
        
        # Get the user's characters for context
        supabase_client = get_authenticated_supabase(user_id)
        characters = []
        
        # Get main character
        main_char_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', True).execute()
        if main_char_result.data:
            characters.append(main_char_result.data[0])
        
        # Get supporting characters
        supporting_chars_result = supabase_client.table('characters').select('*').eq('user_id', user_id).eq('is_main_character', False).execute()
        if supporting_chars_result.data:
            characters.extend(supporting_chars_result.data)
        
        # Process the script again to get panel data
        # Note: For efficiency, you might want to store this data in the session instead
        manga_data = process_script_with_gpt4o(script, characters)
        
        if not manga_data:
            return jsonify({'error': 'Failed to process script'}), 500
        
        panels = manga_data.get('panels', [])
        dialogues = manga_data.get('dialogues', [])
        
        # Get the specific panel to retry
        if panel_number >= len(panels):
            return jsonify({'error': 'Invalid panel number'}), 400
        
        panel = panels[panel_number]
        panel['panel_number'] = panel_number
        
        # Create a sanitized prompt if the previous error was content policy violation
        if data.get('error') == 'content_policy_violation':
            # Simplify the description to avoid policy violations
            original_description = panel.get('description', '')
            panel['description'] = "A manga scene with characters in conversation. " + \
                                  original_description.split('.')[0]  # Use just the first sentence
        
        # Generate the image for this panel
        result = generate_panel_image(panel)
        
        if result and result.get('image_url'):
            return jsonify({
                'success': True,
                'panel': {
                    'panel_number': panel_number,
                    'image_url': result.get('image_url'),
                    'dialogue': dialogues[panel_number] if panel_number < len(dialogues) else ''
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error_message', 'Failed to generate image')
            })
    
    except Exception as e:
        print(f"Error retrying panel image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error: {str(e)}'}), 500

# Helper function from the previous implementation
def generate_panel_image(panel):
    try:
        panel_number = panel.get("panel_number")
        description = panel.get("description", "")
        
        # Build the prompt by combining panel description with character descriptions
        prompt_parts = [description]
        
        # Add character descriptions if available
        for key, value in panel.items():
            if key not in ["description", "panel_number"] and isinstance(value, str):
                prompt_parts.append(f"{key}: {value}")
        
        # Combine into a final prompt with manga style instructions
        prompt = "Create a BLACK AND WHITE ONLY image in a MANGA style. " + \
                 "The image should look like it was SKETCHED with pen and ink, with strong lines and contrasts. " + \
                 "Scene: " + " ".join(prompt_parts)
        
        # Limit prompt to a reasonable length for DALL-E
        if len(prompt) > 3800:  # DALL-E has a limit around 4000 chars
            prompt = prompt[:3800]
        
        print(f"Generating image for panel {panel_number}...")
        print(f"Prompt (truncated): {prompt[:200]}...")
        
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "quality": "standard",
            "style": "vivid"  # Using vivid for more dramatic manga-like imagery
        }
        
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            error_data = response.json().get('error', {})
            error_code = error_data.get('code', '')
            error_message = error_data.get('message', response.text)
            
            print(f"Error generating image for panel {panel_number}: {error_message}")
            
            return {
                "panel_number": panel_number,
                "image_url": None,
                "error": error_code,
                "error_message": error_message
            }
        
        result = response.json()
        image_url = result['data'][0]['url']
        
        print(f"Successfully generated image for panel {panel_number}")
        
        return {
            "panel_number": panel_number,
            "image_url": image_url,
            "error": None
        }
    
    except Exception as e:
        print(f"Error generating image for panel {panel_number}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "panel_number": panel.get("panel_number"),
            "image_url": None,
            "error": "exception",
            "error_message": str(e)
        }
    
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


################TESTING@@@@@@@@@@@@
# Add these diagnostic routes to your Flask app

@app.route('/debug_omi_uid', methods=['GET'])
def debug_omi_uid():
    """
    Debug endpoint to check if an Omi UID exists in the database.
    
    Query parameters:
    - uid: The Omi UID to check
    """
    try:
        # Get the UID to check
        uid = request.args.get('uid')
        if not uid:
            return jsonify({
                'error': 'No UID provided',
                'usage': 'Add ?uid=YOUR_OMI_UID to the URL'
            }), 400
        
        print(f"Checking for omi_uid: {uid}")
        
        # Use service client (not authenticated) to ensure we're not limited by RLS
        result = supabase.table('users').select('id, email, name, omi_uid').eq('omi_uid', uid).execute()
        
        # Additional debug query to see all users with omi_uid set
        all_users_with_omi = supabase.table('users').select('id, email, name, omi_uid').not_.is_('omi_uid', None).execute()
        
        return jsonify({
            'query': f"omi_uid = '{uid}'",
            'matched_users': result.data,
            'matches_found': len(result.data),
            'all_users_with_omi': all_users_with_omi.data,
            'total_users_with_omi': len(all_users_with_omi.data)
        })
    except Exception as e:
        print(f"Error in debug_omi_uid: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/set_omi_uid', methods=['GET', 'POST'])
def set_omi_uid():
    """
    Endpoint to set the Omi UID for a user.
    
    GET: Show a simple form
    POST: Process the form and update the database
    """
    if 'user' not in session:
        return 'Not logged in. Please log in first.', 401
    
    user_id = session['user']['id']
    
    if request.method == 'GET':
        # Get current omi_uid for this user
        try:
            supabase_client.table('users').update({'omi_uid': uid}).eq('id', user_id).execute()

            result = supabase_client.table('users').select('omi_uid').eq('id', user_id).execute()
            current_uid = result.data[0]['omi_uid'] if result.data and 'omi_uid' in result.data[0] else None
        except Exception as e:
            print(f"Error getting current omi_uid: {e}")
            current_uid = None
        
        # Return a simple HTML form
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Set Omi UID</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .form-group {{ margin-bottom: 20px; }}
                label {{ display: block; margin-bottom: 5px; }}
                input[type=text] {{ width: 100%; padding: 8px; font-size: 16px; }}
                button {{ padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }}
                .current {{ margin-bottom: 20px; padding: 15px; background-color: #f8f8f8; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Set Omi Device UID</h1>
                
                <div class="current">
                    <h3>Current Settings</h3>
                    <p><strong>User ID:</strong> {user_id}</p>
                    <p><strong>Current Omi UID:</strong> {current_uid or 'Not set'}</p>
                </div>
                
                <form method="POST" action="/set_omi_uid">
                    <div class="form-group">
                        <label for="uid">Enter your Omi device UID:</label>
                        <input type="text" id="uid" name="uid" value="{current_uid or ''}" required>
                    </div>
                    <button type="submit">Save</button>
                </form>
            </div>
        </body>
        </html>
        """
    else:  # POST
        uid = request.form.get('uid')
        if not uid:
            return 'No UID provided', 400
        
        try:
            print(f"Setting omi_uid={uid} for user {user_id}")
            
            # Get authenticated client
            supabase_client = get_authenticated_supabase(user_id)
            
            # Update the user record
            update_result = supabase_client.table('users').update({'omi_uid': uid}).eq('id', user_id).execute()
            
            print(f"Update result: {update_result}")
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Omi UID Updated</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .container {{ max-width: 600px; margin: 0 auto; text-align: center; }}
                    .success {{ color: #4CAF50; }}
                    .button {{ display: inline-block; margin-top: 20px; padding: 10px 15px; background-color: #4CAF50; color: white; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="success">Success!</h1>
                    <p>Your Omi UID has been set to: <strong>{uid}</strong></p>
                    <p>You can now use your Omi device to send audio to your account.</p>
                    <a href="/" class="button">Back to Dashboard</a>
                </div>
            </body>
            </html>
            """
        except Exception as e:
            print(f"Error setting UID: {e}")
            import traceback
            traceback.print_exc()
            return f'Failed to set UID: {str(e)}', 500

@app.route('/test_audio_upload', methods=['GET'])
def test_audio_upload_form():
    """
    Display a form for testing audio upload without an actual Omi device
    """
    if 'user' not in session:
        return 'Not logged in. Please log in first.', 401
    
    user_id = session['user']['id']
    
    # Get current omi_uid for this user
    try:
        result = supabase.table('users').select('omi_uid').eq('id', user_id).execute()
        current_uid = result.data[0]['omi_uid'] if result.data and 'omi_uid' in result.data[0] else None
    except Exception as e:
        print(f"Error getting current omi_uid: {e}")
        current_uid = None
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Audio Upload</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 5px; }}
            input[type=file], input[type=text], input[type=number] {{ width: 100%; padding: 8px; font-size: 16px; margin-bottom: 10px; }}
            button {{ padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }}
            .current {{ margin-bottom: 20px; padding: 15px; background-color: #f8f8f8; border-radius: 4px; }}
            .note {{ font-size: 14px; color: #666; margin-top: 5px; }}
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const form = document.getElementById('uploadForm');
                form.addEventListener('submit', async function(e) {{
                    e.preventDefault();
                    
                    const uid = document.getElementById('uid').value;
                    const sampleRate = document.getElementById('sampleRate').value;
                    const audioFile = document.getElementById('audioFile').files[0];
                    
                    if (!uid || !audioFile) {{
                        alert('Please provide both UID and audio file');
                        return;
                    }}
                    
                    // Read file as ArrayBuffer
                    const reader = new FileReader();
                    reader.onload = async function(e) {{
                        const arrayBuffer = e.target.result;
                        
                        try {{
                            // Send the request
                            const response = await fetch(`/audio_stream?sample_rate=${{sampleRate}}&uid=${{uid}}`, {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/octet-stream'
                                }},
                                body: arrayBuffer
                            }});
                            
                            const result = await response.text();
                            const resultElement = document.getElementById('result');
                            
                            if (response.ok) {{
                                resultElement.innerHTML = `<div class="success">
                                    <h3>Success!</h3>
                                    <p>${{result}}</p>
                                </div>`;
                            }} else {{
                                resultElement.innerHTML = `<div class="error">
                                    <h3>Error (${{response.status}})</h3>
                                    <p>${{result}}</p>
                                </div>`;
                            }}
                        }} catch (error) {{
                            document.getElementById('result').innerHTML = `<div class="error">
                                <h3>Error</h3>
                                <p>${{error.message}}</p>
                            </div>`;
                        }}
                    }};
                    
                    reader.readAsArrayBuffer(audioFile);
                }});
            }});
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Test Audio Upload</h1>
            
            <div class="current">
                <h3>Current Settings</h3>
                <p><strong>User ID:</strong> {user_id}</p>
                <p><strong>Current Omi UID:</strong> {current_uid or 'Not set'}</p>
                <p class="note">If your Omi UID is not set, please <a href="/set_omi_uid">set it here</a> first.</p>
            </div>
            
            <form id="uploadForm">
                <div class="form-group">
                    <label for="uid">Omi UID:</label>
                    <input type="text" id="uid" name="uid" value="{current_uid or ''}" required>
                    <p class="note">This should match the UID set in your user profile.</p>
                </div>
                
                <div class="form-group">
                    <label for="sampleRate">Sample Rate (Hz):</label>
                    <input type="number" id="sampleRate" name="sampleRate" value="16000" required>
                    <p class="note">Default is 16000 Hz for Omi devices.</p>
                </div>
                
                <div class="form-group">
                    <label for="audioFile">Audio File:</label>
                    <input type="file" id="audioFile" name="audioFile" accept="audio/*" required>
                    <p class="note">Select a WAV or raw audio file.</p>
                </div>
                
                <button type="submit">Upload Audio</button>
            </form>
            
            <div id="result" style="margin-top: 30px;"></div>
        </div>
    </body>
    </html>
    """

#TESTING#####################


@app.route('/fetch_webhook_data', methods=['GET'])
def fetch_webhook_data():
    """
    Fetch data from the webhook URL and process it to create a script.
    """
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        user_id = session['user']['id']
        
        # Get the user's Omi UID
        try:
            result = supabase.table('users').select('omi_uid').eq('id', user_id).execute()
            omi_uid = result.data[0]['omi_uid'] if result.data and 'omi_uid' in result.data[0] else None
            
            if not omi_uid:
                return jsonify({'error': 'Omi UID not set. Please set your Omi UID first.'}), 400
                
        except Exception as e:
            print(f"Error getting omi_uid: {e}")
            return jsonify({'error': 'Failed to retrieve Omi UID'}), 500
        
        # Fetch data from webhook
        webhook_url = f"https://webhook.site/6e59844e-e7d0-4061-9b36-e4259422831a?uid={omi_uid}"
        
        response = requests.get(webhook_url)
        if response.status_code != 200:
            return jsonify({'error': f'Failed to fetch data from webhook: {response.status_code}'}), 500
        
        # Process the webhook data
        try:
            webhook_data = response.json()
            print(f"Received webhook data: {webhook_data}")
            
            # Extract text segments
            segments = webhook_data.get('segments', [])
            if not segments:
                return jsonify({'error': 'No text segments found in webhook data'}), 404
            
            # Construct a script from the segments
            script = ""
            for segment in segments:
                speaker = segment.get('speaker', 'Unknown')
                text = segment.get('text', '')
                
                if text:
                    script += f"{speaker}: {text}\n"
            
            # Store the script in the database
            try:
                script_id = str(uuid.uuid4())
                
                script_data = {
                    'id': script_id,
                    'user_id': user_id,
                    'content': script,
                    'created_at': datetime.now().isoformat(),
                    'source': 'webhook'
                }
                
                # Get authenticated client
                supabase_client = get_authenticated_supabase(user_id)
                
                # Insert the script
                result = supabase_client.table('scripts').insert(script_data).execute()
                
                return jsonify({
                    'success': True,
                    'script': script,
                    'script_id': script_id
                })
                
            except Exception as db_error:
                print(f"Error storing script: {db_error}")
                import traceback
                traceback.print_exc()
                
                # Return the script even if storing fails
                return jsonify({
                    'success': True,
                    'script': script,
                    'warning': 'Script was generated but could not be stored in the database'
                })
                
        except Exception as proc_error:
            print(f"Error processing webhook data: {proc_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Failed to process webhook data: {str(proc_error)}'}), 500
            
    except Exception as e:
        print(f"Error in fetch_webhook_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/webhook_receiver', methods=['POST'])
def webhook_receiver():
    """
    Endpoint to directly receive webhook data and store it for the user.
    
    Expected webhook format:
    {
      "session_id": "user_uid",
      "segments": [
        {
          "text": "Text content",
          "speaker": "SPEAKER_X",
          "speaker_id": X,
          "is_user": true/false,
          "person_id": null,
          "start": 0,
          "end": 0.5
        }
      ]
    }
    """
    try:
        data = request.json
        print(f"Received webhook data: {data}")
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
            
        # Extract the UID from the session_id field
        omi_uid = data.get('session_id')
        if not omi_uid:
            return jsonify({'error': 'No session_id provided in webhook data'}), 400
            
        # Find the user with this OMI UID
        try:
            result = supabase.table('users').select('id').eq('omi_uid', omi_uid).execute()
            
            if not result.data:
                print(f"No user found with omi_uid: {omi_uid}")
                return jsonify({'error': 'No user found with the provided session_id'}), 404
                
            user_id = result.data[0]['id']
            print(f"Found user {user_id} for omi_uid {omi_uid}")
            
        except Exception as e:
            print(f"Error finding user: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'Error processing user information'}), 500
            
        # Extract text segments
        segments = data.get('segments', [])
        if not segments:
            return jsonify({'error': 'No text segments found in webhook data'}), 400
            
        # Construct a script from the segments
        script = ""
        for segment in segments:
            speaker = segment.get('speaker', 'Unknown')
            text = segment.get('text', '')
            
            if text:
                script += f"{speaker}: {text}\n"
                
        print(f"Generated script: {script}")
        
        # Store the script in the database
        try:
            script_id = str(uuid.uuid4())
            
            script_data = {
                'id': script_id,
                'user_id': user_id,
                'content': script,
                'created_at': datetime.now().isoformat(),
                'source': 'webhook'
            }
            
            # Use service role client for storing
            result = supabase.table('scripts').insert(script_data).execute()
            
            print(f"Stored script with ID: {script_id}")
            return jsonify({
                'success': True,
                'message': 'Webhook data processed successfully',
                'script_id': script_id
            })
            
        except Exception as db_error:
            print(f"Error storing script: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Failed to store script: {str(db_error)}'}), 500
            
    except Exception as e:
        print(f"Error in webhook_receiver: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/scripts')
def view_scripts():
    """
    View all scripts for the current user
    """
    if 'user' not in session:
        return redirect('/login')
    
    user_id = session['user']['id']
    
    try:
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get all scripts for the user
        scripts_result = supabase_client.table('scripts').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        
        scripts = scripts_result.data if scripts_result.data else []
        
        return render_template('scripts.html', user=session['user'], scripts=scripts)
        
    except Exception as e:
        print(f"Error fetching scripts: {e}")
        import traceback
        traceback.print_exc()
        
        # Return an empty list if there's an error
        return render_template('scripts.html', user=session['user'], scripts=[], error=str(e))
    

@app.route('/get_script/<script_id>', methods=['GET'])
def get_script(script_id):
    """
    Retrieve a specific script by ID
    """
    try:
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        user_id = session['user']['id']
        
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get the specified script
        script_result = supabase_client.table('scripts').select('*').eq('id', script_id).eq('user_id', user_id).execute()
        
        if not script_result.data:
            return jsonify({'error': 'Script not found or does not belong to user'}), 404
            
        script = script_result.data[0]
        
        return jsonify({
            'success': True,
            'script': script
        })
        
    except Exception as e:
        print(f"Error fetching script: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/create_manga', methods=['GET'])
def create_manga_page():
    """
    Page to create a manga from a script
    """
    if 'user' not in session:
        return redirect('/login')
    
    script_id = request.args.get('script_id')
    
    if not script_id:
        return redirect('/scripts')
    
    user_id = session['user']['id']
    
    try:
        # Get authenticated client
        supabase_client = get_authenticated_supabase(user_id)
        
        # Get the specified script
        script_result = supabase_client.table('scripts').select('*').eq('id', script_id).eq('user_id', user_id).execute()
        
        if not script_result.data:
            return "Script not found or does not belong to user", 404
            
        script = script_result.data[0]
        
        return render_template('create_manga.html', user=session['user'], script=script)
        
    except Exception as e:
        print(f"Error fetching script: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)