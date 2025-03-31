// static/people.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const addPersonButton = document.getElementById('add-person-button');
    const modal = document.getElementById('add-person-modal');
    const closeButton = document.querySelector('.close-button');
    const cancelButton = document.querySelector('.cancel-button');
    const addPersonForm = document.getElementById('add-person-form');
    const personImage = document.getElementById('person-image');
    const imagePreview = document.getElementById('image-preview');
    const previewContainer = document.querySelector('.preview-container');
    const modalProcessing = document.getElementById('modal-processing');
    const deleteButtons = document.querySelectorAll('.delete-button');
    
    // Show modal when add button is clicked
    addPersonButton.addEventListener('click', function() {
        modal.style.display = 'flex';
    });
    
    // Close modal when close button is clicked
    closeButton.addEventListener('click', function() {
        modal.style.display = 'none';
        resetForm();
    });
    
    // Close modal when cancel button is clicked
    cancelButton.addEventListener('click', function() {
        modal.style.display = 'none';
        resetForm();
    });
    
    // Close modal when clicking outside of it
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
            resetForm();
        }
    });
    
    // Preview image when selected
    personImage.addEventListener('change', function(event) {
        if (event.target.files && event.target.files[0]) {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            
            reader.readAsDataURL(event.target.files[0]);
        }
    });
    
    // Handle form submission
    addPersonForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        
        const name = document.getElementById('person-name').value.trim();
        const image = personImage.files[0];
        
        if (!name || !image) {
            alert('Please provide both a name and an image.');
            return;
        }
        
        // Show processing indicator
        addPersonForm.style.display = 'none';
        modalProcessing.style.display = 'block';
        
        try {
            // Create form data
            const formData = new FormData();
            formData.append('name', name);
            formData.append('image', image);
            
            // Send to server
            const response = await fetch('/add_person', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Error: ' + result.error);
                addPersonForm.style.display = 'block';
                modalProcessing.style.display = 'none';
                return;
            }
            
            // Refresh the page to show the new character
            window.location.reload();
            
        } catch (error) {
            console.error('Error adding character:', error);
            alert('Error adding character. Please try again.');
            
            // Reset UI
            addPersonForm.style.display = 'block';
            modalProcessing.style.display = 'none';
        }
    });
    
    // Handle delete buttons
    deleteButtons.forEach(button => {
        button.addEventListener('click', async function() {
            const personId = this.dataset.id;
            
            if (confirm('Are you sure you want to delete this character?')) {
                try {
                    const response = await fetch('/delete_person', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ personId })
                    });
                    
                    const result = await response.json();
                    
                    if (result.error) {
                        alert('Error: ' + result.error);
                        return;
                    }
                    
                    // Refresh the page
                    window.location.reload();
                    
                } catch (error) {
                    console.error('Error deleting character:', error);
                    alert('Error deleting character. Please try again.');
                }
            }
        });
    });
    
    // Helper function to reset the form
    function resetForm() {
        addPersonForm.reset();
        previewContainer.style.display = 'none';
        addPersonForm.style.display = 'block';
        modalProcessing.style.display = 'none';
    }
    // Add this to your dashboard.js and people.js files

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
document.addEventListener('DOMContentLoaded', function() {
    refreshSignedUrls();
    
    // Refresh URLs every 10 minutes
    setInterval(refreshSignedUrls, 600000);
});

});