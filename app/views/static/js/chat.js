const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const mediaInput = document.getElementById("media-input");
const conversationId = crypto.randomUUID();

const CUSTOMER_ID = 1;


function addMessage(message, role) {
    const messageElement = document.createElement("div");

    messageElement.classList.add("message", role);

    const contentElement = document.createElement("div");

    contentElement.classList.add("message-content");

    contentElement.textContent = message;

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


chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();

    const file = mediaInput.files[0];
    if (!message && !file) return;

    addMessage(message || (file ? `Uploaded: ${file.name}` : ""), "user");
    messageInput.value = "";
    setLoading(true);

    try {
        const formData = new FormData();
        formData.append("message", message);
        formData.append("customer_id", CUSTOMER_ID);
        formData.append("conversation_id", conversationId);
        if (file) formData.append("file", file);

        const response = await fetch("/api/chat", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        addMessage(data.response, "assistant");
        mediaInput.value = "";

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