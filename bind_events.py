from bs4 import BeautifulSoup

with open('static/index.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

login_form = soup.find('form', id='loginForm')
if login_form:
    login_form['onsubmit'] = "handleLogin(event)"

chat_input = soup.find('textarea', id='chatInput')
if chat_input:
    chat_input['onkeydown'] = "handleChatKeydown(event)"

send_btn = soup.find('button', id='sendBtn')
if send_btn:
    send_btn['onclick'] = "sendMessage()"

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(str(soup))
print("Events bound.")
