async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value;
  
    if (!message) return;
  
    addMessage(message, "user");
  
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });
  
    const data = await res.json();
    addMessage(data.reply, "bot");
  
    input.value = "";
  }
  
  function addMessage(text, sender) {
    const chatBox = document.getElementById("chat-box");
    const div = document.createElement("div");
  
    div.className = sender;
    div.innerHTML = text;
  
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }