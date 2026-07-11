const sendBtn = document.getElementById("sendBtn");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcomeScreen");
const typing = document.getElementById("typingIndicator");
const chatWindow = document.getElementById("chatWindow");
const attachBtn = document.getElementById("attachBtn");
const fileInput = document.getElementById("fileInput");
const voiceBtn = document.getElementById("voiceBtn");
const notice = document.getElementById("notice");
const noticeIcon = document.getElementById("noticeIcon");
const noticeText = document.getElementById("noticeText");
const notifDot = document.getElementById("notifDot");

const CONVERSATION_ID_KEY = "assistant_conversation_id";
const USER_ID = "mayur";

// sessionStorage is scoped to this tab and clears when the tab closes -
// which lines up well with "the chat session is over".
function getConversationId(){
    let id = sessionStorage.getItem(CONVERSATION_ID_KEY);
    if(!id){
        id = crypto.randomUUID();
        sessionStorage.setItem(CONVERSATION_ID_KEY, id);
    }
    return id;
}

let conversationId = getConversationId();

/* ---------- Floating notification card ---------- */

let noticeTimer = null;

function showNotice(text, icon = "✦", duration = 3200){
    clearTimeout(noticeTimer);
    noticeIcon.textContent = icon;
    noticeText.textContent = text;
    notice.classList.remove("hidden", "leaving");
    notifDot.classList.add("on");

    noticeTimer = setTimeout(() => {
        notice.classList.add("leaving");
        setTimeout(() => notice.classList.add("hidden"), 350);
    }, duration);
}

// Startup status
window.addEventListener("load", () => {
    setTimeout(() => showNotice("Memory Ready", "🧠"), 700);
});

/* ---------- Chat ---------- */

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keydown", function(e){
    if(e.key === "Enter" && !e.shiftKey){
        e.preventDefault();
        sendMessage();
    }
});

// Auto-grow the textarea with content
input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
});

async function sendMessage(){

    const text = input.value.trim();

    if(text === "") return;

    welcome.style.display = "none";
    chatWindow.classList.add("active");

    addMessage(text, "user");

    input.value = "";
    input.style.height = "auto";

    typing.classList.remove("hidden");

    try{

        const response = await fetch("/api/chat",{
            method:"POST",
            headers:{
                "Content-Type":"application/json"
            },
            body:JSON.stringify({
                message:text,
                conversation_id:conversationId,
                user_id:USER_ID
            })
        });

        const data = await response.json();

        typing.classList.add("hidden");

        addMessage(data.response, "assistant");

        // Defensive sync: keeps the client in step with the server's id in
        // the unlikely case they ever diverge.
        if(data.conversation_id){
            conversationId = data.conversation_id;
            sessionStorage.setItem(CONVERSATION_ID_KEY, conversationId);
        }

    }catch(err){

        typing.classList.add("hidden");

        addMessage("Unable to connect to assistant.", "assistant");

    }

}

function addMessage(text, type){

    const wrapper = document.createElement("div");
    wrapper.className = "message " + type;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = marked.parse(text);

    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);

    hljs.highlightAll();

    chatWindow.scrollTop = chatWindow.scrollHeight;
}

/* ---------- Document upload ---------- */

attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if(!file) return;

    showNotice("Document Uploaded — " + file.name, "📄");

    // Hook the file into the conversation so the backend can pick it up.
    const form = new FormData();
    form.append("file", file);
    form.append("conversation_id", conversationId);
    form.append("user_id", USER_ID);

    fetch("/api/upload", { method:"POST", body:form })
        .catch(() => {/* endpoint optional — the notice already confirmed the local pick */});

    fileInput.value = "";
});

/* ---------- Voice mode ---------- */

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let listening = false;

if(SpeechRecognition){
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;

    recognition.onresult = (e) => {
        input.value = Array.from(e.results).map(r => r[0].transcript).join("");
        input.dispatchEvent(new Event("input"));
    };

    recognition.onend = () => stopListening();
    recognition.onerror = () => stopListening();
}

function stopListening(){
    listening = false;
    voiceBtn.classList.remove("recording");
}

voiceBtn.addEventListener("click", () => {
    if(!recognition){
        showNotice("Voice not supported in this browser", "🎤");
        return;
    }
    if(listening){
        recognition.stop();
        stopListening();
        return;
    }
    listening = true;
    voiceBtn.classList.add("recording");
    showNotice("Listening…", "🎤", 2000);
    recognition.start();
});

/* ---------- Session flush ---------- */

// Flush the buffered chat session to the database when the tab closes or
// navigates away. sendBeacon fires reliably even during unload, unlike a
// normal fetch() call which the browser may cancel mid-flight.
function flushSession(){
    const id = sessionStorage.getItem(CONVERSATION_ID_KEY);
    if(!id) return;

    const payload = JSON.stringify({
        conversation_id:id,
        user_id:USER_ID
    });

    const blob = new Blob([payload], { type: "application/json" });
    navigator.sendBeacon("/api/session/end", blob);
}

window.addEventListener("pagehide", flushSession);
