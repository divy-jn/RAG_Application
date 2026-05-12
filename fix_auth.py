from bs4 import BeautifulSoup
import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

login_form = soup.find('form', id='loginForm')

if login_form and not soup.find('form', id='registerForm'):
    # Clone login form to make register form
    import copy
    register_form = copy.copy(login_form)
    register_form['id'] = 'registerForm'
    register_form['onsubmit'] = 'handleRegister(event)'
    register_form['style'] = 'display:none;'

    # Update title
    welcome_text = soup.find('h2', string=re.compile('Welcome Back'))
    if welcome_text:
        reg_title = copy.copy(welcome_text)
        reg_title.string = 'Create Account'
        reg_title['id'] = 'regTitle'
        reg_title['style'] = 'display:none;'
        welcome_text.insert_after(reg_title)

    # Convert email input to Name input
    name_div = copy.copy(register_form.find('div', class_='flex flex-col gap-2'))
    name_label = name_div.find('label')
    if name_label: name_label.string = 'Full Name'
    name_input = name_div.find('input')
    if name_input:
        name_input['id'] = 'regName'
        name_input['type'] = 'text'
        name_input['placeholder'] = 'Alex Chen'

    # Convert another to Username input
    user_div = copy.copy(name_div)
    user_label = user_div.find('label')
    if user_label: user_label.string = 'Username'
    user_input = user_div.find('input')
    if user_input:
        user_input['id'] = 'regUsername'
        user_input['placeholder'] = 'alexchen'

    # Fix email input
    email_div = register_form.find('div', class_='flex flex-col gap-2')
    email_input = email_div.find('input')
    if email_input:
        email_input['id'] = 'regEmail'

    # Fix password input
    pass_div = register_form.find_all('div', class_='flex flex-col gap-2')[1]
    pass_input = pass_div.find('input')
    if pass_input:
        pass_input['id'] = 'regPassword'

    # Update button
    btn = register_form.find('button', id='loginBtn')
    if btn:
        btn['id'] = 'regBtn'
        btn.string = 'Create Account'
        
    # Remove 'Remember me' from register form
    remember_div = register_form.find('div', class_='flex items-center gap-3 px-1 mt-1')
    if remember_div:
        remember_div.decompose()

    # Prepend name and username to register form
    register_form.insert(0, user_div)
    register_form.insert(0, name_div)

    # Insert register form
    login_form.insert_after(register_form)

    # Update "Sign Up" link
    signup_link = soup.find('a', string=re.compile('Sign Up'))
    if signup_link:
        signup_link['onclick'] = 'event.preventDefault(); toggleAuthUI();'

    # Add toggleAuthUI to JS to handle custom titles
    script_tag = soup.find('script', src='/static/app.js')
    if script_tag:
        custom_js = soup.new_tag('script')
        custom_js.string = '''
        function toggleAuthUI() {
            toggleAuth(); // Call original function
            const isLogin = document.getElementById('loginForm').style.display !== 'none';
            const welcome = document.querySelector('h2.font-headline-sm');
            const regTitle = document.getElementById('regTitle');
            if (isLogin) {
                welcome.style.display = 'block';
                if(regTitle) regTitle.style.display = 'none';
            } else {
                welcome.style.display = 'none';
                if(regTitle) regTitle.style.display = 'block';
            }
        }
        '''
        script_tag.insert_before(custom_js)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(str(soup))
print("Auth fixed.")
