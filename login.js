document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const screenContent = document.getElementById('screen-content');
    const pageTurnSound = document.getElementById('pageTurnSound');
    const deviceSound = document.getElementById('deviceSound');
    const cameraSound = document.getElementById('cameraSound');
    const recordingIndicator = document.querySelector('.recording-indicator');
    
    // Current screen state
    let currentScreen = 'welcome';
    
    // Initialize the device
    function initDevice() {
        deviceSound.play();
        showWelcomeScreen();
        
        // Simulate Omi device boot sequence
        gsap.from('.omi-device', {
            scale: 0.9,
            opacity: 0,
            duration: 1,
            ease: "power3.out"
        });
        
        gsap.from('.device-sensors .sensor', {
            scale: 0,
            stagger: 0.2,
            duration: 0.5,
            delay: 0.5
        });
    }
    
    // Show welcome screen
    function showWelcomeScreen() {
        currentScreen = 'welcome';
        screenContent.innerHTML = `
            <div class="welcome-screen screen-transition">
                <h1>Welcome to Your Personal Manga</h1>
                <p>OMI transforms your daily life into manga stories using advanced speech recognition and AI technology.</p>
                <button class="btn-signin" id="google-signin-btn">
                    <i class="fab fa-google"></i> Continue with Google
                </button>
            </div>
        `;
        
        // Add event listener to the button
        document.getElementById('google-signin-btn').addEventListener('click', function() {
            pageTurnSound.play();
            showCharacterSetup();
        });
        
        // Animate elements
        gsap.from('.welcome-screen h1, .welcome-screen p', {
            y: 20,
            opacity: 0,
            stagger: 0.2,
            duration: 0.8,
            ease: "power2.out"
        });
        
        gsap.from('.btn-signin', {
            y: 30,
            opacity: 0,
            duration: 0.8,
            delay: 0.5,
            ease: "back.out(1.7)"
        });
    }
    
    // Show character setup screen
    function showCharacterSetup() {
        currentScreen = 'character-setup';
        screenContent.innerHTML = `
            <div class="character-setup screen-transition">
                <h2>Hey User, Let's Setup Your Character</h2>
                <p>Upload a photo or take one with your camera to create your manga avatar.</p>
                
                <div class="character-preview" id="character-preview">
                    <i class="fas fa-user" style="font-size: 3rem; color: rgba(76, 201, 240, 0.3);"></i>
                    <img id="preview-image" src="" alt="Your Character">
                </div>
                
                <div class="upload-options">
                    <button class="upload-btn" id="upload-photo">
                        <i class="fas fa-upload"></i> Upload Photo
                    </button>
                    <button class="upload-btn" id="take-photo">
                        <i class="fas fa-camera"></i> Take Photo
                    </button>
                </div>
            </div>
            
            <div class="camera-interface" id="camera-interface">
                <div class="camera-view" id="camera-view"></div>
                <div class="camera-controls">
                    <button class="camera-btn" id="close-camera">
                        <i class="fas fa-times"></i>
                    </button>
                    <button class="camera-btn capture-btn" id="capture-btn">
                        <i class="fas fa-camera"></i>
                    </button>
                    <button class="camera-btn" id="flip-camera">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>
            </div>
        `;
        
        // Get elements
        const characterPreview = document.getElementById('character-preview');
        const previewImage = document.getElementById('preview-image');
        const uploadPhotoBtn = document.getElementById('upload-photo');
        const takePhotoBtn = document.getElementById('take-photo');
        const cameraInterface = document.getElementById('camera-interface');
        const closeCameraBtn = document.getElementById('close-camera');
        const captureBtn = document.getElementById('capture-btn');
        const flipCameraBtn = document.getElementById('flip-camera');
        
        // Upload photo handler
        uploadPhotoBtn.addEventListener('click', function() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            
            input.onchange = function(e) {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        previewImage.src = event.target.result;
                        document.querySelector('.character-preview i').style.display = 'none';
                        previewImage.style.display = 'block';
                        
                        // Animate the preview
                        gsap.from(previewImage, {
                            scale: 0.8,
                            opacity: 0,
                            duration: 0.5,
                            ease: "back.out(1.7)"
                        });
                    };
                    reader.readAsDataURL(file);
                }
            };
            
            input.click();
        });
        
        // Take photo handler
        takePhotoBtn.addEventListener('click', function() {
            cameraInterface.style.display = 'flex';
            gsap.from(cameraInterface, {
                opacity: 0,
                duration: 0.5
            });
            
            // In a real app, we'd initialize the camera here
            // For demo, we'll just show a placeholder
            const cameraView = document.getElementById('camera-view');
            cameraView.innerHTML = `
                <div style="width:100%;height:100%;display:flex;justify-content:center;align-items:center;background-color:#111;">
                    <i class="fas fa-user" style="font-size:5rem;color:rgba(255,255,255,0.1);"></i>
                </div>
            `;
            
            // Simulate camera active
            recordingIndicator.style.opacity = '1';
            recordingIndicator.classList.add('recording-active');
        });
        
        // Close camera handler
        closeCameraBtn.addEventListener('click', function() {
            gsap.to(cameraInterface, {
                opacity: 0,
                duration: 0.3,
                onComplete: function() {
                    cameraInterface.style.display = 'none';
                    recordingIndicator.style.opacity = '0';
                    recordingIndicator.classList.remove('recording-active');
                }
            });
        });
        
        // Capture photo handler
        captureBtn.addEventListener('click', function() {
            cameraSound.play();
            
            // Flash effect
            const flash = document.createElement('div');
            flash.style.position = 'absolute';
            flash.style.top = '0';
            flash.style.left = '0';
            flash.style.width = '100%';
            flash.style.height = '100%';
            flash.style.backgroundColor = 'white';
            flash.style.opacity = '0';
            cameraView.appendChild(flash);
            
            gsap.to(flash, {
                opacity: 0.8,
                duration: 0.1,
                yoyo: true,
                repeat: 1,
                onComplete: function() {
                    cameraView.removeChild(flash);
                    
                    // In a real app, we'd capture the actual image here
                    // For demo, we'll use a placeholder
                    const capturedImage = 'https://via.placeholder.com/150';
                    
                    previewImage.src = capturedImage;
                    document.querySelector('.character-preview i').style.display = 'none';
                    previewImage.style.display = 'block';
                    
                    gsap.from(previewImage, {
                        scale: 0.8,
                        opacity: 0,
                        duration: 0.5,
                        ease: "back.out(1.7)"
                    });
                    
                    // Close camera
                    gsap.to(cameraInterface, {
                        opacity: 0,
                        duration: 0.3,
                        onComplete: function() {
                            cameraInterface.style.display = 'none';
                            recordingIndicator.style.opacity = '0';
                            recordingIndicator.classList.remove('recording-active');
                        }
                    });
                }
            });
        });
        
        // Animate elements
        gsap.from('.character-setup h2, .character-setup p', {
            y: 20,
            opacity: 0,
            stagger: 0.2,
            duration: 0.8,
            ease: "power2.out"
        });
        
        gsap.from('.character-preview', {
            scale: 0.8,
            opacity: 0,
            duration: 0.8,
            delay: 0.3,
            ease: "back.out(1.7)"
        });
        
        gsap.from('.upload-btn', {
            y: 20,
            opacity: 0,
            stagger: 0.1,
            duration: 0.6,
            delay: 0.5,
            ease: "power2.out"
        });
    }
    
    // Initialize the device
    initDevice();
    
    // Simulate Omi processing speech
    function simulateSpeechProcessing() {
        if (currentScreen === 'character-setup') {
            // Random manga-style speech bubble
            const phrases = [
                "Analyzing your features...",
                "Creating manga style...",
                "Almost done...",
                "Looking good!",
                "Perfect for manga!"
            ];
            
            const bubble = document.createElement('div');
            bubble.className = 'speech-bubble';
            bubble.textContent = phrases[Math.floor(Math.random() * phrases.length)];
            screenContent.appendChild(bubble);
            
            gsap.from(bubble, {
                y: 20,
                opacity: 0,
                duration: 0.5,
                onComplete: function() {
                    setTimeout(function() {
                        gsap.to(bubble, {
                            y: -20,
                            opacity: 0,
                            duration: 0.5,
                            onComplete: function() {
                                screenContent.removeChild(bubble);
                            }
                        });
                    }, 2000);
                }
            });
        }
    }
    
    // Random speech processing simulation
    setInterval(simulateSpeechProcessing, 5000);
    
    // Add some subtle device movements
    gsap.to('.omi-device', {
        y: -5,
        duration: 5,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut"
    });
});