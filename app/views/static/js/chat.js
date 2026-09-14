const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");

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

    if (!message) {
        return;
    }

    addMessage(message, "user");

    messageInput.value = "";

    setLoading(true);

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                customer_id: CUSTOMER_ID
            })
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