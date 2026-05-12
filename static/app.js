
            // ==============================
            // STATE
            // ==============================
            const API = '';
            let token = localStorage.getItem('token');
            let currentUser = null;
            let selectedFile = null;
            let currentConversationId = null;
            let abortController = null;
            let isStreaming = false;
            let userScrolledUp = false;
            let activeDocumentIds = [];

            // ==============================
            // UTILS
            // ==============================
            function toast(msg, type = 'success') {
                const el = document.createElement('div');
                el.className = `toast ${type}`;
                el.textContent = msg;
                document.getElementById('toasts').appendChild(el);
                setTimeout(() => el.remove(), 4000);
            }

            async function api(path, options = {}) {
                const headers = { ...options.headers };
                if (token) headers['Authorization'] = `Bearer ${token}`;
                if (!(options.body instanceof FormData) && options.body) {
                    headers['Content-Type'] = 'application/json';
                }
                const res = await fetch(API + path, { ...options, headers });
                if (res.status === 401) { handleLogout(); throw new Error('Session expired'); }
                return res;
            }

            // ==============================
            // AUTH
            // ==============================
            function toggleAuth() {
                const login = document.getElementById('loginForm');
                const reg = document.getElementById('registerForm');
                document.getElementById('forgotPasswordForm').style.display = 'none';
                document.getElementById('resetPasswordForm').style.display = 'none';
                const loginVisible = login.style.display !== 'none';
                login.style.display = loginVisible ? 'none' : 'flex';
                reg.style.display = loginVisible ? 'flex' : 'none';
                document.getElementById('authError').classList.add('hidden');
            }

            let resetToken = null;

            function showForgotPassword() {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('registerForm').style.display = 'none';
                document.getElementById('resetPasswordForm').style.display = 'none';
                document.getElementById('forgotPasswordForm').style.display = 'flex';
                document.getElementById('authError').classList.add('hidden');
            }

            function showLoginForm() {
                document.getElementById('loginForm').style.display = 'flex';
                document.getElementById('registerForm').style.display = 'none';
                document.getElementById('forgotPasswordForm').style.display = 'none';
                document.getElementById('resetPasswordForm').style.display = 'none';
                document.getElementById('authError').classList.add('hidden');
            }

            async function handleForgotPassword(e) {
                e.preventDefault();
                const username = document.getElementById('fpUsername').value;
                const email = document.getElementById('fpEmail').value;
                const btn = document.getElementById('fpBtn');
                btn.disabled = true;
                btn.textContent = 'Verifying...';

                try {
                    const res = await fetch(API + `/api/auth/forgot-password?username=${encodeURIComponent(username)}&email=${encodeURIComponent(email)}`, {
                        method: 'POST'
                    });
                    const data = await res.json();

                    if (!res.ok) {
                        showAuthError(data.detail || 'Verification failed');
                        return;
                    }

                    resetToken = data.reset_token;
                    document.getElementById('forgotPasswordForm').style.display = 'none';
                    document.getElementById('resetPasswordForm').style.display = 'block';
                    document.getElementById('authError').style.display = 'none';
                    toast('Identity verified! Set your new password.', 'success');
                } catch (err) {
                    showAuthError('Network error. Please try again.');
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Verify Identity';
                }
            }

            async function handleResetPassword(e) {
                e.preventDefault();
                const newPassword = document.getElementById('rpNewPassword').value;
                const confirmPassword = document.getElementById('rpConfirmPassword').value;
                const btn = document.getElementById('rpBtn');

                if (newPassword !== confirmPassword) {
                    showAuthError('Passwords do not match');
                    return;
                }

                btn.disabled = true;
                btn.textContent = 'Resetting...';

                try {
                    const res = await fetch(API + `/api/auth/reset-password?reset_token=${encodeURIComponent(resetToken)}&new_password=${encodeURIComponent(newPassword)}`, {
                        method: 'POST'
                    });
                    const data = await res.json();

                    if (!res.ok) {
                        showAuthError(data.detail || 'Reset failed');
                        return;
                    }

                    toast('Password reset successfully! Please sign in.', 'success');
                    resetToken = null;
                    showLoginForm();
                } catch (err) {
                    showAuthError('Network error. Please try again.');
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Reset Password';
                }
            }

            function showAuthError(msg) {
                const el = document.getElementById('authError');
                el.textContent = msg;
                el.classList.remove('hidden');
            }

            async function handleLogin(e) {
                e.preventDefault();
                const btn = document.getElementById('loginBtn');
                btn.disabled = true;
                btn.innerHTML = '<div class="spinner"></div>';
                try {
                    const form = new URLSearchParams();
                    form.append('username', document.getElementById('loginUsername').value);
                    form.append('password', document.getElementById('loginPassword').value);
                    const res = await fetch(API + '/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: form
                    });
                    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Login failed'); }
                    const data = await res.json();
                    token = data.access_token;
                    localStorage.setItem('token', token);
                    await loadUser();
                    showApp();
                    toast('Welcome back!');
                } catch (err) {
                    showAuthError(err.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Sign In';
                }
            }

            async function handleRegister(e) {
                e.preventDefault();
                const btn = document.getElementById('regBtn');
                btn.disabled = true;
                btn.innerHTML = '<div class="spinner"></div>';
                try {
                    const res = await fetch(API + '/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            full_name: document.getElementById('regName').value,
                            username: document.getElementById('regUsername').value,
                            email: document.getElementById('regEmail').value,
                            password: document.getElementById('regPassword').value
                        })
                    });
                    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Registration failed'); }
                    toast('Account created! Please sign in.');
                    toggleAuth();
                } catch (err) {
                    showAuthError(err.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Create Account';
                }
            }

            async function loadUser() {
                const res = await api('/api/auth/me');
                if (res.ok) {
                    currentUser = await res.json();
                    const name = currentUser.full_name || currentUser.username;
                    const initial = name[0].toUpperCase();
                    document.getElementById('userName').textContent = name;
                    document.getElementById('userAvatar').textContent = initial;
                    document.getElementById('sidebarUserName').textContent = name;
                    document.getElementById('sidebarAvatar').textContent = initial;
                }
            }

            function handleLogout() {
                token = null;
                currentUser = null;
                currentConversationId = null;
                localStorage.removeItem('token');
                document.getElementById('authScreen').style.display = 'flex';
                document.getElementById('appScreen').style.display = 'none';
            }

            function showApp() {
                document.getElementById('authScreen').style.display = 'none';
                document.getElementById('appScreen').style.display = 'flex';
                loadDocuments();
                loadConversations();
                fetchModels();
            }

            async function fetchModels() {
                try {
                    const res = await api('/api/chat/models');
                    if (!res.ok) return;
                    const data = await res.json();
                    const select = document.getElementById('modelSelect');
                    if (select && data.models) {
                        select.innerHTML = data.models.map(m =>
                            `<option value="${m}" ${m === data.active ? 'selected' : ''}>${m}</option>`
                        ).join('');
                    }
                } catch (err) {
                    console.error('Failed to fetch models:', err);
                }
            }

            async function changeModel(e) {
                const model = e.target.value;
                if (!model) return;
                try {
                    const res = await api('/api/chat/model', {
                        method: 'POST',
                        body: JSON.stringify({ model })
                    });
                    if (res.ok) {
                        toast(`Model changed to ${model}`);
                    }
                } catch (err) {
                    toast('Failed to change model', 'error');
                }
            }

            // ==============================
            // TABS
            // ==============================
            function switchTab(tab) {
                document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `panel-${tab}`));
                if (tab === 'documents') loadDocuments();
            }

            // ==============================
            // SIDEBAR — CONVERSATION LIST
            // ==============================
            async function loadConversations() {
                try {
                    const res = await api('/api/chat/conversations');
                    if (!res.ok) return;
                    const data = await res.json();
                    renderSidebar(data.conversations || []);
                } catch (err) {
                    console.error('Load conversations error:', err);
                }
            }

            function renderSidebar(conversations) {
                const list = document.getElementById('sidebarList');
                if (!conversations.length) {
                    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-secondary);font-size:13px;">No conversations yet</div>';
                    return;
                }
                list.innerHTML = conversations.map(c => `
                <div class="sidebar-item ${c.conversation_id == currentConversationId ? 'active' : ''}"
                     onclick="loadConversation(${c.conversation_id})" data-id="${c.conversation_id}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;opacity:0.5">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <span class="title">${escapeHtml(c.title || 'Untitled')}</span>
                    <button class="delete-chat" onclick="event.stopPropagation();deleteConversation(${c.conversation_id})" title="Delete">🗑</button>
                </div>
            `).join('');
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            async function loadConversation(convId) {
                // Summarize title of the old conversation in background
                if (currentConversationId && currentConversationId !== convId) {
                    summarizeTitle(currentConversationId);
                }

                currentConversationId = convId;
                const container = document.getElementById('chatMessages');
                container.innerHTML = '';

                // Highlight active in sidebar
                document.querySelectorAll('.sidebar-item').forEach(el => {
                    el.classList.toggle('active', el.dataset.id == convId);
                });

                // Remove welcome screen
                const welcome = document.getElementById('chatWelcome');
                if (welcome) welcome.remove();

                try {
                    const res = await api(`/api/chat/conversations/${convId}`);
                    if (!res.ok) return;
                    const data = await res.json();

                    data.messages.forEach(msg => {
                        addMessage(msg.content, msg.role, msg.intent);
                    });
                } catch (err) {
                    console.error('Load conversation error:', err);
                }
            }

            function startNewChat() {
                // Summarize title of old conversation
                if (currentConversationId) {
                    summarizeTitle(currentConversationId);
                }

                currentConversationId = null;
                const container = document.getElementById('chatMessages');
                container.innerHTML = `
                <div class="chat-welcome" id="chatWelcome">
                    <h2>How can I help you study?</h2>
                    <p>Upload your notes first, then ask questions, get explanations, or generate practice questions from your material.</p>
                    <div class="quick-actions">
                        <div class="quick-action" onclick="setQuery('Explain the key concepts from my notes')">Explain concepts</div>
                        <div class="quick-action" onclick="setQuery('Generate 5 practice questions from my notes')">Generate questions</div>
                        <div class="quick-action" onclick="setQuery('What is machine learning?')">Ask a doubt</div>
                    </div>
                </div>
            `;

                // Deselect sidebar
                document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
            }

            async function deleteConversation(convId) {
                if (!confirm('Delete this conversation?')) return;
                try {
                    const res = await api(`/api/chat/conversations/${convId}`, { method: 'DELETE' });
                    if (res.ok) {
                        if (currentConversationId == convId) startNewChat();
                        loadConversations();
                        toast('Conversation deleted');
                    }
                } catch (err) { toast(err.message, 'error'); }
            }

            async function summarizeTitle(convId) {
                try {
                    await api(`/api/chat/conversations/${convId}/summarize-title`, { method: 'POST' });
                    loadConversations(); // Refresh sidebar
                } catch (err) {
                    console.log('Title summarization skipped:', err);
                }
            }

            // ==============================
            // CHAT
            // ==============================
            function setQuery(q) {
                document.getElementById('chatInput').value = q;
                document.getElementById('chatInput').focus();
            }

            function handleChatKeydown(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            }

            function addMessage(content, role, intent) {
                const welcome = document.getElementById('chatWelcome');
                if (welcome) welcome.remove();

                const container = document.getElementById('chatMessages');
                const div = document.createElement('div');
                div.className = `message ${role}`;

                let actionsHtml = '';
                if (role === 'user') {
                    actionsHtml = `
                    <div class="msg-actions">
                        <button class="msg-action-btn" onclick="editMessage(this)" title="Edit"></button>
                        <button class="msg-action-btn" onclick="copyMessage(this)" title="Copy"></button>
                    </div>`;
                } else {
                    actionsHtml = `
                    <div class="msg-actions">
                        <button class="msg-action-btn" onclick="copyMessage(this)" title="Copy"></button>
                    </div>`;
                }

                let html = actionsHtml;
                if (role === 'assistant' && intent) {
                    html += `<div class="intent-badge">${intent.replace(/_/g, ' ')}</div>`;
                }
                html += `<div class="message-content">${parseMarkdown(content)}</div>`;
                div.innerHTML = html;

                container.appendChild(div);
                scrollToBottomIfNeeded();
                return div;
            }

            function parseMarkdown(text) {
                if (!text) return '';

                // Protect LaTeX expressions from other replacements
                let mathBlocks = [];
                let mathIdx = 0;

                // Display math $$...$$
                text = text.replace(/\$\$(.*?)\$\$/gs, (_, expr) => {
                    const id = `%%MATH${mathIdx++}%%`;
                    mathBlocks.push({ id, expr: expr.trim(), display: true });
                    return id;
                });

                // Inline math $...$
                text = text.replace(/\$([^$\n]+?)\$/g, (_, expr) => {
                    const id = `%%MATH${mathIdx++}%%`;
                    mathBlocks.push({ id, expr: expr.trim(), display: false });
                    return id;
                });

                // Code blocks ```...```
                text = text.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
                // Inline code
                text = text.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px;font-size:13px;">$1</code>');

                // Block quotes > ...
                text = text.replace(/^> (.*)$/gm, '<blockquote style="border-left:3px solid var(--accent);padding:4px 12px;margin:8px 0;color:var(--text-secondary);">$1</blockquote>');

                // Headings
                text = text.replace(/^### (.*$)/gm, '<h3 style="margin:12px 0 6px;">$1</h3>');
                text = text.replace(/^## (.*$)/gm, '<h2 style="margin:14px 0 8px;">$1</h2>');
                text = text.replace(/^# (.*$)/gm, '<h1 style="margin:16px 0 10px;font-size:1.4em;">$1</h1>');

                // Lists
                text = text.replace(/^- (.*)$/gm, '<li style="margin-left:16px;list-style:disc;">$1</li>');
                text = text.replace(/^\d+\. (.*)$/gm, '<li style="margin-left:16px;list-style:decimal;">$1</li>');

                // Bold & italic
                text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

                // Horizontal rule
                text = text.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0;">');

                // Line breaks
                text = text.replace(/\n/g, '<br>');

                // Restore math expressions
                for (const block of mathBlocks) {
                    try {
                        const rendered = katex.renderToString(block.expr, {
                            displayMode: block.display,
                            throwOnError: false
                        });
                        text = text.replace(block.id, rendered);
                    } catch (e) {
                        text = text.replace(block.id, `<code>${block.expr}</code>`);
                    }
                }

                return text;
            }

            // ==============================
            // MESSAGE ACTIONS
            // ==============================
            function copyMessage(btn) {
                const msgDiv = btn.closest('.message');
                const contentDiv = msgDiv.querySelector('.message-content');
                const text = contentDiv.innerText || contentDiv.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    // Show brief tooltip
                    const original = btn.innerHTML;
                    btn.innerHTML = '';
                    setTimeout(() => btn.innerHTML = original, 1500);
                });
            }

            function editMessage(btn) {
                const msgDiv = btn.closest('.message');
                const contentDiv = msgDiv.querySelector('.message-content');
                const currentText = contentDiv.innerText || contentDiv.textContent;

                const textarea = document.createElement('textarea');
                textarea.value = currentText;
                textarea.style.cssText = 'width:100%;min-height:60px;background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--accent);border-radius:8px;padding:10px;font-family:inherit;font-size:14px;resize:vertical;';

                const actions = document.createElement('div');
                actions.style.cssText = 'display:flex;gap:8px;margin-top:8px;';
                actions.innerHTML = `
                <button class="btn btn-sm btn-primary" style="font-size:12px;padding:4px 12px;">Save & Resend</button>
                <button class="btn btn-sm btn-outline" style="font-size:12px;padding:4px 12px;">Cancel</button>
            `;

                const originalContent = contentDiv.innerHTML;
                contentDiv.innerHTML = '';
                contentDiv.appendChild(textarea);
                contentDiv.appendChild(actions);
                textarea.focus();

                actions.children[0].onclick = () => {
                    const newText = textarea.value.trim();
                    if (!newText) return;
                    contentDiv.innerHTML = parseMarkdown(newText);

                    // Remove all messages after this one and resend
                    const allMsgs = [...document.getElementById('chatMessages').children];
                    const idx = allMsgs.indexOf(msgDiv);
                    for (let i = allMsgs.length - 1; i > idx; i--) {
                        allMsgs[i].remove();
                    }

                    document.getElementById('chatInput').value = newText;
                    sendMessage();
                };

                actions.children[1].onclick = () => {
                    contentDiv.innerHTML = originalContent;
                };
            }

            // ==============================
            // SMART SCROLL
            // ==============================
            function setupScrollDetection() {
                const container = document.getElementById('chatMessages');
                container.addEventListener('scroll', () => {
                    if (isStreaming) {
                        const threshold = 100;
                        const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
                        userScrolledUp = !atBottom;
                    }
                });
            }

            function scrollToBottomIfNeeded() {
                if (userScrolledUp) return;
                const container = document.getElementById('chatMessages');
                container.scrollTop = container.scrollHeight;
            }

            // ==============================
            // STOP STREAMING
            // ==============================
            function stopStreaming() {
                if (abortController) {
                    abortController.abort();
                    abortController = null;
                }
            }

            // ==============================
            // SEND MESSAGE
            // ==============================
            async function sendMessage() {
                const input = document.getElementById('chatInput');
                const query = input.value.trim();
                if (!query) return;

                input.value = '';
                input.style.height = 'auto';

                // Remove old suggestion chips
                document.querySelectorAll('.suggestion-chips').forEach(el => el.remove());

                addMessage(query, 'user');

                const statusIndicator = document.getElementById('statusIndicator');
                const statusText = document.getElementById('statusText');
                const sendBtn = document.getElementById('sendBtn');
                const stopBtn = document.getElementById('stopBtn');

                if (statusIndicator) statusIndicator.style.display = 'flex';
                if (statusText) statusText.textContent = 'Starting...';
                if (sendBtn) sendBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = 'inline-flex';

                const messagesDiv = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message assistant';

                // Add copy action to streaming message
                const actionsHtml = '<div class="msg-actions"><button class="msg-action-btn" onclick="copyMessage(this)" title="Copy"></button></div>';
                messageDiv.innerHTML = actionsHtml;

                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.textContent = '';
                messageDiv.appendChild(contentDiv);
                messagesDiv.appendChild(messageDiv);
                scrollToBottomIfNeeded();

                isStreaming = true;
                userScrolledUp = false;

                try {
                    abortController = new AbortController();
                    const res = await fetch(API + '/api/chat/stream', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                            query: query,
                            conversation_id: currentConversationId,
                            active_document_ids: activeDocumentIds
                        }),
                        signal: abortController.signal
                    });

                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || 'Request failed');
                    }

                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    let fullText = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });

                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                            if (!line.startsWith('data: ')) continue;
                            try {
                                const payload = JSON.parse(line.slice(6));

                                if (payload.type === 'chunk') {
                                    fullText += payload.content;
                                    contentDiv.innerHTML = parseMarkdown(fullText);
                                    scrollToBottomIfNeeded();
                                } else if (payload.type === 'status') {
                                    if (statusText) statusText.textContent = payload.message;
                                } else if (payload.type === 'info') {
                                    if (statusText) statusText.textContent = payload.message;
                                } else if (payload.type === 'suggestions') {
                                    // Render follow-up question chips
                                    if (payload.questions && payload.questions.length > 0) {
                                        const chipsDiv = document.createElement('div');
                                        chipsDiv.className = 'suggestion-chips';
                                        payload.questions.forEach(q => {
                                            const chip = document.createElement('button');
                                            chip.className = 'suggestion-chip';
                                            chip.textContent = q;
                                            chip.onclick = () => {
                                                document.getElementById('chatInput').value = q;
                                                sendMessage();
                                            };
                                            chipsDiv.appendChild(chip);
                                        });
                                        messageDiv.appendChild(chipsDiv);
                                        scrollToBottomIfNeeded();
                                    }
                                } else if (payload.type === 'done') {
                                    if (!currentConversationId && payload.conversation_id) {
                                        currentConversationId = payload.conversation_id;
                                    }
                                    loadConversations();
                                } else if (payload.type === 'error') {
                                    contentDiv.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(payload.message)}</span>`;
                                }
                            } catch (parseErr) {
                                // Incomplete JSON, will be handled in next iteration
                            }
                        }
                    }

                } catch (err) {
                    if (err.name !== 'AbortError') {
                        contentDiv.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(err.message)}</span>`;
                    }
                } finally {
                    isStreaming = false;
                    userScrolledUp = false;
                    if (statusIndicator) statusIndicator.style.display = 'none';
                    if (sendBtn) sendBtn.style.display = 'inline-flex';
                    if (stopBtn) stopBtn.style.display = 'none';
                    abortController = null;
                }
            }

            // ==============================
            // CHAT FILE UPLOAD
            // ==============================
            async function handleChatFileUpload(e) {
                const file = e.target.files[0];
                if (!file) return;

                // Switch to documents tab, select file, and show upload form
                switchTab('documents');

                // Set the file in the documents upload flow
                selectedFile = file;
                document.getElementById('selectedFileName').textContent = `${file.name}`;
                document.getElementById('uploadForm').style.display = 'block';
                document.getElementById('uploadZone').style.display = 'none';

                toast(`File "${file.name}" selected — fill in details and upload.`);
                e.target.value = ''; // Reset
            }

            // ==============================
            // DOCUMENTS
            // ==============================
            function handleFileSelect(e) {
                selectedFile = e.target.files[0];
                if (selectedFile) showUploadForm();
            }

            function handleDrop(e) {
                e.preventDefault();
                e.target.classList.remove('dragover');
                selectedFile = e.dataTransfer.files[0];
                if (selectedFile) showUploadForm();
            }

            function showUploadForm() {
                document.getElementById('selectedFileName').textContent = `${selectedFile.name}`;
                document.getElementById('uploadForm').style.display = 'block';
                document.getElementById('uploadZone').style.display = 'none';
            }

            function toggleUploadForm() {
                const uploadZone = document.getElementById('uploadZone');
                const uploadForm = document.getElementById('uploadForm');

                // If upload form is showing (file already selected), reset to zone
                if (uploadForm.style.display === 'block') {
                    cancelUpload();
                    return;
                }

                // Show upload zone and trigger file picker
                uploadZone.style.display = 'block';
                uploadForm.style.display = 'none';
                document.getElementById('fileInput').click();
            }

            function cancelUpload() {
                selectedFile = null;
                document.getElementById('uploadForm').style.display = 'none';
                document.getElementById('uploadZone').style.display = 'block';
                document.getElementById('fileInput').value = '';
            }

            let isFirstLoad = true;

            function uploadDocument() {
                if (!selectedFile) return;

                const form = new FormData();
                form.append('file', selectedFile);
                form.append('document_type', document.getElementById('docType').value);
                form.append('subject', document.getElementById('docSubject').value || '');
                form.append('topic', document.getElementById('docTopic').value || '');
                form.append('visibility', 'private');

                toast(`Indexing ${selectedFile.name} in background...`, 'success');
                cancelUpload();

                // Do not await, fire and forget to unblock UI
                api('/api/documents/upload', { method: 'POST', body: form })
                    .then(res => {
                        if (!res.ok) throw new Error('Upload failed');
                        return res.json();
                    })
                    .then(data => {
                        toast('Document indexed successfully!', 'success');
                        if (data && data.id) {
                            if (!activeDocumentIds.includes(data.id)) activeDocumentIds.push(data.id);
                        }
                        loadDocuments();
                    })
                    .catch(err => {
                        toast(`Failed to upload document: ${err.message}`, 'error');
                        console.error('Upload Error:', err);
                    });
            }

            function toggleActiveDocument(id, isActive) {
                if (isActive) {
                    if (!activeDocumentIds.includes(id)) activeDocumentIds.push(id);
                } else {
                    activeDocumentIds = activeDocumentIds.filter(docId => docId !== id);
                }
            }

            async function loadDocuments() {
                try {
                    const res = await api('/api/documents/list');
                    if (!res.ok) return;
                    const data = await res.json();
                    const grid = document.getElementById('docGrid');
                    const empty = document.getElementById('docsEmpty');
                    if (!data.documents || data.documents.length === 0) {
                        grid.innerHTML = '';
                        grid.appendChild(empty);
                        empty.style.display = 'block';
                        return;
                    }

                    if (isFirstLoad) {
                        data.documents.forEach(doc => {
                            if (!activeDocumentIds.includes(doc.id)) activeDocumentIds.push(doc.id);
                        });
                        isFirstLoad = false;
                    }

                    empty.style.display = 'none';
                    grid.innerHTML = data.documents.map(doc => `
                    <div class="doc-card">
                        <div class="doc-card-header">
                            <div class="doc-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                    <polyline points="14 2 14 8 20 8"></polyline>
                                </svg>
                            </div>
                            <div class="doc-title-wrapper">
                                <div class="doc-name" title="${doc.original_filename || doc.filename}">${doc.original_filename || doc.filename}</div>
                                <div class="doc-type">${doc.document_type || 'notes'}</div>
                            </div>
                        </div>

                        <div class="doc-stats">
                            <div class="stat-item">
                                <span class="stat-label">Vector Chunks</span>
                                <span class="stat-val">${doc.chunk_count ? doc.chunk_count : '---'}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Payload Size</span>
                                <span class="stat-val">${formatSize(doc.file_size)}</span>
                            </div>
                        </div>

                        <div class="doc-footer" style="padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 10px;">
                            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;" title="Enable as active source">
                                <input type="checkbox" onchange="toggleActiveDocument(${doc.id}, this.checked)" ${activeDocumentIds.includes(doc.id) ? 'checked' : ''}>
                                <span style="font-size:12px; color:var(--text-secondary)">Active</span>
                            </label>
                            <button class="btn btn-sm" style="background:transparent; border:none; color:var(--danger); padding:4px;" onclick="deleteDocument(${doc.id})" title="Delete Source">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                        </div>
                    </div>
                `).join('');
                } catch (err) { console.error('Load docs error:', err); }
            }

            function formatSize(bytes) {
                if (!bytes) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
            }

            async function deleteDocument(id) {
                if (!confirm('Delete this document?')) return;
                try {
                    const res = await api(`/api/documents/${id}`, { method: 'DELETE' });
                    if (res.ok) { toast('Document deleted'); loadDocuments(); }
                } catch (err) { toast(err.message, 'error'); }
            }

            // ==============================
            // AUTO-RESIZE TEXTAREA
            // ==============================
            document.getElementById('chatInput').addEventListener('input', function () {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 140) + 'px';
            });

            // ==============================
            // INIT
            // ==============================
            setupScrollDetection();
            (async function init() {
                if (token) {
                    try {
                        await loadUser();
                        showApp();
                    } catch {
                        handleLogout();
                    }
                }
            })();
        