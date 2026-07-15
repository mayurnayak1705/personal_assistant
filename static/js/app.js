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
const whatsappStatus = document.getElementById("whatsappStatus");
const notifBtn = document.getElementById("notifBtn");
const reminderPopup = document.getElementById("reminderPopup");
const reminderTitle = document.getElementById("reminderTitle");
const reminderDescription = document.getElementById("reminderDescription");
const reminderTime = document.getElementById("reminderTime");
const reminderAckBtn = document.getElementById("reminderAckBtn");
const notificationPanel = document.getElementById("notificationPanel");
const notificationList = document.getElementById("notificationList");
const notificationEmpty = document.getElementById("notificationEmpty");
const notificationCount = document.getElementById("notificationCount");
const replyContext = document.getElementById("replyContext");
const replyContactName = document.getElementById("replyContactName");
const cancelReplyBtn = document.getElementById("cancelReplyBtn");

const CONVERSATION_ID_KEY = "assistant_conversation_id";
const WHATSAPP_CURSOR_KEY = "whatsapp_message_cursor";
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
let replyTarget = null;

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

    const outboundReply = replyTarget;
    const replyRecipient = outboundReply
        ? (outboundReply.phoneNumber || outboundReply.name)
        : "";
    const backendText = outboundReply
        ? `Send this WhatsApp message to ${replyRecipient}: ${text}`
        : text;

    addMessage(text, "user");
    clearReplyTarget();

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
                message:backendText,
                conversation_id:conversationId,
                user_id:USER_ID
            })
        });

        const data = await response.json();

        typing.classList.add("hidden");

        addMessage(data.response, "assistant");
        if(data.artifact?.artifact_type === "expense_report"){
            addExpenseReport(data.artifact);
        }

        // Defensive sync: keeps the client in step with the server's id in
        // the unlikely case they ever diverge.
        if(data.conversation_id){
            conversationId = data.conversation_id;
            sessionStorage.setItem(CONVERSATION_ID_KEY, conversationId);
        }

    }catch(err){

        typing.classList.add("hidden");

        addMessage("Unable to connect to assistant.", "assistant");
        if(outboundReply) setReplyTarget(outboundReply);

    }

}

function setReplyTarget(target){
    replyTarget = target;
    replyContactName.textContent = target.name;
    replyContext.classList.remove("hidden");
    input.placeholder = `Reply to ${target.name}…`;
    input.focus();
}

function clearReplyTarget(){
    replyTarget = null;
    replyContext.classList.add("hidden");
    replyContactName.textContent = "";
    input.placeholder = "Ask anything…";
}

cancelReplyBtn.addEventListener("click", clearReplyTarget);

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

/* ---------- Structured expense reports ---------- */

const inrFormatter = new Intl.NumberFormat("en-IN", {
    style:"currency",
    currency:"INR",
    maximumFractionDigits:2
});
const expenseColours = ["#60a5fa", "#a78bfa", "#34d399", "#f59e0b", "#f472b6", "#22d3ee"];

function formatINR(value){
    return inrFormatter.format(Number(value || 0));
}

function expenseStat(label, value, context=""){
    const stat = document.createElement("div");
    stat.className = "expense-stat";
    const caption = document.createElement("span");
    caption.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    stat.append(caption, strong);
    if(context){
        const small = document.createElement("small");
        small.textContent = context;
        stat.appendChild(small);
    }
    return stat;
}

function addExpenseReport(report){
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant expense-report-message";
    const card = document.createElement("section");
    card.className = "expense-report";
    card.setAttribute("aria-label", "Expense report in Indian rupees");

    const header = document.createElement("div");
    header.className = "expense-report-head";
    const title = document.createElement("h3");
    title.textContent = "Spending overview";
    const period = document.createElement("span");
    period.textContent = `${report.period.start_date} – ${report.period.end_date}`;
    header.append(title, period);

    const summary = report.summary || {};
    const stats = document.createElement("div");
    stats.className = "expense-stats";
    stats.append(
        expenseStat("Spent", formatINR(summary.total_expenses), `${summary.transaction_count || 0} transactions`),
        expenseStat("Income", formatINR(summary.total_income)),
        expenseStat("Remaining", formatINR(summary.remaining_income)),
        expenseStat("Daily average", formatINR(summary.average_daily_spending))
    );
    if(summary.highest_expense){
        stats.appendChild(expenseStat(
            "Highest expense",
            formatINR(summary.highest_expense.amount),
            summary.highest_expense.category || "Uncategorised"
        ));
    }
    if(summary.budget !== null && summary.budget !== undefined){
        stats.appendChild(expenseStat(
            "Budget used",
            `${summary.budget_utilisation_percent || 0}%`,
            `of ${formatINR(summary.budget)}`
        ));
    }

    const charts = document.createElement("div");
    charts.className = "expense-charts";
    const categories = report.category_breakdown || [];
    if(categories.length){
        charts.appendChild(buildExpenseDonut(categories, summary.total_expenses));
    }
    const trend = report.spending_trend || [];
    if(trend.length){
        charts.appendChild(buildExpenseTrend(trend));
    }

    card.append(header, stats);
    if(charts.childElementCount) card.appendChild(charts);
    if((report.transactions || []).length){
        card.appendChild(buildExpenseTransactions(report.transactions, report.omitted_count || 0));
    }
    wrapper.appendChild(card);
    messages.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function buildExpenseDonut(categories, total){
    const figure = document.createElement("figure");
    figure.className = "expense-chart expense-donut-chart";
    const heading = document.createElement("figcaption");
    heading.textContent = "Category breakdown";
    const body = document.createElement("div");
    body.className = "expense-donut-body";
    const donut = document.createElement("div");
    donut.className = "expense-donut";
    donut.setAttribute("role", "img");
    donut.setAttribute("aria-label", categories.map(item => `${item.label}: ${formatINR(item.value)}`).join(", "));
    let cursor = 0;
    const segments = categories.map((item, index) => {
        const start = cursor;
        cursor += total ? (Number(item.value) / Number(total)) * 100 : 0;
        return `${expenseColours[index % expenseColours.length]} ${start}% ${cursor}%`;
    });
    donut.style.background = `conic-gradient(${segments.join(",")})`;
    const centre = document.createElement("span");
    centre.textContent = formatINR(total);
    donut.appendChild(centre);

    const legend = document.createElement("ul");
    legend.className = "expense-legend";
    categories.slice(0, 6).forEach((item, index) => {
        const row = document.createElement("li");
        const swatch = document.createElement("i");
        swatch.style.backgroundColor = expenseColours[index % expenseColours.length];
        const label = document.createElement("span");
        label.textContent = item.label;
        const value = document.createElement("strong");
        value.textContent = formatINR(item.value);
        row.append(swatch, label, value);
        legend.appendChild(row);
    });
    body.append(donut, legend);
    figure.append(heading, body);
    return figure;
}

function buildExpenseTrend(trend){
    const figure = document.createElement("figure");
    figure.className = "expense-chart expense-trend-chart";
    const heading = document.createElement("figcaption");
    heading.textContent = "Spending trend";
    const plot = document.createElement("div");
    plot.className = "expense-bars";
    const visible = trend.slice(-12);
    const maximum = Math.max(...visible.map(item => Number(item.value)), 1);
    visible.forEach(item => {
        const column = document.createElement("div");
        column.className = "expense-bar-column";
        const amount = document.createElement("span");
        amount.className = "expense-bar-value";
        amount.textContent = formatINR(item.value);
        const bar = document.createElement("i");
        bar.style.height = `${Math.max(5, (Number(item.value) / maximum) * 100)}%`;
        const label = document.createElement("small");
        label.textContent = item.label;
        column.setAttribute("aria-label", `${item.label}: ${formatINR(item.value)}`);
        column.append(amount, bar, label);
        plot.appendChild(column);
    });
    figure.append(heading, plot);
    return figure;
}

function buildExpenseTransactions(transactions, omittedCount){
    const section = document.createElement("section");
    section.className = "expense-transactions";
    const heading = document.createElement("h4");
    heading.textContent = "Recent matching expenses";
    const list = document.createElement("div");
    transactions.forEach(item => {
        const row = document.createElement("div");
        const details = document.createElement("span");
        details.textContent = `${item.date} · ${item.category}${item.note ? ` · ${item.note}` : ""}`;
        const amount = document.createElement("strong");
        amount.textContent = formatINR(item.amount);
        row.append(details, amount);
        list.appendChild(row);
    });
    section.append(heading, list);
    if(omittedCount){
        const note = document.createElement("p");
        note.textContent = `+ ${omittedCount} more expenses included in the summary`;
        section.appendChild(note);
    }
    return section;
}

/* ---------- Incoming WhatsApp messages ---------- */

function setWhatsAppStatus(connected){
    const dot = whatsappStatus.querySelector(".pill-dot");
    dot.classList.toggle("ok", connected);
    dot.classList.toggle("pending", !connected);
    whatsappStatus.lastChild.textContent = connected
        ? "WhatsApp Connected"
        : "WhatsApp Offline";
}

function addWhatsAppMessage(message){
    welcome.style.display = "none";
    chatWindow.classList.add("active");

    const wrapper = document.createElement("div");
    wrapper.className = "message whatsapp";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const sender = message.contact_name || message.phone_number || "WhatsApp";
    meta.textContent = `WhatsApp · ${sender}`;

    const body = document.createElement("div");
    body.textContent = message.body || "";

    const actions = document.createElement("div");
    actions.className = "whatsapp-actions";
    const replyButton = document.createElement("button");
    replyButton.type = "button";
    replyButton.className = "whatsapp-reply-btn";
    replyButton.textContent = "Reply";
    replyButton.setAttribute("aria-label", `Reply to ${sender} on WhatsApp`);
    replyButton.addEventListener("click", () => {
        setReplyTarget({
            name: sender,
            phoneNumber: message.phone_number || ""
        });
    });
    actions.appendChild(replyButton);

    bubble.append(meta, body, actions);
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    showNotice(`WhatsApp from ${sender}`, "💬", 4500);
}

let whatsappPolling = false;

async function pollWhatsApp(){
    if(whatsappPolling || document.hidden) return;
    whatsappPolling = true;
    try{
        const storedCursor = sessionStorage.getItem(WHATSAPP_CURSOR_KEY);
        const query = storedCursor === null
            ? ""
            : `?after_id=${encodeURIComponent(storedCursor)}`;
        const response = await fetch(`/api/whatsapp/messages${query}`);
        const data = await response.json();

        if(data.error){
            setWhatsAppStatus(false);
            return;
        }

        setWhatsAppStatus(true);
        for(const message of (data.messages || [])){
            addWhatsAppMessage(message);
        }
        if(data.cursor !== null && data.cursor !== undefined){
            sessionStorage.setItem(WHATSAPP_CURSOR_KEY, String(data.cursor));
        }
    }catch(_err){
        setWhatsAppStatus(false);
    }finally{
        whatsappPolling = false;
    }
}

pollWhatsApp();
setInterval(pollWhatsApp, 2000);
document.addEventListener("visibilitychange", () => {
    if(!document.hidden) pollWhatsApp();
});

/* ---------- Durable reminder notifications ---------- */

const reminderQueue = [];
const knownReminderIds = new Set();
const notificationReminders = new Map();
let activeReminder = null;
let reminderPolling = false;
let reminderPopupTimer = null;

function updateNotificationIndicator(){
    const hasPending = Boolean(activeReminder)
        || reminderQueue.length > 0
        || notificationReminders.size > 0;
    notifDot.classList.toggle("on", hasPending);
}

function reminderDueLabel(reminder){
    const dueAt = new Date(reminder.reminder_time);
    return Number.isNaN(dueAt.getTime())
        ? "Due now"
        : `Due ${dueAt.toLocaleString()}`;
}

function renderNotificationPanel(){
    notificationList.replaceChildren();
    const reminders = Array.from(notificationReminders.values());
    notificationCount.textContent = String(reminders.length);
    notificationEmpty.classList.toggle("hidden", reminders.length > 0);

    for(const reminder of reminders){
        const item = document.createElement("article");
        item.className = "notification-item";

        const head = document.createElement("div");
        head.className = "notification-item-head";
        const icon = document.createElement("span");
        icon.className = "notification-item-icon";
        icon.textContent = "⏰";
        const content = document.createElement("div");
        const title = document.createElement("h3");
        title.textContent = reminder.title || "Reminder";
        const description = document.createElement("p");
        description.textContent = reminder.description || "";
        content.append(title, description);
        head.append(icon, content);

        const due = document.createElement("time");
        due.textContent = reminderDueLabel(reminder);
        const acknowledge = document.createElement("button");
        acknowledge.type = "button";
        acknowledge.textContent = "Acknowledge";
        acknowledge.addEventListener("click", async () => {
            acknowledge.disabled = true;
            acknowledge.textContent = "Acknowledging…";
            const succeeded = await acknowledgeReminder(reminder);
            if(!succeeded){
                acknowledge.disabled = false;
                acknowledge.textContent = "Acknowledge";
            }
        });

        item.append(head, due, acknowledge);
        notificationList.appendChild(item);
    }
    updateNotificationIndicator();
}

function moveActiveReminderToNotifications(){
    if(!activeReminder) return;
    notificationReminders.set(activeReminder.id, activeReminder);
    activeReminder = null;
    reminderPopup.classList.add("hidden");
    reminderPopupTimer = null;
    renderNotificationPanel();
    renderNextReminder();
}

function renderNextReminder(){
    if(activeReminder || reminderQueue.length === 0) return;
    activeReminder = reminderQueue.shift();
    reminderTitle.textContent = activeReminder.title || "Reminder";
    reminderDescription.textContent = activeReminder.description || "";
    const dueAt = new Date(activeReminder.reminder_time);
    reminderTime.textContent = Number.isNaN(dueAt.getTime())
        ? "Due now"
        : `Due ${dueAt.toLocaleString()}`;
    reminderPopup.classList.remove("hidden");
    clearTimeout(reminderPopupTimer);
    reminderPopupTimer = setTimeout(moveActiveReminderToNotifications, 30000);
    updateNotificationIndicator();
}

function enqueueReminders(reminders){
    for(const reminder of reminders){
        if(knownReminderIds.has(reminder.id)) continue;
        knownReminderIds.add(reminder.id);
        reminderQueue.push(reminder);
    }
    renderNextReminder();
}

async function acknowledgeReminder(reminder){
    try{
        const response = await fetch(
            `/api/reminders/${encodeURIComponent(reminder.id)}/acknowledge`,
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({user_id: USER_ID})
            }
        );
        if(!response.ok) throw new Error("acknowledgement failed");

        notificationReminders.delete(reminder.id);
        if(activeReminder && activeReminder.id === reminder.id){
            activeReminder = null;
            clearTimeout(reminderPopupTimer);
            reminderPopupTimer = null;
            reminderPopup.classList.add("hidden");
        }
        renderNotificationPanel();
        renderNextReminder();
        return true;
    }catch(_err){
        showNotice("Could not acknowledge reminder. Please try again.", "⚠️", 4500);
        return false;
    }
}

async function pollReminders(){
    if(reminderPolling || document.hidden) return;
    reminderPolling = true;
    try{
        const response = await fetch(
            `/api/reminders/due?user_id=${encodeURIComponent(USER_ID)}`
        );
        if(!response.ok) return;
        const data = await response.json();
        enqueueReminders(data.reminders || []);
    }catch(_err){
        // The next poll retries. Pending reminders remain durable in Postgres.
    }finally{
        reminderPolling = false;
    }
}

reminderAckBtn.addEventListener("click", async () => {
    if(!activeReminder) return;
    const reminder = activeReminder;
    clearTimeout(reminderPopupTimer);
    reminderPopupTimer = null;
    reminderAckBtn.disabled = true;
    reminderAckBtn.textContent = "Acknowledging…";
    const succeeded = await acknowledgeReminder(reminder);
    reminderAckBtn.disabled = false;
    reminderAckBtn.textContent = "Acknowledge";
    if(!succeeded && activeReminder){
        reminderPopupTimer = setTimeout(moveActiveReminderToNotifications, 30000);
    }
});

notifBtn.addEventListener("click", () => {
    notificationPanel.classList.toggle("hidden");
});

renderNotificationPanel();

pollReminders();
setInterval(pollReminders, 5000);
document.addEventListener("visibilitychange", () => {
    if(!document.hidden) pollReminders();
});

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
