document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const chatContainer = document.getElementById('chatContainer');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const sidebar = document.getElementById('sidebar');
    const toggleSidebar = document.getElementById('toggleSidebar');
    const newChatBtn = document.getElementById('newChatBtn');
    const historyList = document.getElementById('historyList');
    const themeSwitch = document.getElementById('themeSwitch');
    const voiceBtn = document.getElementById('voiceBtn');
    const ttsToggle = document.getElementById('ttsToggle');
    const fileUpload = document.getElementById('fileUpload');
    const historySearch = document.getElementById('historySearch');

    // --- State ---
    let currentChatId = null;
    let chats = JSON.parse(localStorage.getItem('ai_chats')) || {};
    let isTtsEnabled = false;
    let recognition = null;

    // --- Initialization ---
    initApp();

    function initApp() {
        renderHistory();
        if (Object.keys(chats).length > 0) {
            const lastId = Object.keys(chats).sort().reverse()[0];
            loadChat(lastId);
        } else {
            startNewChat();
        }

        // Initialize Speech Recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRec();
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                userInput.value = text;
                sendMessage();
            };
        } else {
            voiceBtn.style.display = 'none';
        }
    }

    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    toggleSidebar.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    newChatBtn.addEventListener('click', startNewChat);

    themeSwitch.addEventListener('change', () => {
        document.body.classList.toggle('dark-mode', themeSwitch.checked);
        document.body.classList.toggle('light-mode', !themeSwitch.checked);
    });

    voiceBtn.addEventListener('click', () => {
        if (recognition) recognition.start();
    });

    ttsToggle.addEventListener('click', () => {
        isTtsEnabled = !isTtsEnabled;
        ttsToggle.classList.toggle('active', isTtsEnabled);
        ttsToggle.querySelector('i').className = isTtsEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute';
    });

    fileUpload.addEventListener('change', handleFileUpload);

    document.querySelectorAll('.qa-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            userInput.value = btn.dataset.query;
            sendMessage();
        });
    });

    historySearch.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        document.querySelectorAll('.history-item').forEach(item => {
            item.style.display = item.textContent.toLowerCase().includes(term) ? 'block' : 'none';
        });
    });

    // --- Functions ---

    function startNewChat() {
        currentChatId = Date.now().toString();
        chats[currentChatId] = {
            title: "New Chat",
            messages: []
        };
        saveChats();
        renderHistory();
        clearChatUI();
    }

    function loadChat(id) {
        currentChatId = id;
        clearChatUI(true);
        chats[id].messages.forEach(msg => {
            appendMessage(msg.role, msg.content, msg.source, msg.model, false);
        });
        renderHistory();
    }

    function clearChatUI(isLoad = false) {
        if (!isLoad) {
            chatContainer.innerHTML = `
                <div class="message bot-message welcome">
                    <div class="message-content">
                        <h1>How can I help you today?</h1>
                        <p>I can answer any question about news, sports, coding, math, and more. I never say "I don't know."</p>
                        <div class="quick-actions">
                            <button class="qa-btn" data-query="Latest world news"><i class="fas fa-newspaper"></i> News</button>
                            <button class="qa-btn" data-query="Live sports scores"><i class="fas fa-football-ball"></i> Sports</button>
                            <button class="qa-btn" data-query="Weather in London"><i class="fas fa-cloud-sun"></i> Weather</button>
                            <button class="qa-btn" data-query="Bitcoin price current"><i class="fas fa-chart-line"></i> Stocks</button>
                            <button class="qa-btn" data-query="Explain quantum computing"><i class="fas fa-microchip"></i> Tech</button>
                        </div>
                    </div>
                </div>
            `;
            // Re-attach listeners for new welcome buttons
            document.querySelectorAll('.qa-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    userInput.value = btn.dataset.query;
                    sendMessage();
                });
            });
        } else {
            chatContainer.innerHTML = '';
        }
    }

    async function sendMessage() {
        const query = userInput.value.trim();
        if (!query) return;

        appendMessage('user', query);
        userInput.value = '';
        showTyping(true);

        try {
            const response = await fetch('http://localhost:5000/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, history: chats[currentChatId].messages })
            });

            const data = await response.json();
            showTyping(false);
            
            if (data.answer) {
                appendMessage('bot', data.answer, data.source, data.model, true, data.sources || []);
                if (isTtsEnabled) speak(data.answer);
                
                // Update chat title if first message
                if (chats[currentChatId].messages.length === 2) {
                    chats[currentChatId].title = query.substring(0, 30) + (query.length > 30 ? '...' : '');
                    renderHistory();
                }
            }
        } catch (error) {
            console.error(error);
            showTyping(false);
            appendMessage('bot', "I'm having trouble connecting to my brain right now. Please ensure the backend server is running.");
        }
    }

    function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = async (event) => {
                appendMessage('user', `[Uploaded Image: ${file.name}]`);
                showTyping(true);
                
                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('http://localhost:5000/image', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    showTyping(false);
                    appendMessage('bot', data.answer, data.source, data.model, true, data.sources || []);
                } catch (err) {
                    showTyping(false);
                    appendMessage('bot', "Error processing image.");
                }
            };
            reader.readAsDataURL(file);
        } else {
            // Text files etc - could be handled here
            alert("For now, only images can be analyzed. Text files will be supported soon!");
        }
    }

    function appendMessage(role, content, source = null, model = null, save = true, sources = []) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}-message`;
        
        let html = `
            <div class="message-content">${marked.parse(content)}</div>
        `;

        if (role === 'bot' && sources && sources.length > 0) {
            html += `<div class="sources-grid">`;
            sources.forEach(src => {
                const domain = new URL(src.url).hostname;
                const faviconUrl = `https://www.google.com/s2/favicons?sz=64&domain=${domain}`;
                html += `
                    <a href="${src.url}" target="_blank" class="source-card">
                        <div class="source-header">
                            <img src="${faviconUrl}" alt="" class="source-favicon">
                            <span class="source-title">${src.title}</span>
                        </div>
                        <div class="source-snippet">${src.snippet}</div>
                    </a>
                `;
            });
            html += `</div>`;
        }

        if (role === 'bot') {
            html += `
                <div class="message-meta">
                    <span class="source-badge">${source || 'AI Knowledge'}</span>
                    <span class="model-info">${model || 'Gemini'}</span>
                    <i class="fas fa-copy action-btn" onclick="copyText(this)" title="Copy"></i>
                    <i class="fas fa-redo action-btn" onclick="regenerateLast()" title="Regenerate"></i>
                </div>
            `;
        }

        msgDiv.innerHTML = html;
        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        if (save) {
            chats[currentChatId].messages.push({ role, content, source, model, sources });
            saveChats();
        }
    }

    function showTyping(show) {
        typingIndicator.style.display = show ? 'block' : 'none';
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function renderHistory() {
        historyList.innerHTML = '';
        Object.keys(chats).sort().reverse().forEach(id => {
            const item = document.createElement('div');
            item.className = `history-item ${id === currentChatId ? 'active' : ''}`;
            item.textContent = chats[id].title;
            item.onclick = () => loadChat(id);
            historyList.appendChild(item);
        });
    }

    function saveChats() {
        localStorage.setItem('ai_chats', JSON.stringify(chats));
    }

    function speak(text) {
        const utterance = new SpeechSynthesisUtterance(text);
        window.speechSynthesis.speak(utterance);
    }

    // Global handles for dynamic elements
    window.copyText = (el) => {
        const text = el.closest('.message').querySelector('.message-content').innerText;
        navigator.clipboard.writeText(text);
        el.classList.remove('fa-copy');
        el.classList.add('fa-check');
        setTimeout(() => {
            el.classList.remove('fa-check');
            el.classList.add('fa-copy');
        }, 2000);
    };

    window.regenerateLast = () => {
        if (chats[currentChatId].messages.length < 2) return;
        // Logic: Remove last bot response and re-send last user message
        const lastMsg = chats[currentChatId].messages.pop();
        if (lastMsg.role === 'bot') {
            const userMsg = chats[currentChatId].messages.pop();
            userInput.value = userMsg.content;
            chatContainer.removeChild(chatContainer.lastChild); // bot
            chatContainer.removeChild(chatContainer.lastChild); // user
            sendMessage();
        }
    };

    // --- Particles Initialization ---
    const particleContainer = document.getElementById('particles-js');
    if (particleContainer && window.initParticles) {
        window.initParticles(particleContainer, {
            particleColors: ["#ffffff"],
            particleCount: 200,
            particleSpread: 10,
            speed: 0.1,
            particleBaseSize: 100,
            moveParticlesOnHover: true,
            alphaParticles: false,
            disableRotation: false,
            pixelRatio: 1
        });
    }
});
