const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const chatContainer = document.getElementById('chat-container');
const typingIndicator = document.getElementById('typing-indicator');

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-bubble chat-bubble-user';

    const contentP = document.createElement('p');
    contentP.textContent = message;

    messageDiv.appendChild(contentP);
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

function addBotVideo(videoUrl) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-bubble chat-bubble-bot';

    const video = document.createElement('video');
    video.src = videoUrl;
    video.loop = false;
    video.controls = true;
    video.autoplay = true;
    video.playsinline = true;

    // ✅ Pause all other videos when this one plays
    video.addEventListener("play", () => {
        const allVideos = document.querySelectorAll("video");
        allVideos.forEach(v => {
            if (v !== video) v.pause();
        });
    });

    messageDiv.appendChild(video);
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

function addBotText(text) {
    const msg = document.createElement("div");
    msg.className = "chat-bubble chat-bubble-bot";
    msg.innerHTML = `<p>${text.replaceAll('/', "<br>")}</p>`;
    chatContainer.appendChild(msg);
    scrollToBottom();
}

function addBotImages(images) {
    images.forEach(src => {
        const msg = document.createElement("div");
        msg.className = "chat-bubble chat-bubble-bot";

        const img = document.createElement("img");
        img.src = src + "?v=" + Date.now();
        img.className = "rounded-lg max-w-full";

        msg.appendChild(img);
        chatContainer.appendChild(msg);
    });
    scrollToBottom();
}


messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message === '') return;

    addUserMessage(message);
    messageInput.value = '';

    typingIndicator.classList.remove('hidden');
    scrollToBottom();

    try {

        // ✅ ✅ ADDED BLOCK START
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 300000); // 300 sec (5 min)
        const response = await fetch('http://127.0.0.1:5000/get-response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
            signal: controller.signal
        });
        clearTimeout(timeout);
        // ✅ ✅ ADDED BLOCK END


        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();

        typingIndicator.classList.add('hidden');

        // ✅ Video
        const botVideoUrl = `${data.videoUrl}?v=${Date.now()}`;
        addBotVideo(botVideoUrl);

        // ✅ Text (disabled)
        // if (data.answer) addBotText(data.answer);

        // ✅ Images (disabled)
        // if (data.images?.length) addBotImages(data.images);

    } catch (error) {
        console.error('Error fetching video response:', error);
        typingIndicator.classList.add('hidden');
        const errorElement = document.createElement('div');
        errorElement.className = 'chat-bubble chat-bubble-bot';
        errorElement.innerHTML = `<p class="text-red-400">Error: Failed to connect to backend server.</p>`;
        chatContainer.appendChild(errorElement);
    } finally {
        if (!typingIndicator.classList.contains('hidden')) {
            typingIndicator.classList.add('hidden');
        }
        scrollToBottom();
    }
});