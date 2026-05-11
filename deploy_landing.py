import os

project_root = '/opt/businesaios'
landing_dir = os.path.join(project_root, 'frontend', 'landing')

# Создаем папку, если не существует
os.makedirs(landing_dir, exist_ok=True)

# HTML файл лендинга
html_file = os.path.join(landing_dir, 'index.html')
html_content = """
<!-- Вставь сюда HTML-код лендинга из твоего сообщения -->
"""
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

# CSS файл лендинга
css_file = os.path.join(landing_dir, 'style.css')
css_content = """
/* Вставь сюда весь CSS код лендинга */
"""
with open(css_file, 'w', encoding='utf-8') as f:
    f.write(css_content)

# JS файл лендинга
js_file = os.path.join(landing_dir, 'app.js')
js_content = """
// Вставь сюда JS код лендинга
"""
with open(js_file, 'w', encoding='utf-8') as f:
    f.write(js_content)

print(f'Landing добавлен в проект в {landing_dir}')
