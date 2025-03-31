// static/dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const cameraButton = document.getElementById('camera-button');
    const retryButton = document.getElementById('retry-button');
    const submitButton = document.getElementById('submit-button');
    const fileUpload = document.getElementById('file-upload');
    const capturedImage = document.getElementById('captured-image');
    const capturedImageContainer = document.getElementById('captured-image-container');
    const cameraPreview = document.getElementById('camera-preview');
    const processingIndicator = document.getElementById('processing-indicator');
    const characterResult = document.getElementById('character-result');
    const characterDescription = document.getElementById('character-description');
    // Check if user already has a character
    const existingCharacter = document.querySelector('.existing-character');
    const characterCreation = document.querySelector('.character-creation');

    let stream = null;
    let imageCapture = null;
    let photoBlob = null;
    // Add this to the beginning of dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    
    
    if (existingCharacter) {
        // Initially hide the character creation elements
        cameraPreview.style.display = 'none';
        capturedImageContainer.style.display = 'none';
        document.querySelector('.upload-alternative').style.display = 'none';
        document.querySelector('.camera-controls').style.display = 'none';
        
        // Add event listener to "Create New Character" button
        document.getElementById('create-new-character').addEventListener('click', function() {
            existingCharacter.style.display = 'none';
            cameraPreview.style.display = 'block';
            document.querySelector('.upload-alternative').style.display = 'block';
            document.querySelector('.camera-controls').style.display = 'block';
            initCamera(); // Make sure camera initializes
        });
    } else {
        // Start camera for new users
        initCamera();
    }
});
    // Initialize camera
    async function initCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'user',
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                } 
            });
            video.srcObject = stream;
            
            // Create ImageCapture instance
            const track = stream.getVideoTracks()[0];
            imageCapture = new ImageCapture(track);
            
            cameraButton.disabled = false;
        } catch (err) {
            console.error('Error accessing camera:', err);
            // Show message if camera access is denied
            cameraPreview.innerHTML = `
                <div class="camera-error">
                    <p>Camera access denied or not available.</p>
                    <p>Please upload an image instead.</p>
                </div>
            `;
        }
    }
    
    // Start camera when page loads
    initCamera();
    
    // Take photo
    cameraButton.addEventListener('click', async () => {
        if (imageCapture) {
            try {
                const photoBlob = await imageCapture.takePhoto();
                displayCapturedImage(photoBlob);
            } catch (err) {
                // Fallback to canvas capture if takePhoto() is not supported
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                canvas.toBlob(blob => {
                    displayCapturedImage(blob);
                });
            }
        }
    });
    
    // Display captured image
    function displayCapturedImage(blob) {
        photoBlob = blob;
        capturedImage.src = URL.createObjectURL(blob);
        cameraPreview.style.display = 'none';
        capturedImageContainer.style.display = 'block';
        cameraButton.style.display = 'none';
        retryButton.style.display = 'inline';
        submitButton.style.display = 'inline';
    }
    
    // Retry photo capture
    retryButton.addEventListener('click', () => {
        cameraPreview.style.display = 'block';
        capturedImageContainer.style.display = 'none';
        cameraButton.style.display = 'inline';
        retryButton.style.display = 'none';
        submitButton.style.display = 'none';
        URL.revokeObjectURL(capturedImage.src);
    });
    
    // File upload
    fileUpload.addEventListener('change', (event) => {
        if (event.target.files && event.target.files[0]) {
            photoBlob = event.target.files[0];
            const reader = new FileReader();
            reader.onload = (e) => {
                capturedImage.src = e.target.result;
                cameraPreview.style.display = 'none';
                capturedImageContainer.style.display = 'block';
                cameraButton.style.display = 'none';
                retryButton.style.display = 'inline';
                submitButton.style.display = 'inline';
            };
            reader.readAsDataURL(photoBlob);
        }
    });
    
// Update the submitButton event listener in dashboard.js
submitButton.addEventListener('click', async () => {
    if (!photoBlob) return;
    
    // Show processing indicator
    capturedImageContainer.style.display = 'none';
    retryButton.style.display = 'none';
    submitButton.style.display = 'none';
    processingIndicator.style.display = 'block';
    processingIndicator.querySelector('p').textContent = 'Analyzing your image...';
    
    // Create form data
    const formData = new FormData();
    formData.append('image', photoBlob);
    
    try {
        // Step 1: Get description from image
        const response = await fetch('/process_image', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.error) {
            alert('Error: ' + result.error);
            processingIndicator.style.display = 'none';
            retryButton.style.display = 'inline';
            return;
        }
        
        // Display character description
        characterDescription.textContent = result.description;
        characterResult.style.display = 'block';
        
        // Step 2: Generate character image from description
        processingIndicator.querySelector('p').textContent = 'Creating your manga character...';
        
        const imageResponse = await fetch('/generate_character', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                description: result.description
            })
        });
        
        const imageResult = await imageResponse.json();
        
        // Hide processing indicator
        processingIndicator.style.display = 'none';
        
        if (imageResult.error) {
            alert('Error generating image: ' + imageResult.error);
            return;
        }
        
        // Display generated character image
        document.getElementById('character-image').src = imageResult.image_url;
        document.getElementById('character-image-result').style.display = 'block';
        
        // Step 3: Save main character to database
        try {
            const saveResponse = await fetch('/save_main_character', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    imageUrl: imageResult.image_url,
                    description: result.description
                })
            });
            
            const saveResult = await saveResponse.json();
            
            if (saveResult.error) {
                console.error('Error saving character:', saveResult.error);
                alert('Error saving your character: ' + saveResult.error);
            } else {
                console.log('Character saved successfully!');
                
                // Show success message
                const successMessage = document.createElement('div');
                successMessage.className = 'success-message';
                successMessage.innerHTML = `
                    <p>Your manga character has been created successfully!</p>
                    <button id="view-characters" class="action-button">View All Characters</button>
                `;
                document.getElementById('character-image-result').appendChild(successMessage);
                
                // Add event listener to view characters button
                document.getElementById('view-characters').addEventListener('click', () => {
                    window.location.href = '/people';
                });
            }
        } catch (error) {
            console.error('Error saving character:', error);
            alert('Error saving your character. Please try again.');
        }
    } catch (error) {
        console.error('Error processing image:', error);
        processingIndicator.style.display = 'none';
        alert('Error processing your image. Please try again.');
        retryButton.style.display = 'inline';
    }
});

});