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
    // Manga generation elements
    const generateMangaBtn = document.getElementById('generate-manga-btn');
    const dayScriptInput = document.getElementById('day-script');
    const mangaProcessingIndicator = document.getElementById('manga-processing-indicator');
    const mangaResult = document.getElementById('manga-result');
    const mangaPanels = document.getElementById('manga-panels');
    const viewFullMangaBtn = document.getElementById('view-full-manga');
    const saveSuccessDiv = document.getElementById('save-success');

    let stream = null;
    let imageCapture = null;
    let photoBlob = null;

    // Add a new button for generating images
    const generateImagesBtn = document.createElement('button');
    generateImagesBtn.id = 'generate-images-btn';
    generateImagesBtn.className = 'action-button';
    generateImagesBtn.style.display = 'none';
    generateImagesBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        Generate Images
    `;
    
    // Insert the button before view-full-manga button
    if (viewFullMangaBtn) {
        viewFullMangaBtn.parentNode.insertBefore(generateImagesBtn, viewFullMangaBtn);
    }

    // Create the Save Manga button
    function addSaveMangaButton() {
        console.log("Adding save manga button");
        
        // Create a save manga button if it doesn't already exist
        if (document.getElementById('save-manga-btn')) {
            return document.getElementById('save-manga-btn');
        }
        
        const saveMangaBtn = document.createElement('button');
        saveMangaBtn.id = 'save-manga-btn';
        saveMangaBtn.className = 'action-button';
        saveMangaBtn.style.display = 'none';
        saveMangaBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
                <polyline points="7 3 7 8 15 8"></polyline>
            </svg>
            Save Memory
        `;
        
        // Insert the Save Manga button before View Full Manga button
        if (viewFullMangaBtn) {
            viewFullMangaBtn.parentNode.insertBefore(saveMangaBtn, viewFullMangaBtn);
        } else if (mangaResult) {
            mangaResult.appendChild(saveMangaBtn);
        }
        
        // Add event listener to the save button
        saveMangaBtn.addEventListener('click', async function() {
            console.log("Save manga button clicked");
            
            // Get the manga panels data
            const mangaPanelsData = document.getElementById('manga-panels').dataset.mangaPanels;
            
            if (!mangaPanelsData) {
                alert('Please generate manga images first before saving.');
                return;
            }
            
            // Show processing indicator
            mangaProcessingIndicator.style.display = 'block';
            mangaProcessingIndicator.querySelector('p').textContent = 'Saving your memory...';
            saveMangaBtn.disabled = true;
            
            try {
                // Get manga panels data
                const mangaPanelsEl = document.getElementById('manga-panels');
                
                // First try to get from mangaPanels
                let data = null;
                if (mangaPanelsEl.dataset.mangaPanels) {
                    try {
                        data = JSON.parse(mangaPanelsEl.dataset.mangaPanels);
                        console.log("Using manga_panels data from dataset:", data.length, "panels");
                    } catch (e) {
                        console.error("Error parsing manga panels data:", e);
                    }
                }
                
                if (!data) {
                    alert('No manga data found. Please generate images first.');
                    mangaProcessingIndicator.style.display = 'none';
                    return;
                }
                
                // Send the request with the correct key 'manga_panels'
                const response = await fetch('/save_manga', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        manga_panels: data
                    })
                });
                
                const result = await response.json();
                console.log("Save result:", result);
                
                // Hide processing indicator
                mangaProcessingIndicator.style.display = 'none';
                
                if (result.error) {
                    alert('Error: ' + result.error);
                    return;
                }
                
                // Show success message
                alert(`Your memory has been saved successfully! ${result.panel_count} panels were saved.`);
                
                // Show the success div if it exists
                const saveSuccess = document.getElementById('save-success');
                if (saveSuccess) {
                    saveSuccess.style.display = 'block';
                }
                
                // Hide the save button
                saveMangaBtn.style.display = 'none';
                
            } catch (error) {
                console.error('Error saving manga:', error);
                mangaProcessingIndicator.style.display = 'none';
                alert('Error saving manga. Please try again.');
            }
        });
        
        return saveMangaBtn;
    }
    
    // Initialize or retrieve the save manga button
    const saveMangaBtn = addSaveMangaButton();

    // Function to refresh signed URLs for images
    async function refreshSignedUrls() {
        // Find all images with URLs that contain "sign" (indicating a signed URL)
        const images = document.querySelectorAll('img[src*="sign"]');
        
        for (const img of images) {
            const currentSrc = img.src;
            // Extract the path from the URL (everything after the bucket name)
            const pathMatch = currentSrc.match(/character-images\/(.+?)(\?|$)/);
            
            if (pathMatch && pathMatch[1]) {
                const path = pathMatch[1];
                
                try {
                    const response = await fetch('/get-signed-image-url', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ path })
                    });
                    
                    const result = await response.json();
                    
                    if (result.url) {
                        img.src = result.url;
                    }
                } catch (error) {
                    console.error('Error refreshing image URL:', error);
                }
            }
        }
    }

    // Refresh URLs on page load
    refreshSignedUrls();
    
    // Refresh URLs every 10 minutes
    setInterval(refreshSignedUrls, 600000);

    // Check for existing character
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

    // Check if elements exist (they might not be loaded yet in some views)
    if (generateMangaBtn) {
        console.log("Found generate manga button");
        
        // Generate manga button click handler
        generateMangaBtn.addEventListener('click', async function() {
            console.log("Generate manga button clicked");
            const script = dayScriptInput.value.trim();
            
            if (!script) {
                alert('Please enter a description of your day to generate a manga.');
                return;
            }
            
            // Show processing indicator
            mangaProcessingIndicator.style.display = 'block';
            mangaResult.style.display = 'none';
            generateImagesBtn.style.display = 'none';
            
            // Hide any previous success messages
            if (saveSuccessDiv) {
                saveSuccessDiv.style.display = 'none';
            }
            
            try {
                // Send script to backend
                const response = await fetch('/generate_manga', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        script: script,
                        generate_images: false  // Don't generate images yet
                    })
                });
                
                const result = await response.json();
                
                // Hide processing indicator
                mangaProcessingIndicator.style.display = 'none';
                
                if (result.error) {
                    alert('Error: ' + result.error);
                    return;
                }
                
                // Display manga panels preview
                displayMangaPanels(result.panels, result.dialogues);
                
                // Show result and generate images button
                mangaResult.style.display = 'block';
                generateImagesBtn.style.display = 'inline-block';
                
            } catch (error) {
                console.error('Error generating manga:', error);
                mangaProcessingIndicator.style.display = 'none';
                alert('Error generating manga. Please try again.');
            }
        });
    } else {
        console.log("Generate manga button not found");
    }
    
    // Generate images button click handler
    if (generateImagesBtn) {
        generateImagesBtn.addEventListener('click', async function() {
            // Show processing indicator
            mangaProcessingIndicator.style.display = 'block';
            mangaProcessingIndicator.querySelector('p').textContent = 'Generating memoir images...';
            generateImagesBtn.style.display = 'none';
            
            // Hide any previous success messages
            if (saveSuccessDiv) {
                saveSuccessDiv.style.display = 'none';
            }
            
            try {
                const script = dayScriptInput.value.trim();
                
                // Send request to generate images
                const response = await fetch('/generate_manga', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        script: script,
                        generate_images: true  // Generate images this time
                    })
                });
                
                const result = await response.json();
                
                // Hide processing indicator
                mangaProcessingIndicator.style.display = 'none';
                
                if (result.error) {
                    alert('Error: ' + result.error);
                    return;
                }
                
                // Display manga panels with actual images
                displayMangaImages(result.manga_panels);
                
                // Show result
                mangaResult.style.display = 'block';
                
                // Show View Full Manga button
                viewFullMangaBtn.style.display = 'inline-block';
                
                // Show Save Manga button
                saveMangaBtn.style.display = 'inline-block';
                
            } catch (error) {
                console.error('Error generating memoir images:', error);
                mangaProcessingIndicator.style.display = 'none';
                alert('Error generating memoir images. Please try again.');
                // Show the generate images button again so user can retry
                generateImagesBtn.style.display = 'inline-block';
            }
        });
    }
    
    // Function to display manga panels (without images)
    function displayMangaPanels(panels, dialogues) {
        // Clear previous panels
        mangaPanels.innerHTML = '';
        
        // For now, show placeholders for the first 4 panels (first page)
        // In a real implementation, you would display actual images once generated
        for (let i = 0; i < Math.min(4, panels.length); i++) {
            const panel = panels[i];
            const dialogue = dialogues[i];
            
            const panelElement = document.createElement('div');
            panelElement.className = 'manga-panel';
            
            panelElement.innerHTML = `
                <div class="panel-image-container">
                    <div class="placeholder-panel">Panel ${i+1}</div>
                </div>
                <div class="panel-dialogue">${dialogue}</div>
            `;
            
            mangaPanels.appendChild(panelElement);
        }
        
        // Store all panels data in data attributes for later use
        mangaPanels.dataset.panels = JSON.stringify(panels);
        mangaPanels.dataset.dialogues = JSON.stringify(dialogues);
    }
    
    // Function to display manga images
    function displayMangaImages(mangaPanels) {
        console.log("Displaying manga images:", mangaPanels ? mangaPanels.length : 0, "panels");
        
        // Clear previous panels
        document.getElementById('manga-panels').innerHTML = '';
        
        // Display first 4 panels (first page)
        for (let i = 0; i < Math.min(4, mangaPanels.length); i++) {
            const panel = mangaPanels[i];
            
            const panelElement = document.createElement('div');
            panelElement.className = 'manga-panel';
            
            // Check if image was generated successfully
            if (panel.image_url) {
                panelElement.innerHTML = `
                    <div class="panel-image-container">
                        <img src="${panel.image_url}" alt="Panel ${panel.panel_number + 1}" class="panel-image">
                    </div>
                    <div class="panel-dialogue">${panel.dialogue}</div>
                `;
            } else {
                // Fallback if image generation failed
                panelElement.innerHTML = `
                    <div class="panel-image-container">
                        <div class="placeholder-panel">Panel ${panel.panel_number + 1} (Image failed)</div>
                    </div>
                    <div class="panel-dialogue">${panel.dialogue}</div>
                `;
            }
            
            document.getElementById('manga-panels').appendChild(panelElement);
        }
        
        // Store the manga panels data for later use
        const mangaPanelsJSON = JSON.stringify(mangaPanels);
        console.log("Storing manga panels data:", mangaPanelsJSON ? mangaPanelsJSON.substring(0, 100) + "..." : "empty");
        document.getElementById('manga-panels').dataset.mangaPanels = mangaPanelsJSON;
        
        // Show buttons after manga is generated
        if (viewFullMangaBtn) {
            viewFullMangaBtn.style.display = 'inline-block';
        }
        
        if (saveMangaBtn) {
            saveMangaBtn.style.display = 'inline-block';
        }
    }
    
    // View full manga button click handler
    if (viewFullMangaBtn) {
        viewFullMangaBtn.addEventListener('click', function() {
            // Check if we have manga panels with images
            const mangaPanelsData = document.getElementById('manga-panels').dataset.mangaPanels;
            
            if (mangaPanelsData) {
                const mangaPanels = JSON.parse(mangaPanelsData);
                showFullManga(mangaPanels);
            } else {
                // If we only have panel data without images
                const panels = JSON.parse(document.getElementById('manga-panels').dataset.panels || '[]');
                const dialogues = JSON.parse(document.getElementById('manga-panels').dataset.dialogues || '[]');
                alert(`Full manga would display all ${panels.length} panels. This feature is coming soon! You need to generate images first.`);
            }
        });
    }
    
    // Function to show the full manga in a modal
    function showFullManga(mangaPanels) {
        // Create a modal to display all panels
        const modal = document.createElement('div');
        modal.className = 'manga-modal';
        modal.innerHTML = `
            <div class="manga-modal-content">
                <span class="manga-close-button">&times;</span>
                <h2>Your Memory</h2>
                <div class="manga-pages"></div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Create pages (4 panels per page)
        const pagesContainer = modal.querySelector('.manga-pages');
        
        for (let i = 0; i < mangaPanels.length; i += 4) {
            const pageDiv = document.createElement('div');
            pageDiv.className = 'manga-page';
            
            // Add up to 4 panels for this page
            for (let j = i; j < Math.min(i + 4, mangaPanels.length); j++) {
                const panel = mangaPanels[j];
                
                const panelDiv = document.createElement('div');
                panelDiv.className = 'manga-panel-full';
                
                if (panel.image_url) {
                    panelDiv.innerHTML = `
                        <div class="panel-image-container-full">
                            <img src="${panel.image_url}" alt="Panel ${panel.panel_number + 1}" class="panel-image">
                        </div>
                        <div class="panel-dialogue-full">${panel.dialogue}</div>
                    `;
                } else {
                    panelDiv.innerHTML = `
                        <div class="panel-image-container-full">
                            <div class="placeholder-panel">Panel ${panel.panel_number + 1} (Image failed)</div>
                        </div>
                        <div class="panel-dialogue-full">${panel.dialogue}</div>
                    `;
                }
                
                pageDiv.appendChild(panelDiv);
            }
            
            pagesContainer.appendChild(pageDiv);
        }
        
        // Show the modal
        modal.style.display = 'flex';
        
        // Close button functionality
        modal.querySelector('.manga-close-button').addEventListener('click', function() {
            document.body.removeChild(modal);
        });
        
        // Click outside to close
        window.addEventListener('click', function(event) {
            if (event.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }
    
    // Submit button event listener for character creation
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