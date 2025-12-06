document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("sp-chat-widget")) return;

  const widget = document.createElement("div");
  widget.id = "sp-chat-widget";
  widget.innerHTML = `
    <button class="sp-chat-toggle" id="sp-chat-toggle">Chat</button>
    <div class="sp-chat-container" id="sp-chat-container">
      <div class="sp-chat-header"><h3>SmartPlanHub AI Assistant</h3></div>
      <div class="sp-chat-intro">Ask about deadlines, progress, or planning.</div>
      <div class="sp-chat-log" id="sp-chat-log"></div>
      <form class="sp-chat-form" id="sp-chat-form">
        <input type="text" id="sp-chat-input" name="inquiry" placeholder="Ask: What do I have due? How am I doing?" autocomplete="off" />
        <button type="submit">Send</button>
      </form>
    </div>
  `;
  document.body.appendChild(widget);

  const toggleBtn = document.getElementById("sp-chat-toggle");
  const chat = document.getElementById("sp-chat-container");
  const form = document.getElementById("sp-chat-form");
  const input = document.getElementById("sp-chat-input");
  const log = document.getElementById("sp-chat-log");

  toggleBtn.onclick = () => {
    chat.style.display = chat.style.display === "none" ? "block" : "none";
  };

  function addMessage(className, text) {
    const msg = document.createElement("div");
    msg.className = `sp-chat-message ${className}`;
    msg.innerHTML = text;
    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
  }

  function showTyping() {
    hideTyping();
    const t = document.createElement("div");
    t.id = "sp-chat-typing";
    t.className = "sp-chat-message sp-chat-bot";
    t.textContent = "Typing...";
    log.appendChild(t);
    log.scrollTop = log.scrollHeight;
  }

  function hideTyping() {
    const t = document.getElementById("sp-chat-typing");
    if (t) t.remove();
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage("sp-chat-user", text);
    showTyping();

    fetch("/handle_inquiry", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ inquiry: text })
    })
      .then((res) => res.json())
      .then((data) => {
        hideTyping();
        const reply = (data && data.response) ? data.response : "I'm still gathering your info—please try again shortly.";
        addMessage("sp-chat-bot", reply);
        if (data && data.error) {
          addMessage("sp-chat-bot", "Heads up: " + data.error);
        }
      })
      .catch(() => {
        hideTyping();
        addMessage("sp-chat-bot", "I can't reach the server right now—please try again soon.");
      });

    input.value = "";
  });
});
