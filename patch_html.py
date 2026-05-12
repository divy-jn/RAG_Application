ids = ['appScreen', 'authError', 'authScreen', 'chatInput', 'chatMessages', 'chatWelcome', 'docGrid', 'docSubject', 'docTopic', 'docType', 'docsEmpty', 'fileInput', 'forgotPasswordForm', 'fpBtn', 'fpEmail', 'fpUsername', 'loginBtn', 'loginForm', 'loginPassword', 'loginUsername', 'modelSelect', 'regBtn', 'regEmail', 'regName', 'regPassword', 'regUsername', 'registerForm', 'resetPasswordForm', 'rpBtn', 'rpConfirmPassword', 'rpNewPassword', 'selectedFileName', 'sendBtn', 'sidebarAvatar', 'sidebarList', 'sidebarUserName', 'statusIndicator', 'statusText', 'stopBtn', 'toasts', 'uploadForm', 'uploadZone', 'userAvatar', 'userName']

html = open('static/index.html', 'r', encoding='utf-8').read()

dummy_script = f"""
<script>
// Dummy elements to prevent JS errors
const requiredIds = {ids};
requiredIds.forEach(id => {{
    if (!document.getElementById(id)) {{
        const el = document.createElement('div');
        el.id = id;
        el.style.display = 'none';
        document.body.appendChild(el);
    }}
}});
</script>
<script src="app.js"></script>
"""

html = html.replace('<script src="app.js"></script>', dummy_script)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Dummy elements added")
