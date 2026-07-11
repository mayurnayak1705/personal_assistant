const sendBtn = document.getElementById("sendBtn");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcomeScreen");
const typing = document.getElementById("typingIndicator");

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

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keydown", function(e){
    if(e.key === "Enter" && !e.shiftKey){
        e.preventDefault();
        sendMessage();
    }
});

async function sendMessage(){

    const text = input.value.trim();

    if(text === "") return;

    welcome.style.display = "none";

    addMessage(text,"user");

    input.value = "";

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

        addMessage(data.response,"assistant");

        // Defensive sync: keeps the client in step with the server's id in
        // the unlikely case they ever diverge.
        if(data.conversation_id){
            conversationId = data.conversation_id;
            sessionStorage.setItem(CONVERSATION_ID_KEY, conversationId);
        }

    }catch(err){

        typing.classList.add("hidden");

        addMessage("Unable to connect to assistant.","assistant");

    }

}

function addMessage(text,type){

    const wrapper = document.createElement("div");

    wrapper.className = "message " + type;

    const bubble = document.createElement("div");

    bubble.className = "bubble";

    bubble.innerHTML = marked.parse(text);

    wrapper.appendChild(bubble);

    messages.appendChild(wrapper);

    hljs.highlightAll();

    messages.scrollTop = messages.scrollHeight;

    window.scrollTo(0,document.body.scrollHeight);

}

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