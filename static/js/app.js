const sendBtn = document.getElementById("sendBtn");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcomeScreen");
const welcomeGreeting = document.getElementById("welcomeGreeting");
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
const whatsappStatusText = document.getElementById("whatsappStatusText");
const gmailBtn = document.getElementById("gmailBtn");
const gmailBadge = document.getElementById("gmailBadge");
const gmailPanel = document.getElementById("gmailPanel");
const gmailTotal = document.getElementById("gmailTotal");
const gmailAccount = document.getElementById("gmailAccount");
const gmailComposeBtn = document.getElementById("gmailComposeBtn");
const gmailScheduleBtn = document.getElementById("gmailScheduleBtn");
const gmailUnreadList = document.getElementById("gmailUnreadList");
const gmailUnreadEmpty = document.getElementById("gmailUnreadEmpty");
const gmailUnreadCount = document.getElementById("gmailUnreadCount");
const gmailScheduledList = document.getElementById("gmailScheduledList");
const gmailScheduledEmpty = document.getElementById("gmailScheduledEmpty");
const gmailScheduledCount = document.getElementById("gmailScheduledCount");
const gmailReader = document.getElementById("gmailReader");
const gmailReaderSubject = document.getElementById("gmailReaderSubject");
const gmailReaderAvatar = document.getElementById("gmailReaderAvatar");
const gmailReaderFrom = document.getElementById("gmailReaderFrom");
const gmailReaderTo = document.getElementById("gmailReaderTo");
const gmailReaderDate = document.getElementById("gmailReaderDate");
const gmailReaderBody = document.getElementById("gmailReaderBody");
const gmailReaderClose = document.getElementById("gmailReaderClose");
const gmailReaderReply = document.getElementById("gmailReaderReply");
const tasksBtn = document.getElementById("tasksBtn");
const tasksBadge = document.getElementById("tasksBadge");
const tasksPanel = document.getElementById("tasksPanel");
const tasksTotal = document.getElementById("tasksTotal");
const taskOverviewList = document.getElementById("taskOverviewList");
const taskOverviewEmpty = document.getElementById("taskOverviewEmpty");
const taskFilterButtons = Array.from(document.querySelectorAll("[data-task-filter]"));
const notifBtn = document.getElementById("notifBtn");
const settingsBtn = document.getElementById("settingsBtn");
const settingsPanel = document.getElementById("settingsPanel");
const whatsappToggle = document.getElementById("whatsappToggle");
const whatsappToggleDescription = document.getElementById("whatsappToggleDescription");
const whatsappIntegrationStatus = document.getElementById("whatsappIntegrationStatus");
const whatsappConnectBtn = document.getElementById("whatsappConnectBtn");
const whatsappDisconnectBtn = document.getElementById("whatsappDisconnectBtn");
const whatsappPairingModal = document.getElementById("whatsappPairingModal");
const whatsappPairingClose = document.getElementById("whatsappPairingClose");
const whatsappPairingCancel = document.getElementById("whatsappPairingCancel");
const whatsappPairingRetry = document.getElementById("whatsappPairingRetry");
const whatsappQrImage = document.getElementById("whatsappQrImage");
const whatsappQrLoader = document.getElementById("whatsappQrLoader");
const whatsappPairingMessage = document.getElementById("whatsappPairingMessage");
const googleConnectBtn = document.getElementById("googleConnectBtn");
const calendarGoogleConnectBtn = document.getElementById("calendarGoogleConnectBtn");
const gmailIntegrationStatus = document.getElementById("gmailIntegrationStatus");
const calendarIntegrationStatus = document.getElementById("calendarIntegrationStatus");
const gmailIntegrationDescription = document.getElementById("gmailIntegrationDescription");
const calendarIntegrationDescription = document.getElementById("calendarIntegrationDescription");
const googleOauthFileInput = document.getElementById("googleOauthFileInput");
const themeToggle = document.getElementById("themeToggle");
const themeToggleDescription = document.getElementById("themeToggleDescription");
const reminderPopup = document.getElementById("reminderPopup");
const reminderTitle = document.getElementById("reminderTitle");
const reminderDescription = document.getElementById("reminderDescription");
const reminderTime = document.getElementById("reminderTime");
const reminderAckBtn = document.getElementById("reminderAckBtn");
const notificationPanel = document.getElementById("notificationPanel");
const notificationCount = document.getElementById("notificationCount");
const reminderNotificationList = document.getElementById("reminderNotificationList");
const reminderNotificationEmpty = document.getElementById("reminderNotificationEmpty");
const reminderNotificationCount = document.getElementById("reminderNotificationCount");
const taskNotificationList = document.getElementById("taskNotificationList");
const taskNotificationEmpty = document.getElementById("taskNotificationEmpty");
const taskNotificationCount = document.getElementById("taskNotificationCount");
const expenseImportNotificationList = document.getElementById("expenseImportNotificationList");
const expenseImportNotificationEmpty = document.getElementById("expenseImportNotificationEmpty");
const expenseImportNotificationCount = document.getElementById("expenseImportNotificationCount");
const replyContext = document.getElementById("replyContext");
const replyContactName = document.getElementById("replyContactName");
const cancelReplyBtn = document.getElementById("cancelReplyBtn");
const profileSetupModal = document.getElementById("profileSetupModal");
const profileSetupForm = document.getElementById("profileSetupForm");
const profileNameInput = document.getElementById("profileNameInput");
const profileSetupError = document.getElementById("profileSetupError");
const profileSetupSubmit = document.getElementById("profileSetupSubmit");

const CONVERSATION_ID_KEY = "assistant_conversation_id";
const WHATSAPP_CURSOR_KEY = "whatsapp_message_cursor";
const USER_ID = window.DEEP_THOUGHT_USER_ID || "local-user";
const THEME_KEY = "assistant_theme";
let whatsappEnabled = false;
let whatsappPaired = false;
let whatsappStateLoaded = false;
let whatsappToggleBusy = false;
let whatsappPairingStatus = "idle";
let whatsappPairingPollTimer = null;
let googleConnected = false;
let googleConfigured = false;
let googleConnectionBusy = false;

function setGoogleIntegrationState(status){
    googleConfigured = Boolean(status?.configured);
    googleConnected = Boolean(status?.connected);
    const badges = [gmailIntegrationStatus, calendarIntegrationStatus];
    badges.forEach((badge) => {
        badge.textContent = googleConnected
            ? "Connected"
            : googleConfigured
            ? "Ready to connect"
            : "Setup required";
        badge.classList.toggle("integration-status-live", googleConnected);
        badge.classList.toggle(
            "integration-status-error",
            googleConfigured && !googleConnected && Boolean(status?.error)
        );
    });
    const account = status?.email || "your Google account";
    gmailIntegrationDescription.textContent = googleConnected
        ? `Connected as ${account}.`
        : googleConfigured
        ? "OAuth configuration saved locally. Connect your Google account."
        : "Connect Google to send, schedule and read email.";
    calendarIntegrationDescription.textContent = googleConnected
        ? "Calendar access uses this same Google connection."
        : googleConfigured
        ? "Calendar will use the configured Google OAuth project."
        : "The same Google connection manages meetings and events.";
    [googleConnectBtn, calendarGoogleConnectBtn].forEach((button) => {
        button.textContent = googleConnected
            ? "Disconnect"
            : googleConfigured
            ? "Connect"
            : "Add OAuth JSON";
        button.disabled = googleConnectionBusy;
    });
}

async function loadGoogleIntegrationState(){
    try{
        const response = await fetch(
            `/api/integrations/google/status?user_id=${encodeURIComponent(USER_ID)}`
        );
        if(!response.ok) throw new Error("Google status unavailable");
        setGoogleIntegrationState(await response.json());
    }catch(err){
        setGoogleIntegrationState({connected:false,error:err.message});
    }
}

async function toggleGoogleIntegration(){
    if(googleConnectionBusy) return;
    if(!googleConfigured){
        googleOauthFileInput.click();
        return;
    }
    googleConnectionBusy = true;
    setGoogleIntegrationState({connected:googleConnected});
    try{
        if(googleConnected){
            if(!window.confirm("Disconnect Gmail and Google Calendar from Deep Thought?")) return;
            const response = await fetch(
                `/api/integrations/google/disconnect?user_id=${encodeURIComponent(USER_ID)}`,
                {method:"POST"}
            );
            if(!response.ok) throw new Error("Could not disconnect Google");
            googleConnected = false;
            showNotice("Google disconnected", "G");
        }else{
            const popup = window.open("about:blank", "deep-thought-google-oauth", "width=560,height=720");
            const response = await fetch(
                `/api/integrations/google/connect?user_id=${encodeURIComponent(USER_ID)}`,
                {method:"POST"}
            );
            const data = await response.json();
            if(!response.ok || !data.authorization_url){
                if(popup) popup.close();
                throw new Error(data.detail || "Could not start Google connection");
            }
            if(popup){
                popup.location.href = data.authorization_url;
                popup.focus();
            }else{
                window.location.href = data.authorization_url;
            }
        }
    }catch(err){
        showNotice(err.message || "Google connection failed", "!", 5000);
    }finally{
        googleConnectionBusy = false;
        await loadGoogleIntegrationState();
    }
}

googleOauthFileInput.addEventListener("change", async () => {
    const file = googleOauthFileInput.files?.[0];
    googleOauthFileInput.value = "";
    if(!file) return;
    googleConnectionBusy = true;
    setGoogleIntegrationState({configured:googleConfigured,connected:googleConnected});
    try{
        const clientConfig = JSON.parse(await file.text());
        const response = await fetch("/api/integrations/google/configure", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({user_id:USER_ID,client_config:clientConfig})
        });
        const data = await response.json();
        if(!response.ok) throw new Error(data.detail || "Invalid Google OAuth JSON");
        showNotice("Google OAuth configuration added", "G", 4200);
    }catch(err){
        showNotice(err.message || "Could not read OAuth JSON", "!", 5200);
    }finally{
        googleConnectionBusy = false;
        await loadGoogleIntegrationState();
    }
});

googleConnectBtn.addEventListener("click", toggleGoogleIntegration);
calendarGoogleConnectBtn.addEventListener("click", toggleGoogleIntegration);
window.addEventListener("message", async (event) => {
    if(event.origin !== window.location.origin) return;
    if(event.data?.type !== "deep-thought-google-oauth") return;
    await loadGoogleIntegrationState();
    showNotice(event.data.success ? "Google connected" : "Google connection failed", "G", 4500);
});
loadGoogleIntegrationState().then(() => {
    pollExpenseImports(false);
    setTimeout(() => pollExpenseImports(true), 2000);
});

function applyTheme(theme, persist = true){
    const selected = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = selected;
    document.documentElement.style.colorScheme = selected;
    if(persist){
        try{
            localStorage.setItem(THEME_KEY, selected);
        }catch(_err){
            // The visual switch still works when browser storage is disabled.
        }
    }
    const light = selected === "light";
    themeToggle.setAttribute("aria-checked", String(light));
    themeToggle.setAttribute("aria-label", light ? "Disable light mode" : "Enable light mode");
    themeToggleDescription.textContent = light
        ? "Light appearance is active."
        : "Dark appearance is active.";
}

applyTheme(document.documentElement.dataset.theme || "dark", false);
themeToggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
});

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
let userProfile = null;
let resolveProfileSetup = null;

function applyUserProfile(profile){
    userProfile = profile;
    const name = profile?.first_name || profile?.display_name;
    welcomeGreeting.textContent = name
        ? `${profile.greeting}, ${name}`
        : profile?.greeting || "Welcome";
}

async function loadUserProfile(){
    try{
        const response = await fetch(
            `/api/user/profile?user_id=${encodeURIComponent(USER_ID)}`
        );
        if(!response.ok) throw new Error("profile unavailable");
        userProfile = await response.json();
        applyUserProfile(userProfile);
        return userProfile;
    }catch(_err){
        welcomeGreeting.textContent = "Welcome";
        return null;
    }
}

function requestProfileName(){
    profileSetupError.classList.add("hidden");
    profileSetupError.textContent = "";
    profileSetupModal.classList.remove("hidden");
    requestAnimationFrame(() => profileNameInput.focus());
    return new Promise(resolve => {
        resolveProfileSetup = resolve;
    });
}

profileSetupForm.addEventListener("submit", async event => {
    event.preventDefault();
    const displayName = profileNameInput.value.trim();
    if(!displayName) return;

    profileSetupSubmit.disabled = true;
    profileSetupSubmit.textContent = "Saving…";
    profileSetupError.classList.add("hidden");
    try{
        const response = await fetch("/api/user/profile", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({user_id:USER_ID, display_name:displayName})
        });
        const payload = await response.json();
        if(!response.ok) throw new Error(payload.detail || "Could not save your name.");
        applyUserProfile(payload);
        profileSetupModal.classList.add("hidden");
        const resolver = resolveProfileSetup;
        resolveProfileSetup = null;
        if(resolver) resolver(payload);
    }catch(err){
        profileSetupError.textContent = err.message || "Could not save your name. Please try again.";
        profileSetupError.classList.remove("hidden");
        profileNameInput.focus();
    }finally{
        profileSetupSubmit.disabled = false;
        profileSetupSubmit.textContent = "Continue";
    }
});

async function initializeWelcome(){
    let profile = await loadUserProfile();
    if(profile?.needs_setup){
        profile = await requestProfileName();
    }
    if(profile?.time_period === "morning"){
        await loadDailyBriefing();
    }
}

// Recheck while the app remains open so a scheduled briefing appears without
// requiring a refresh. The server enforces the time and once-per-day delivery.
setInterval(() => {
    loadDailyBriefing();
}, 60 * 1000);

/* ---------- Floating notification card ---------- */

let noticeTimer = null;

/* ---------- Background notification sound ---------- */

let notificationAudioContext = null;
let notificationSoundPending = false;
let pendingNotificationKind = "reminder";

function scheduleNotificationChime(kind = "reminder"){
    if(!notificationAudioContext || notificationAudioContext.state !== "running"){
        notificationSoundPending = true;
        pendingNotificationKind = kind;
        return;
    }

    const context = notificationAudioContext;
    const start = context.currentTime + 0.02;
    const frequencies = kind === "task" ? [659.25, 880] : [880, 1174.66];

    frequencies.forEach((frequency, index) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const toneStart = start + (index * 0.18);
        const toneEnd = toneStart + 0.32;

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(frequency, toneStart);
        gain.gain.setValueAtTime(0.0001, toneStart);
        gain.gain.exponentialRampToValueAtTime(0.16, toneStart + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, toneEnd);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(toneStart);
        oscillator.stop(toneEnd + 0.02);
    });
    notificationSoundPending = false;
}

async function unlockNotificationSound(){
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if(!AudioContextClass) return;
    try{
        if(!notificationAudioContext){
            notificationAudioContext = new AudioContextClass();
        }
        if(notificationAudioContext.state === "suspended"){
            await notificationAudioContext.resume();
        }
        if(notificationSoundPending){
            scheduleNotificationChime(pendingNotificationKind);
        }
    }catch(_err){
        // The next user interaction will try again. Browsers intentionally
        // block audible playback until the page has been interacted with.
    }
}

function playNotificationSound(kind){
    if(!notificationAudioContext){
        notificationSoundPending = true;
        pendingNotificationKind = kind;
        return;
    }
    if(notificationAudioContext.state !== "running"){
        notificationSoundPending = true;
        pendingNotificationKind = kind;
        notificationAudioContext.resume()
            .then(() => {
                if(notificationSoundPending){
                    scheduleNotificationChime(pendingNotificationKind);
                }
            })
            .catch(() => {});
        return;
    }
    scheduleNotificationChime(kind);
}

document.addEventListener("pointerdown", unlockNotificationSound, {capture:true});
document.addEventListener("keydown", unlockNotificationSound, {capture:true});

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
        if(data.suggestion){
            addFollowUpSuggestion(data.suggestion);
        }
        if(data.artifact?.artifact_type === "expense_report"){
            addExpenseReport(data.artifact);
        }
        pollTasks();
        loadTaskOverview();
        loadGmailPanel();

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

function addDailyBriefing(briefing){
    welcome.style.display = "none";
    chatWindow.classList.add("active");

    const wrapper = document.createElement("div");
    wrapper.className = "message assistant daily-briefing-message";
    const bubble = document.createElement("div");
    bubble.className = "bubble daily-briefing-bubble";
    const eyebrow = document.createElement("span");
    eyebrow.className = "daily-briefing-eyebrow";
    eyebrow.textContent = "Daily briefing";
    const text = document.createElement("p");
    text.textContent = briefing.text;
    bubble.append(eyebrow, text);

    const facts = document.createElement("div");
    facts.className = "daily-briefing-facts";
    const factValues = [
        ["Due today", briefing.tasks?.due_today_count || 0],
        ["Overdue", briefing.tasks?.overdue_count || 0],
        ["Reminders", (briefing.reminders?.due_count || 0) + (briefing.reminders?.later_today_count || 0)],
        ["WhatsApp", briefing.whatsapp?.count || 0]
    ];
    factValues.forEach(([label, value]) => {
        const fact = document.createElement("span");
        fact.textContent = `${label}: ${value}`;
        facts.appendChild(fact);
    });
    bubble.appendChild(facts);
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function loadDailyBriefing(){
    try{
        const response = await fetch(
            `/api/briefing/daily?user_id=${encodeURIComponent(USER_ID)}`
        );
        if(!response.ok) return;
        const briefing = await response.json();
        if(briefing.should_show && briefing.text){
            addDailyBriefing(briefing);
        }
    }catch(_err){
        // Each integration remains available even if briefing aggregation fails.
    }
}

function addFollowUpSuggestion(suggestion){
    if(!suggestion?.label || !suggestion?.prompt) return;

    const wrapper = document.createElement("div");
    wrapper.className = "follow-up-suggestion";

    const caption = document.createElement("span");
    caption.textContent = "Suggested next step";

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = suggestion.label;
    button.title = suggestion.reason || "Use this follow-up";
    button.addEventListener("click", () => {
        input.value = suggestion.prompt;
        input.dispatchEvent(new Event("input"));
        input.focus();
    });

    wrapper.append(caption, button);
    messages.appendChild(wrapper);
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

function setWhatsAppStatus({enabled, connected, paired, pairing_status, error = null}){
    whatsappEnabled = Boolean(enabled);
    if(paired !== undefined) whatsappPaired = Boolean(paired);
    if(pairing_status) whatsappPairingStatus = pairing_status;
    whatsappStateLoaded = true;
    const dot = whatsappStatus.querySelector(".pill-dot");
    dot.classList.toggle("ok", whatsappPaired && whatsappEnabled && connected);
    dot.classList.toggle("pending", whatsappPaired && whatsappEnabled && !connected);
    dot.classList.toggle("off", !whatsappEnabled);
    whatsappStatusText.textContent = !whatsappPaired
        ? "WhatsApp Setup Required"
        : !whatsappEnabled
        ? "WhatsApp Off"
        : connected
        ? "WhatsApp Connected"
        : "WhatsApp Connecting";
    whatsappIntegrationStatus.textContent = !whatsappPaired
        ? "Setup required"
        : !whatsappEnabled
        ? "Off"
        : connected
        ? "Connected"
        : "Ready";
    whatsappIntegrationStatus.classList.toggle(
        "integration-status-live",
        whatsappPaired && whatsappEnabled && Boolean(connected)
    );
    whatsappIntegrationStatus.classList.toggle(
        "integration-status-error",
        whatsappPaired && Boolean(error)
    );
    whatsappConnectBtn.classList.toggle("hidden", whatsappPaired);
    whatsappDisconnectBtn.classList.toggle("hidden", !whatsappPaired);
    whatsappToggle.classList.toggle("hidden", !whatsappPaired);
    whatsappToggle.setAttribute("aria-checked", String(whatsappEnabled));
    whatsappToggle.setAttribute(
        "aria-label",
        whatsappEnabled ? "Disable WhatsApp" : "Enable WhatsApp"
    );
    whatsappToggleDescription.textContent = !whatsappPaired
        ? "Link WhatsApp by scanning a QR code."
        : !whatsappEnabled
        ? "Sending and receiving are disabled."
        : connected
        ? "Connected. Sending and receiving are enabled."
        : error || "Enabled, but currently disconnected.";
    if(!whatsappToggleBusy) whatsappToggle.disabled = false;
}

async function loadWhatsAppState(){
    try{
        const response = await fetch("/api/whatsapp/state");
        if(!response.ok) throw new Error("state unavailable");
        const state = await response.json();
        setWhatsAppStatus(state);
        if(state.enabled && state.paired) pollWhatsApp();
    }catch(_err){
        whatsappStateLoaded = true;
        setWhatsAppStatus({enabled:false, connected:false, error:"WhatsApp status is unavailable."});
        setTimeout(loadWhatsAppState, 5000);
    }
}

whatsappToggle.addEventListener("click", async () => {
    if(whatsappToggleBusy || !whatsappStateLoaded) return;
    whatsappToggleBusy = true;
    whatsappToggle.disabled = true;
    const requestedState = !whatsappEnabled;
    whatsappToggleDescription.textContent = requestedState
        ? "Connecting to WhatsApp…"
        : "Disconnecting from WhatsApp…";
    try{
        const response = await fetch("/api/whatsapp/state", {
            method:"PUT",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({enabled:requestedState})
        });
        const payload = await response.json();
        const state = response.ok ? payload : (payload.detail || payload);
        setWhatsAppStatus(state);
        if(!response.ok) throw new Error(state.error || "state update failed");
        if(!state.enabled){
            clearReplyTarget();
            showNotice("WhatsApp sending and receiving disabled", "💬");
        }else{
            showNotice("WhatsApp enabled", "💬");
            pollWhatsApp();
        }
    }catch(err){
        whatsappToggleDescription.textContent = err.message || "Could not update WhatsApp.";
    }finally{
        whatsappToggleBusy = false;
        whatsappToggle.disabled = false;
    }
});

whatsappDisconnectBtn.addEventListener("click", async () => {
    if(whatsappToggleBusy || !whatsappPaired) return;
    const confirmed = window.confirm(
        "Disconnect WhatsApp? This unlinks this device and removes its local session. You will need to scan a new QR code to reconnect."
    );
    if(!confirmed) return;

    whatsappToggleBusy = true;
    whatsappDisconnectBtn.disabled = true;
    whatsappToggle.disabled = true;
    whatsappToggleDescription.textContent = "Disconnecting and removing the local WhatsApp session…";
    try{
        const response = await fetch("/api/whatsapp/disconnect", {method:"POST"});
        const payload = await response.json();
        if(!response.ok) throw new Error(payload.detail || "Could not disconnect WhatsApp");
        clearReplyTarget();
        sessionStorage.removeItem(WHATSAPP_CURSOR_KEY);
        setWhatsAppStatus(payload);
        showNotice("WhatsApp disconnected. Scan a QR code to reconnect.", "💬", 5200);
    }catch(err){
        whatsappToggleDescription.textContent = err.message || "Could not disconnect WhatsApp.";
    }finally{
        whatsappToggleBusy = false;
        whatsappDisconnectBtn.disabled = false;
        whatsappToggle.disabled = false;
    }
});

function renderWhatsAppPairing(state){
    whatsappPairingStatus = state.status || state.pairing_status || "starting";
    const hasQr = whatsappPairingStatus === "qr" && Boolean(state.qr_image);
    whatsappQrImage.classList.toggle("hidden", !hasQr);
    whatsappQrLoader.classList.toggle(
        "hidden",
        !["starting", "success"].includes(whatsappPairingStatus)
    );
    if(hasQr) whatsappQrImage.src = state.qr_image;
    else whatsappQrImage.removeAttribute("src");
    whatsappPairingMessage.textContent = state.message || (
        hasQr ? "Scan this QR code with WhatsApp." : "Requesting a QR code…"
    );
    whatsappPairingMessage.classList.toggle("success", whatsappPairingStatus === "success");
    whatsappPairingMessage.classList.toggle(
        "error",
        ["error", "expired"].includes(whatsappPairingStatus)
    );
    whatsappPairingRetry.classList.toggle(
        "hidden",
        !["error", "expired"].includes(whatsappPairingStatus)
    );
    whatsappPairingCancel.textContent = whatsappPairingStatus === "success" ? "Close" : "Cancel";
    if(state.paired !== undefined){
        setWhatsAppStatus(state);
    }
}

function stopWhatsAppPairingPolling(){
    if(whatsappPairingPollTimer){
        clearInterval(whatsappPairingPollTimer);
        whatsappPairingPollTimer = null;
    }
}

async function pollWhatsAppPairing(){
    try{
        const response = await fetch("/api/whatsapp/pairing");
        if(!response.ok) throw new Error("Pairing status unavailable");
        const state = await response.json();
        renderWhatsAppPairing(state);
        if(state.status === "success"){
            stopWhatsAppPairingPolling();
            showNotice("WhatsApp connected", "💬", 4200);
        }else if(["error", "expired"].includes(state.status)){
            stopWhatsAppPairingPolling();
        }
    }catch(err){
        renderWhatsAppPairing({status:"error",message:err.message});
        stopWhatsAppPairingPolling();
    }
}

async function startWhatsAppPairing(){
    whatsappPairingModal.classList.remove("hidden");
    renderWhatsAppPairing({status:"starting",message:"Requesting a QR code from WhatsApp…"});
    try{
        const response = await fetch("/api/whatsapp/pairing/start", {method:"POST"});
        const state = await response.json();
        if(!response.ok) throw new Error(state.detail || "Could not start WhatsApp pairing");
        renderWhatsAppPairing(state);
        stopWhatsAppPairingPolling();
        whatsappPairingPollTimer = setInterval(pollWhatsAppPairing, 1000);
        await pollWhatsAppPairing();
    }catch(err){
        renderWhatsAppPairing({status:"error",message:err.message});
    }
}

async function closeWhatsAppPairing(){
    stopWhatsAppPairingPolling();
    whatsappPairingModal.classList.add("hidden");
    if(["starting", "qr"].includes(whatsappPairingStatus)){
        try{
            await fetch("/api/whatsapp/pairing", {method:"DELETE"});
        }catch(_err){
            // The helper also exits on its own when its QR sequence expires.
        }
    }
    await loadWhatsAppState();
}

whatsappConnectBtn.addEventListener("click", startWhatsAppPairing);
whatsappPairingRetry.addEventListener("click", startWhatsAppPairing);
whatsappPairingClose.addEventListener("click", closeWhatsAppPairing);
whatsappPairingCancel.addEventListener("click", closeWhatsAppPairing);
whatsappPairingModal.addEventListener("click", (event) => {
    if(event.target === whatsappPairingModal) closeWhatsAppPairing();
});
document.addEventListener("keydown", (event) => {
    if(event.key === "Escape" && !whatsappPairingModal.classList.contains("hidden")){
        closeWhatsAppPairing();
    }
});

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

function addWhatsAppBacklog(messageBatch){
    welcome.style.display = "none";
    chatWindow.classList.add("active");

    const groups = new Map();
    for(const message of messageBatch){
        const sender = message.contact_name || message.phone_number || "WhatsApp";
        const key = message.phone_number || message.chat_jid || sender;
        if(!groups.has(key)) groups.set(key, {sender, messages:[], phoneNumber:message.phone_number || ""});
        groups.get(key).messages.push(message);
    }

    const wrapper = document.createElement("div");
    wrapper.className = "message whatsapp whatsapp-backlog";
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const header = document.createElement("div");
    header.className = "whatsapp-backlog-head";
    const heading = document.createElement("div");
    const eyebrow = document.createElement("span");
    eyebrow.className = "message-meta";
    eyebrow.textContent = "WhatsApp · While you were away";
    const title = document.createElement("strong");
    title.textContent = `${messageBatch.length} messages from ${groups.size} ${groups.size === 1 ? "contact" : "contacts"}`;
    heading.append(eyebrow, title);
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "whatsapp-backlog-toggle";
    toggle.textContent = "View messages";
    toggle.setAttribute("aria-expanded", "false");
    header.append(heading, toggle);

    const summary = document.createElement("div");
    summary.className = "whatsapp-backlog-summary";
    const details = document.createElement("div");
    details.className = "whatsapp-backlog-details hidden";

    for(const group of groups.values()){
        const latest = group.messages[group.messages.length - 1];
        const row = document.createElement("div");
        row.className = "whatsapp-backlog-row";
        const copy = document.createElement("div");
        const sender = document.createElement("strong");
        sender.textContent = group.sender;
        const preview = document.createElement("span");
        preview.textContent = `${group.messages.length} ${group.messages.length === 1 ? "message" : "messages"} · ${latest.body || "Message"}`;
        copy.append(sender, preview);
        const reply = document.createElement("button");
        reply.type = "button";
        reply.className = "whatsapp-reply-btn";
        reply.textContent = "Reply";
        reply.addEventListener("click", () => setReplyTarget({
            name:group.sender,
            phoneNumber:group.phoneNumber
        }));
        row.append(copy, reply);
        summary.appendChild(row);

        for(const message of group.messages){
            const item = document.createElement("div");
            item.className = "whatsapp-backlog-message";
            const itemMeta = document.createElement("span");
            const parsedTime = new Date(message.timestamp);
            itemMeta.textContent = Number.isNaN(parsedTime.getTime())
                ? group.sender
                : `${group.sender} · ${parsedTime.toLocaleString()}`;
            const itemBody = document.createElement("p");
            itemBody.textContent = message.body || "";
            item.append(itemMeta, itemBody);
            details.appendChild(item);
        }
    }

    toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.textContent = expanded ? "Hide messages" : "View messages";
        details.classList.toggle("hidden", !expanded);
        summary.classList.toggle("hidden", expanded);
    });

    bubble.append(header, summary, details);
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    showNotice(`${messageBatch.length} WhatsApp messages received`, "💬", 4500);
}

let whatsappPolling = false;

async function pollWhatsApp(){
    if(whatsappPolling || document.hidden || !whatsappEnabled) return;
    whatsappPolling = true;
    try{
        const storedCursor = sessionStorage.getItem(WHATSAPP_CURSOR_KEY);
        const query = new URLSearchParams({
            user_id:USER_ID,
            conversation_id:conversationId,
            limit:"200"
        });
        if(storedCursor !== null) query.set("after_id", storedCursor);
        const response = await fetch(`/api/whatsapp/messages?${query.toString()}`);
        const data = await response.json();

        if(data.enabled === false){
            setWhatsAppStatus({enabled:false, connected:false});
            return;
        }

        if(data.error){
            setWhatsAppStatus({enabled:true, connected:false, error:data.error});
            return;
        }

        setWhatsAppStatus({enabled:true, connected:data.connected !== false});
        const incoming = data.messages || [];
        if(incoming.length >= 4) addWhatsAppBacklog(incoming);
        else incoming.forEach(addWhatsAppMessage);
        if(data.cursor !== null && data.cursor !== undefined){
            sessionStorage.setItem(WHATSAPP_CURSOR_KEY, String(data.cursor));
        }
    }catch(_err){
        setWhatsAppStatus({enabled:whatsappEnabled, connected:false, error:"WhatsApp is unavailable."});
    }finally{
        whatsappPolling = false;
    }
}

loadWhatsAppState();
setInterval(pollWhatsApp, 2000);
document.addEventListener("visibilitychange", () => {
    if(!document.hidden) pollWhatsApp();
});

/* ---------- Gmail ---------- */

let gmailLoading = false;
let activeGmailMessage = null;

function gmailTime(value){
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString();
}

function useGmailPrompt(prompt){
    input.value = prompt;
    input.dispatchEvent(new Event("input"));
    input.focus();
    gmailPanel.classList.add("hidden");
    gmailBtn.setAttribute("aria-expanded", "false");
}

function closeGmailReader(){
    gmailReader.classList.add("hidden");
    activeGmailMessage = null;
}

function setGmailReaderMetadata(email){
    gmailReaderSubject.textContent = email.subject || "(no subject)";
    gmailReaderFrom.textContent = email.from || "Unknown sender";
    gmailReaderTo.textContent = email.to ? `To: ${email.to}` : "";
    gmailReaderDate.textContent = gmailTime(email.date);
    const initial = String(email.from || "").trim().match(/[A-Za-z0-9]/)?.[0];
    gmailReaderAvatar.textContent = initial?.toUpperCase() || "✉";
}

function appendSafeEmailText(container, value){
    const urlPattern = /https?:\/\/[^\s]+/g;
    let cursor = 0;
    for(const match of value.matchAll(urlPattern)){
        container.appendChild(document.createTextNode(value.slice(cursor, match.index)));
        let url = match[0];
        let trailing = "";
        while(/[.,;!?]$/.test(url)){
            trailing = url.slice(-1) + trailing;
            url = url.slice(0, -1);
        }
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.title = url;
        try{
            link.textContent = `Open ${new URL(url).hostname}`;
        }catch(_err){
            link.textContent = "Open link";
        }
        container.append(link, document.createTextNode(trailing));
        cursor = (match.index || 0) + match[0].length;
    }
    container.appendChild(document.createTextNode(value.slice(cursor)));
}

function renderGmailBody(value){
    gmailReaderBody.replaceChildren();
    const cleaned = String(value || "")
        .replace(/\r/g, "")
        .replace(/^\s*\[image:[^\]]*\]\s*$/gim, "")
        .replace(/<(https?:\/\/[^>]+)>/g, "$1")
        .trim();
    if(!cleaned){
        gmailReaderBody.textContent = "This email has no readable text body.";
        return;
    }
    const blocks = cleaned
        .split(/\n\s*\n+/)
        .map(block => block.split("\n").map(line => line.trim()).filter(Boolean).join(" "))
        .filter(Boolean);
    for(const block of blocks){
        const paragraph = document.createElement("p");
        appendSafeEmailText(paragraph, block);
        gmailReaderBody.appendChild(paragraph);
    }
}

async function openGmailMessage(summary){
    activeGmailMessage = summary;
    setGmailReaderMetadata(summary);
    gmailReaderBody.textContent = "Loading message…";
    gmailReaderReply.disabled = true;
    gmailReader.classList.remove("hidden");
    gmailPanel.classList.add("hidden");
    gmailBtn.setAttribute("aria-expanded", "false");
    gmailReaderClose.focus();

    try{
        const query = new URLSearchParams({
            user_id:USER_ID,
            conversation_id:conversationId
        });
        const response = await fetch(
            `/api/gmail/messages/${encodeURIComponent(summary.id)}?${query.toString()}`
        );
        if(!response.ok) throw new Error("message unavailable");
        const result = await response.json();
        const email = result.email || summary;
        activeGmailMessage = email;
        setGmailReaderMetadata(email);
        renderGmailBody(email.body || email.snippet);
        gmailReaderReply.disabled = false;
    }catch(_err){
        gmailReaderBody.textContent = "This email could not be loaded. Please try again.";
    }
}

gmailReaderClose.addEventListener("click", closeGmailReader);
gmailReader.addEventListener("pointerdown", event => {
    if(event.target === gmailReader) closeGmailReader();
});
gmailReaderReply.addEventListener("click", () => {
    if(!activeGmailMessage) return;
    const email = activeGmailMessage;
    closeGmailReader();
    useGmailPrompt(
        `Reply to Gmail message ${email.id} from ${email.from} about "${email.subject}": `
    );
});

async function runGmailAction(path, button){
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try{
        const response = await fetch(path, {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({user_id:USER_ID, conversation_id:conversationId})
        });
        if(!response.ok) throw new Error("Gmail action failed");
        await loadGmailPanel(true);
    }catch(_err){
        button.disabled = false;
        button.textContent = original;
        showNotice("Could not update Gmail.", "✉️", 4500);
    }
}

function renderUnreadEmails(emails){
    gmailUnreadList.replaceChildren();
    gmailUnreadCount.textContent = String(emails.length);
    gmailTotal.textContent = String(emails.length);
    gmailBadge.textContent = emails.length > 99 ? "99+" : String(emails.length);
    gmailBadge.classList.toggle("hidden", emails.length === 0);
    gmailUnreadEmpty.classList.toggle("hidden", emails.length > 0);

    for(const email of emails){
        const item = document.createElement("article");
        item.className = "gmail-item";
        item.setAttribute("role", "button");
        item.tabIndex = 0;
        item.setAttribute("aria-label", `Open email: ${email.subject || "No subject"}`);
        item.addEventListener("click", event => {
            if(event.target.closest("button")) return;
            openGmailMessage(email);
        });
        item.addEventListener("keydown", event => {
            if(event.target !== item || !["Enter", " "].includes(event.key)) return;
            event.preventDefault();
            openGmailMessage(email);
        });
        const head = document.createElement("div");
        head.className = "gmail-item-head";
        const subject = document.createElement("h4");
        subject.textContent = email.subject || "(no subject)";
        const date = document.createElement("time");
        date.textContent = gmailTime(email.date);
        head.append(subject, date);
        const sender = document.createElement("p");
        sender.className = "gmail-sender";
        sender.textContent = email.from || "Unknown sender";
        const snippet = document.createElement("p");
        snippet.className = "gmail-snippet";
        snippet.textContent = email.snippet || "";
        const actions = document.createElement("div");
        actions.className = "gmail-actions";
        const reply = document.createElement("button");
        reply.type = "button";
        reply.textContent = "Reply";
        reply.addEventListener("click", () => useGmailPrompt(
            `Reply to Gmail message ${email.id} from ${email.from} about "${email.subject}": `
        ));
        const read = document.createElement("button");
        read.type = "button";
        read.textContent = "Mark read";
        read.addEventListener("click", () => runGmailAction(
            `/api/gmail/messages/${encodeURIComponent(email.id)}/read`, read
        ));
        const archive = document.createElement("button");
        archive.type = "button";
        archive.textContent = "Archive";
        archive.addEventListener("click", () => runGmailAction(
            `/api/gmail/messages/${encodeURIComponent(email.id)}/archive`, archive
        ));
        actions.append(reply, read, archive);
        item.append(head, sender, snippet, actions);
        gmailUnreadList.appendChild(item);
    }
}

function renderScheduledEmails(emails){
    gmailScheduledList.replaceChildren();
    gmailScheduledCount.textContent = String(emails.length);
    gmailScheduledEmpty.classList.toggle("hidden", emails.length > 0);
    for(const email of emails){
        const item = document.createElement("article");
        item.className = "gmail-item";
        const head = document.createElement("div");
        head.className = "gmail-item-head";
        const subject = document.createElement("h4");
        subject.textContent = email.subject || "(no subject)";
        const date = document.createElement("time");
        date.textContent = gmailTime(email.send_at);
        head.append(subject, date);
        const recipient = document.createElement("p");
        recipient.className = "gmail-sender";
        recipient.textContent = `To: ${(email.recipients?.to || []).join(", ")}`;
        const actions = document.createElement("div");
        actions.className = "gmail-actions";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", () => runGmailAction(
            `/api/gmail/scheduled/${encodeURIComponent(email.id)}/cancel`, cancel
        ));
        actions.appendChild(cancel);
        item.append(head, recipient, actions);
        gmailScheduledList.appendChild(item);
    }
}

async function loadGmailPanel(force = false){
    if(gmailLoading && !force) return;
    gmailLoading = true;
    try{
        const statusResponse = await fetch("/api/gmail/status");
        const status = await statusResponse.json();
        if(!status.authenticated){
            gmailAccount.textContent = status.error || "Gmail OAuth setup required.";
            renderUnreadEmails([]);
            renderScheduledEmails([]);
            return;
        }
        gmailAccount.textContent = `From: ${status.email || "connected Gmail account"}`;
        const [unreadResponse, scheduledResponse] = await Promise.all([
            fetch("/api/gmail/unread?limit=20"),
            fetch(`/api/gmail/scheduled?user_id=${encodeURIComponent(USER_ID)}&limit=20`)
        ]);
        if(unreadResponse.ok){
            const unread = await unreadResponse.json();
            renderUnreadEmails(unread.messages || []);
        }
        if(scheduledResponse.ok){
            const scheduled = await scheduledResponse.json();
            renderScheduledEmails(scheduled.scheduled_emails || []);
        }
    }catch(_err){
        gmailAccount.textContent = "Gmail is currently unavailable.";
    }finally{
        gmailLoading = false;
    }
}

gmailComposeBtn.addEventListener("click", () => useGmailPrompt("Draft an email to "));
gmailScheduleBtn.addEventListener("click", () => useGmailPrompt("Schedule an email to "));

/* ---------- Durable reminder notifications ---------- */

const reminderQueue = [];
const knownReminderIds = new Set();
const notificationReminders = new Map();
const notificationTasks = new Map();
const notificationExpenseImports = new Map();
const knownExpenseImportIds = new Set();
const knownTaskIds = new Set();
let taskOverview = [];
let taskOverviewFilter = "active";
let taskOverviewLoading = false;
let activeReminder = null;
let reminderPolling = false;
let reminderPopupTimer = null;
let taskPolling = false;
let expenseImportPolling = false;

function updateNotificationIndicator(){
    const hasPending = Boolean(activeReminder)
        || reminderQueue.length > 0
        || notificationReminders.size > 0
        || notificationTasks.size > 0
        || notificationExpenseImports.size > 0;
    notifDot.classList.toggle("on", hasPending);
}

function updateNotificationCount(){
    notificationCount.textContent = String(
        notificationReminders.size + notificationTasks.size + notificationExpenseImports.size
    );
    reminderNotificationCount.textContent = String(notificationReminders.size);
    taskNotificationCount.textContent = String(notificationTasks.size);
    expenseImportNotificationCount.textContent = String(notificationExpenseImports.size);
}

const EXPENSE_IMPORT_CATEGORIES = [
    "food", "transport", "housing", "utilities", "health", "education", "family_kids",
    "entertainment", "shopping", "subscriptions", "personal_care", "gifts_donations",
    "finance_fees", "business", "travel", "home", "pet", "taxes", "investments", "misc"
];

function renderExpenseImportNotifications(){
    expenseImportNotificationList.replaceChildren();
    const imports = Array.from(notificationExpenseImports.values());
    expenseImportNotificationEmpty.classList.toggle("hidden", imports.length > 0);
    for(const imported of imports){
        const item = document.createElement("article");
        item.className = "notification-item notification-expense-import";
        const head = document.createElement("div");
        head.className = "notification-item-head";
        const icon = document.createElement("span");
        icon.className = "notification-item-icon";
        icon.textContent = "₹";
        const content = document.createElement("div");
        const title = document.createElement("h3");
        title.textContent = `${formatINR(imported.amount)} · ${imported.merchant || "Bank transaction"}`;
        const description = document.createElement("p");
        description.textContent = `Added from ${imported.bank_name || "bank"} email on ${imported.transaction_date}.`;
        content.append(title, description);
        head.append(icon, content);
        item.appendChild(head);

        if(imported.status === "needs_category"){
            const prompt = document.createElement("p");
            prompt.className = "expense-category-prompt";
            prompt.textContent = "Which category does this expense belong to?";
            item.appendChild(prompt);
            if(imported.suggested_category){
                const suggestion = document.createElement("button");
                suggestion.type = "button";
                suggestion.className = "expense-category-suggestion";
                suggestion.textContent = `Suggested from your history: ${imported.suggested_category.replaceAll("_", " ")}`;
                suggestion.addEventListener("click", () => resolveExpenseImport(
                    imported, "categorize", imported.suggested_category, suggestion
                ));
                item.appendChild(suggestion);
            }
            const select = document.createElement("select");
            select.setAttribute("aria-label", `Category for ${imported.merchant || "expense"}`);
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Choose category";
            select.appendChild(placeholder);
            EXPENSE_IMPORT_CATEGORIES.forEach(category => {
                const option = document.createElement("option");
                option.value = category;
                option.textContent = category.replaceAll("_", " ");
                select.appendChild(option);
            });
            select.addEventListener("change", () => {
                if(select.value) resolveExpenseImport(imported, "categorize", select.value, select);
            });
            item.appendChild(select);
        }else{
            const category = document.createElement("span");
            category.className = "expense-import-category";
            category.textContent = `Category: ${(imported.category || "misc").replaceAll("_", " ")}`;
            item.appendChild(category);
        }

        const actions = document.createElement("div");
        actions.className = "notification-item-actions";
        const keep = document.createElement("button");
        keep.type = "button";
        keep.textContent = imported.status === "needs_category" ? "Keep as misc" : "Keep";
        keep.addEventListener("click", () => resolveExpenseImport(imported, "keep", null, keep));
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "expense-import-delete";
        remove.textContent = "Delete";
        remove.addEventListener("click", () => resolveExpenseImport(imported, "delete", null, remove));
        actions.append(keep, remove);
        item.appendChild(actions);
        expenseImportNotificationList.appendChild(item);
    }
    updateNotificationCount();
    updateNotificationIndicator();
}

async function resolveExpenseImport(imported, action, category, control){
    control.disabled = true;
    try{
        const response = await fetch(`/api/expense-imports/${encodeURIComponent(imported.id)}/resolve`, {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({action, category, user_id:USER_ID, conversation_id:conversationId})
        });
        if(!response.ok) throw new Error("Could not update imported expense");
        const result = await response.json();
        notificationExpenseImports.delete(imported.id);
        renderExpenseImportNotifications();
        if(result.suggestion) addFollowUpSuggestion(result.suggestion);
        showNotice(
            action === "delete" ? "Imported expense deleted" : action === "categorize" ? `Expense categorized as ${category.replaceAll("_", " ")}` : "Imported expense kept",
            action === "delete" ? "🗑" : "₹",
            4200
        );
    }catch(_err){
        control.disabled = false;
        showNotice("Could not update the imported expense.", "⚠️", 4500);
    }
}

async function pollExpenseImports(scan = false){
    if(expenseImportPolling || !googleConnected) return;
    expenseImportPolling = true;
    try{
        const response = await fetch(`/api/expense-imports?scan=${scan ? "true" : "false"}&limit=50`);
        if(!response.ok) return;
        const data = await response.json();
        const current = new Set((data.imports || []).map(item => item.id));
        for(const importId of notificationExpenseImports.keys()){
            if(!current.has(importId)) notificationExpenseImports.delete(importId);
        }
        const newlyImported = [];
        for(const imported of (data.imports || [])){
            notificationExpenseImports.set(imported.id, imported);
            if(!knownExpenseImportIds.has(imported.id)){
                knownExpenseImportIds.add(imported.id);
                newlyImported.push(imported);
            }
        }
        renderExpenseImportNotifications();
        if(newlyImported.length){
            playNotificationSound("expense");
            showNotice(
                newlyImported.length === 1
                    ? `${formatINR(newlyImported[0].amount)} expense added from Gmail`
                    : `${newlyImported.length} expenses added from Gmail`,
                "₹", 5200
            );
        }
    }catch(_err){
        // Gmail or the network may be temporarily unavailable; retry later.
    }finally{
        expenseImportPolling = false;
    }
}

function reminderDueLabel(reminder){
    const dueAt = new Date(reminder.reminder_time);
    return Number.isNaN(dueAt.getTime())
        ? "Due now"
        : `Due ${dueAt.toLocaleString()}`;
}

function renderNotificationPanel(){
    reminderNotificationList.replaceChildren();
    const reminders = Array.from(notificationReminders.values());
    reminderNotificationEmpty.classList.toggle("hidden", reminders.length > 0);

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
        reminderNotificationList.appendChild(item);
    }
    updateNotificationCount();
    updateNotificationIndicator();
}

function taskDueLabel(task){
    const dueAt = new Date(task.due_date);
    if(Number.isNaN(dueAt.getTime())) return "No due date";
    const overdue = dueAt.getTime() < Date.now();
    return `${overdue ? "Overdue" : "Due"} ${dueAt.toLocaleString()}`;
}

function taskStatusLabel(status){
    return {
        todo:"To do",
        in_progress:"In progress",
        completed:"Completed",
        cancelled:"Cancelled"
    }[status] || String(status || "Unknown").replaceAll("_", " ");
}

function filteredTaskOverview(){
    if(taskOverviewFilter === "active"){
        return taskOverview.filter(task => ["todo", "in_progress"].includes(task.status));
    }
    if(taskOverviewFilter === "completed"){
        return taskOverview.filter(task => task.status === "completed");
    }
    return taskOverview;
}

function updateTasksBadge(){
    const activeCount = taskOverview.filter(
        task => ["todo", "in_progress"].includes(task.status)
    ).length;
    tasksBadge.textContent = activeCount > 99 ? "99+" : String(activeCount);
    tasksBadge.classList.toggle("hidden", activeCount === 0);
}

function renderTaskOverview(){
    taskOverviewList.replaceChildren();
    const tasks = filteredTaskOverview();
    tasksTotal.textContent = String(tasks.length);
    taskOverviewEmpty.classList.toggle("hidden", tasks.length > 0);
    taskOverviewEmpty.textContent = taskOverviewFilter === "active"
        ? "No active tasks."
        : taskOverviewFilter === "completed"
        ? "No completed tasks."
        : "No tasks yet.";

    for(const task of tasks){
        const item = document.createElement("article");
        item.className = "task-overview-item";

        const heading = document.createElement("div");
        heading.className = "task-overview-heading";
        const title = document.createElement("h3");
        title.textContent = task.title || "Untitled task";
        const status = document.createElement("span");
        status.className = `task-status ${task.status || "unknown"}`;
        status.textContent = taskStatusLabel(task.status);
        heading.append(title, status);
        item.appendChild(heading);

        if(task.description){
            const description = document.createElement("p");
            description.textContent = task.description;
            item.appendChild(description);
        }

        const metadata = document.createElement("div");
        metadata.className = "task-overview-meta";
        const priority = document.createElement("span");
        priority.className = `task-priority ${task.priority || "normal"}`;
        priority.textContent = `${task.priority || "normal"} priority`;
        metadata.appendChild(priority);
        if(task.category){
            const category = document.createElement("span");
            category.textContent = task.category;
            metadata.appendChild(category);
        }
        const due = document.createElement("time");
        due.textContent = task.due_date ? taskDueLabel(task) : "No due date";
        metadata.appendChild(due);
        item.appendChild(metadata);

        if(["todo", "in_progress"].includes(task.status)){
            const actions = document.createElement("div");
            actions.className = "notification-item-actions";
            const complete = document.createElement("button");
            complete.type = "button";
            complete.className = "task-complete-btn";
            complete.textContent = "Complete";
            complete.addEventListener("click", () => runTaskAction(task, "complete", complete));
            actions.appendChild(complete);
            item.appendChild(actions);
        }

        taskOverviewList.appendChild(item);
    }
    updateTasksBadge();
}

async function loadTaskOverview(){
    if(taskOverviewLoading) return;
    taskOverviewLoading = true;
    try{
        const response = await fetch(
            `/api/tasks?user_id=${encodeURIComponent(USER_ID)}&view=all&limit=200`
        );
        if(!response.ok) return;
        const data = await response.json();
        taskOverview = data.tasks || [];
        renderTaskOverview();
    }catch(_err){
        // Keep the previous task list visible; the next refresh retries.
    }finally{
        taskOverviewLoading = false;
    }
}

taskFilterButtons.forEach(button => {
    button.addEventListener("click", () => {
        taskOverviewFilter = button.dataset.taskFilter;
        taskFilterButtons.forEach(item => {
            const selected = item === button;
            item.classList.toggle("active", selected);
            item.setAttribute("aria-selected", String(selected));
        });
        renderTaskOverview();
    });
});

function renderTaskNotifications(){
    taskNotificationList.replaceChildren();
    const tasks = Array.from(notificationTasks.values());
    taskNotificationEmpty.classList.toggle("hidden", tasks.length > 0);

    for(const task of tasks){
        const item = document.createElement("article");
        item.className = "notification-item notification-task";

        const head = document.createElement("div");
        head.className = "notification-item-head";
        const icon = document.createElement("span");
        icon.className = "notification-item-icon";
        icon.textContent = "✓";
        const content = document.createElement("div");
        const title = document.createElement("h3");
        title.textContent = task.title || "Task";
        content.appendChild(title);
        if(task.description){
            const description = document.createElement("p");
            description.textContent = task.description;
            content.appendChild(description);
        }
        if(task.priority){
            const priority = document.createElement("span");
            priority.className = `task-priority ${task.priority}`;
            priority.textContent = `${task.priority} priority`;
            content.appendChild(priority);
        }
        head.append(icon, content);

        const due = document.createElement("time");
        due.textContent = taskDueLabel(task);
        const actions = document.createElement("div");
        actions.className = "notification-item-actions";
        const complete = document.createElement("button");
        complete.type = "button";
        complete.className = "task-complete-btn";
        complete.textContent = "Complete";
        complete.addEventListener("click", () => runTaskAction(task, "complete", complete));
        const tomorrow = document.createElement("button");
        tomorrow.type = "button";
        tomorrow.textContent = "Tomorrow";
        tomorrow.addEventListener("click", () => runTaskAction(task, "tomorrow", tomorrow));
        actions.append(complete, tomorrow);

        item.append(head, due, actions);
        taskNotificationList.appendChild(item);
    }
    updateNotificationCount();
    updateNotificationIndicator();
}

async function runTaskAction(task, action, button){
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = action === "complete" ? "Completing…" : "Moving…";
    try{
        const response = await fetch(
            `/api/tasks/${encodeURIComponent(task.id)}/${action}`,
            {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({user_id:USER_ID, conversation_id:conversationId})
            }
        );
        if(!response.ok) throw new Error("task action failed");
        const result = await response.json();
        if(!["completed", "updated"].includes(result.status)) throw new Error("task not found");
        if(result.suggestion) addFollowUpSuggestion(result.suggestion);
        notificationTasks.delete(task.id);
        knownTaskIds.delete(task.id);
        renderTaskNotifications();
        showNotice(
            action === "complete" ? `Completed: ${task.title}` : `Moved to tomorrow: ${task.title}`,
            action === "complete" ? "✓" : "📅"
        );
        loadTaskOverview();
    }catch(_err){
        button.disabled = false;
        button.textContent = originalText;
        showNotice("Could not update task. Please try again.", "⚠️", 4500);
    }
}

async function pollTasks(){
    // Continue polling in background tabs so due tasks can still be heard.
    if(taskPolling) return;
    taskPolling = true;
    try{
        const response = await fetch(
            `/api/tasks/notifications?user_id=${encodeURIComponent(USER_ID)}`
        );
        if(!response.ok) return;
        const data = await response.json();
        const tasks = data.tasks || [];
        const currentIds = new Set(tasks.map(task => task.id));
        for(const taskId of notificationTasks.keys()){
            if(!currentIds.has(taskId)) notificationTasks.delete(taskId);
        }
        const newlyDue = [];
        for(const task of tasks){
            notificationTasks.set(task.id, task);
            if(!knownTaskIds.has(task.id)){
                knownTaskIds.add(task.id);
                newlyDue.push(task);
            }
        }
        renderTaskNotifications();
        if(newlyDue.length > 0){
            playNotificationSound("task");
        }
        if(newlyDue.length === 1){
            showNotice(`Task due: ${newlyDue[0].title}`, "✓", 4500);
        }else if(newlyDue.length > 1){
            showNotice(`${newlyDue.length} tasks are due`, "✓", 4500);
        }
    }catch(_err){
        // PostgreSQL keeps tasks durable; the next poll retries.
    }finally{
        taskPolling = false;
    }
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
    let newlyDueCount = 0;
    for(const reminder of reminders){
        if(knownReminderIds.has(reminder.id)) continue;
        knownReminderIds.add(reminder.id);
        reminderQueue.push(reminder);
        newlyDueCount += 1;
    }
    if(newlyDueCount > 0){
        playNotificationSound("reminder");
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
                body: JSON.stringify({user_id: USER_ID, conversation_id: conversationId})
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
    // Continue polling in background tabs so due reminders can still be heard.
    if(reminderPolling) return;
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
    const open = !notificationPanel.classList.contains("hidden");
    notifBtn.setAttribute("aria-expanded", String(open));
    settingsPanel.classList.add("hidden");
    settingsBtn.setAttribute("aria-expanded", "false");
    tasksPanel.classList.add("hidden");
    tasksBtn.setAttribute("aria-expanded", "false");
    gmailPanel.classList.add("hidden");
    gmailBtn.setAttribute("aria-expanded", "false");
});

gmailBtn.addEventListener("click", () => {
    gmailPanel.classList.toggle("hidden");
    const open = !gmailPanel.classList.contains("hidden");
    gmailBtn.setAttribute("aria-expanded", String(open));
    tasksPanel.classList.add("hidden");
    tasksBtn.setAttribute("aria-expanded", "false");
    notificationPanel.classList.add("hidden");
    notifBtn.setAttribute("aria-expanded", "false");
    settingsPanel.classList.add("hidden");
    settingsBtn.setAttribute("aria-expanded", "false");
    if(open) loadGmailPanel();
});

tasksBtn.addEventListener("click", () => {
    tasksPanel.classList.toggle("hidden");
    const open = !tasksPanel.classList.contains("hidden");
    tasksBtn.setAttribute("aria-expanded", String(open));
    notificationPanel.classList.add("hidden");
    notifBtn.setAttribute("aria-expanded", "false");
    settingsPanel.classList.add("hidden");
    settingsBtn.setAttribute("aria-expanded", "false");
    gmailPanel.classList.add("hidden");
    gmailBtn.setAttribute("aria-expanded", "false");
    if(open) loadTaskOverview();
});

settingsBtn.addEventListener("click", () => {
    settingsPanel.classList.toggle("hidden");
    const open = !settingsPanel.classList.contains("hidden");
    settingsBtn.setAttribute("aria-expanded", String(open));
    notificationPanel.classList.add("hidden");
    notifBtn.setAttribute("aria-expanded", "false");
    tasksPanel.classList.add("hidden");
    tasksBtn.setAttribute("aria-expanded", "false");
    gmailPanel.classList.add("hidden");
    gmailBtn.setAttribute("aria-expanded", "false");
});

// Any icon-controlled aside behaves like a dismissible popover. Keeping this
// relationship driven by aria-controls also covers future panels (for example
// Notes) without adding another document-level handler.
const floatingPanelBindings = Array.from(document.querySelectorAll("[aria-controls]"))
    .map(trigger => ({
        trigger,
        panel: document.getElementById(trigger.getAttribute("aria-controls"))
    }))
    .filter(binding => binding.panel?.matches("aside"));

document.addEventListener("pointerdown", event => {
    for(const {trigger, panel} of floatingPanelBindings){
        if(panel.classList.contains("hidden")) continue;
        if(panel.contains(event.target) || trigger.contains(event.target)) continue;
        panel.classList.add("hidden");
        trigger.setAttribute("aria-expanded", "false");
    }
});

document.addEventListener("keydown", event => {
    if(event.key !== "Escape") return;
    closeGmailReader();
    settingsPanel.classList.add("hidden");
    notificationPanel.classList.add("hidden");
    tasksPanel.classList.add("hidden");
    gmailPanel.classList.add("hidden");
    settingsBtn.setAttribute("aria-expanded", "false");
    notifBtn.setAttribute("aria-expanded", "false");
    tasksBtn.setAttribute("aria-expanded", "false");
    gmailBtn.setAttribute("aria-expanded", "false");
});

renderNotificationPanel();
renderTaskNotifications();
renderTaskOverview();

initializeWelcome();
setInterval(loadUserProfile, 5 * 60 * 1000);
pollReminders();
setInterval(pollReminders, 5000);
pollTasks();
setInterval(pollTasks, 7000);
loadTaskOverview();
setInterval(loadTaskOverview, 30000);
loadGmailPanel();
setInterval(loadGmailPanel, 30000);
setInterval(() => pollExpenseImports(true), 60 * 1000);
document.addEventListener("visibilitychange", () => {
    if(!document.hidden){
        pollReminders();
        pollTasks();
        pollExpenseImports(true);
    }
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
