const sendBtn = document.getElementById("sendBtn");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcomeScreen");
const typing = document.getElementById("typingIndicator");

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
                message:text
            })

        });

        const data = await response.json();

        typing.classList.add("hidden");

        addMessage(data.response,"assistant");

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