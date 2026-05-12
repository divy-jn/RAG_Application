import re
s = open('static/app.js', 'r', encoding='utf-8').read()
ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", s))
print(sorted(list(ids)))
