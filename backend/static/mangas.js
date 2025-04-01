// static/mangas.js
document.addEventListener('DOMContentLoaded', function() {
    // Function to refresh signed URLs for images
    async function refreshSignedUrls() {
        // Find all images with URLs that contain "sign" (indicating a signed URL)
        const images = document.querySelectorAll('img[src*="sign"]');
        
        for (const img of images) {
            const currentSrc = img.src;
            // Extract the path from the URL (everything after the bucket name)
            const pathMatch = currentSrc.match(/manga-panels\/(.+?)(\?|$)/);
            
            if (pathMatch && pathMatch[1]) {
                const path = pathMatch[1];
                
                try {
                    const response = await fetch('/get-signed-image-url', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ 
                            path,
                            bucket: 'manga-panels'  // Specify which bucket to use
                        })
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

    // Add click handlers for any interactive elements
    const mangaCards = document.querySelectorAll('.manga-card');
    
    mangaCards.forEach(card => {
        card.addEventListener('click', function(event) {
            // If the click wasn't on a button or link
            if (!event.target.closest('a, button')) {
                // Get the manga ID from the View Manga button
                const viewButton = this.querySelector('a[href*="/view_manga/"]');
                if (viewButton) {
                    window.location.href = viewButton.href;
                }
            }
        });
    });
});