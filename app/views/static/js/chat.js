const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const mediaInput = document.getElementById("media-input");
const recordBtn = document.getElementById("record-btn");
const recordBtnText = document.getElementById("record-btn-text");
const mediaPreviewTray = document.getElementById("media-preview-tray");
const previewFilename = document.getElementById("preview-filename");
const previewAudio = document.getElementById("preview-audio");
const clearMediaBtn = document.getElementById("clear-media-btn");

const conversationId = crypto.randomUUID();
const CUSTOMER_ID = 1;

let mediaRecorder = null;
let audioChunks = [];
let recordedAudioBlob = null;
let recordInterval = null;
let recordSeconds = 0;


function addMessage(message, role, media = null) {
    const messageElement = document.createElement("div");

    messageElement.classList.add("message", role);

    const contentElement = document.createElement("div");

    contentElement.classList.add("message-content");

    if (media) {
        const mediaContainer = document.createElement("div");
        mediaContainer.classList.add("message-media");

        if (media.type === "image") {
            const img = document.createElement("img");
            img.src = media.url;
            img.alt = media.name || "Uploaded image";
            img.classList.add("media-preview-image");
            mediaContainer.appendChild(img);
        } else if (media.type === "audio") {
            const audio = document.createElement("audio");
            audio.src = media.url;
            audio.controls = true;
            audio.classList.add("media-preview-audio");
            mediaContainer.appendChild(audio);
        }

        const link = document.createElement("a");
        link.href = media.downloadUrl || media.url;
        link.target = "_blank";
        link.classList.add("media-download-link");
        link.textContent = `Original ${media.type || "file"}: ${media.name || "download"}`;
        mediaContainer.appendChild(link);

        contentElement.appendChild(mediaContainer);
    }

    if (message) {
        const textElement = document.createElement("div");
        textElement.textContent = message;
        contentElement.appendChild(textElement);
    }

    messageElement.appendChild(contentElement);

    chatMessages.appendChild(messageElement);

    chatMessages.scrollTop = chatMessages.scrollHeight;
}


function setLoading(isLoading) {
    sendButton.disabled = isLoading;

    if (isLoading) {
        sendButton.textContent = "Sending...";
    } else {
        sendButton.textContent = "Send";
    }
}


function clearSelectedMedia() {
    mediaInput.value = "";
    recordedAudioBlob = null;
    if (previewAudio.src) {
        URL.revokeObjectURL(previewAudio.src);
        previewAudio.src = "";
    }
    previewAudio.style.display = "none";
    previewFilename.textContent = "";
    mediaPreviewTray.style.display = "none";
}

if (clearMediaBtn) {
    clearMediaBtn.addEventListener("click", clearSelectedMedia);
}


// When user chooses an image or audio file from disk
mediaInput.addEventListener("change", () => {
    const file = mediaInput.files[0];
    if (!file) return;

    recordedAudioBlob = null;
    const isAud = file.type.startsWith("audio/") || /\.(mp3|wav|ogg|m4a|webm|flac)$/i.test(file.name);
    const isImg = file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(file.name);

    previewFilename.textContent = `${isAud ? "🎵 Audio" : isImg ? "🖼️ Image" : "📎 File"}: ${file.name}`;
    if (isAud) {
        previewAudio.src = URL.createObjectURL(file);
        previewAudio.style.display = "block";
    } else {
        previewAudio.style.display = "none";
    }
    mediaPreviewTray.style.display = "flex";
});


// Voice recording with live microphone
if (recordBtn) {
    recordBtn.addEventListener("click", async () => {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];

            const preferredMime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus") ? "audio/ogg;codecs=opus" : "audio/webm");

            mediaRecorder = new MediaRecorder(stream, { mimeType: preferredMime });

            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                clearInterval(recordInterval);
                recordBtn.classList.remove("recording");
                recordBtnText.textContent = "Record";

                recordedAudioBlob = new Blob(audioChunks, { type: "audio/webm" });
                stream.getTracks().forEach((track) => track.stop());

                mediaInput.value = "";
                const mins = Math.floor(recordSeconds / 60);
                const secs = String(recordSeconds % 60).padStart(2, "0");
                previewFilename.textContent = `🎙️ Voice Note (${mins}:${secs})`;
                previewAudio.src = URL.createObjectURL(recordedAudioBlob);
                previewAudio.style.display = "block";
                mediaPreviewTray.style.display = "flex";
            };

            mediaRecorder.start();
            recordSeconds = 0;
            recordBtn.classList.add("recording");
            recordBtnText.textContent = "⏹️ Stop (0:00)";

            recordInterval = setInterval(() => {
                recordSeconds++;
                const mins = Math.floor(recordSeconds / 60);
                const secs = String(recordSeconds % 60).padStart(2, "0");
                recordBtnText.textContent = `⏹️ Stop (${mins}:${secs})`;
            }, 1000);

        } catch (err) {
            alert("Microphone permission was denied or not supported by this browser: " + err.message);
        }
    });
}


chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();
    const file = mediaInput.files[0];
    const hasAudioRecord = Boolean(recordedAudioBlob);

    if (!message && !file && !hasAudioRecord) return;

    let clientMedia = null;
    let fileToSend = null;

    if (hasAudioRecord) {
        fileToSend = new File([recordedAudioBlob], "voice_note.webm", { type: "audio/webm" });
        clientMedia = {
            url: URL.createObjectURL(recordedAudioBlob),
            type: "audio",
            name: "voice_note.webm"
        };
    } else if (file) {
        fileToSend = file;
        const isImg = file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(file.name);
        clientMedia = {
            url: URL.createObjectURL(file),
            type: isImg ? "image" : "audio",
            name: file.name
        };
    }

    addMessage(message, "user", clientMedia);
    messageInput.value = "";
    clearSelectedMedia();
    setLoading(true);

    try {
        const formData = new FormData();
        formData.append("message", message);
        formData.append("customer_id", CUSTOMER_ID);
        formData.append("conversation_id", conversationId);
        if (fileToSend) formData.append("file", fileToSend);

        const response = await fetch("/api/chat", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        addMessage(data.response, "assistant");

    } catch (error) {
        addMessage(
            `Error: ${error.message}`,
            "assistant"
        );
    } finally {
        setLoading(false);
        messageInput.focus();
    }
});