from bs4 import BeautifulSoup
import re

# Read HTML files
with open('stitch_auth.html', 'r', encoding='utf-8') as f:
    auth_soup = BeautifulSoup(f.read(), 'html.parser')

with open('stitch_mobile2.html', 'r', encoding='utf-8') as f:
    app_soup = BeautifulSoup(f.read(), 'html.parser')

# Update Auth Screen
auth_form = auth_soup.find('form')
if auth_form:
    auth_form['id'] = 'loginForm'

email_input = auth_soup.find('input', id='email')
if email_input:
    email_input['id'] = 'loginUsername'
    email_input['name'] = 'loginUsername'

password_input = auth_soup.find('input', id='password')
if password_input:
    password_input['id'] = 'loginPassword'

signin_btn = auth_soup.find('button', type='submit')
if signin_btn:
    signin_btn['id'] = 'loginBtn'

auth_main = auth_soup.find('main')
if auth_main:
    auth_main['id'] = 'authScreen'

# Update App Screen
app_body = app_soup.find('body')
# Wrap the app content in a div#appScreen
app_screen_div = app_soup.new_tag('div', id='appScreen', style='display:none')
for child in list(app_body.children):
    app_screen_div.append(child)
app_body.append(app_screen_div)

# Find chat messages container
# It's the flex container inside main holding the messages
chat_main = app_soup.find('main')
if chat_main:
    chat_container = chat_main.find('div', class_=re.compile('max-w-container-max'))
    if chat_container:
        chat_container['id'] = 'chatMessages'

# Find textarea
textarea = app_soup.find('textarea')
if textarea:
    textarea['id'] = 'chatInput'

# Find send button (button containing 'send' icon)
for btn in app_soup.find_all('button'):
    icon = btn.find('span', text=re.compile(r'send'))
    if icon:
        btn['id'] = 'sendBtn'

# Find user avatar and name
drawer = app_soup.find('div', id='drawer')
if drawer:
    img = drawer.find('img')
    if img:
        img['id'] = 'userAvatar'
    name = drawer.find('h3')
    if name:
        name['id'] = 'userName'
    nav = drawer.find('nav')
    if nav:
        nav['id'] = 'sidebarList'

# Construct final HTML
final_html = f"""<!DOCTYPE html>
<html class="dark" lang="en">
<head>
{app_soup.head.decode_contents()}
<style>
/* Toast notifications */
#toasts {{ position: fixed; top: 1rem; right: 1rem; z-index: 9999; display: flex; flex-direction: column; gap: 0.5rem; }}
.toast {{ padding: 1rem 1.5rem; border-radius: 0.5rem; color: white; opacity: 0; transform: translateY(-10px); transition: all 0.3s ease; }}
.toast.show {{ opacity: 1; transform: translateY(0); }}
.toast-success {{ background: #10b981; }}
.toast-error {{ background: #ef4444; }}
</style>
</head>
<body class="bg-background text-on-background font-body-md min-h-screen flex flex-col selection:bg-primary selection:text-on-primary-container bg-mesh">
    <div id="toasts"></div>
    {auth_main.prettify()}
    {app_screen_div.prettify()}
    
    <script src="app.js"></script>
</body>
</html>"""

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(final_html)

print("index.html successfully built!")
