const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

// Add message to chat UI
function addMessage(sender, text) {
    const msg = document.createElement("div");
    msg.classList.add("message", sender);
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Show typing indicator
function showTyping() {
    const typing = document.createElement("div");
    typing.id = "typing";
    typing.classList.add("message", "ai");
    typing.textContent = "Typing...";
    chatBox.appendChild(typing);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Remove typing indicator
function removeTyping() {
    const typing = document.getElementById("typing");
    if (typing) typing.remove();
}

// Send message to backend
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMessage("user", text);
    userInput.value = "";

    showTyping();

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        removeTyping();
        addMessage("ai", data.reply);
    } catch (error) {
        removeTyping();
        addMessage("ai", "Error contacting server.");
    }
}

// Send button click
sendBtn.addEventListener("click", sendMessage);

// Enter key sends message
userInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
        sendMessage();
    }
});
