from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file, flash
import requests
import sqlite3
import pandas as pd
import io
import os
from config import BOT_TOKEN, CHAT_ID, GROUP_CHAT_ID, CHANNEL_CHAT_ID, EXCEL_FILE, ADMIN_WEB_PASSWORD, MODERATOR_WEB_PASSWORD, DB_PATH

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Замените на надёжное значение

# Декоратор для проверки авторизации с возможной проверкой роли
def login_required(role=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if "role" not in session:
                return redirect(url_for('login'))
            if role and session.get("role") != role:
                flash("Недостаточно прав доступа.", "danger")
                return redirect(url_for('dashboard'))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get("role")
        password = request.form.get("password")
        if role == "admin":
            if password == ADMIN_WEB_PASSWORD:
                session["role"] = "admin"
                return redirect(url_for('dashboard'))
            else:
                flash("Неверный пароль для администратора.", "danger")
        elif role == "moderator":
            if password == MODERATOR_WEB_PASSWORD:
                session["role"] = "moderator"
                return redirect(url_for('dashboard'))
            else:
                flash("Неверный пароль для модератора.", "danger")
        else:
            flash("Пожалуйста, выберите роль.", "danger")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required()
def dashboard():
    return render_template("dashboard.html", role=session.get("role"))

@app.route('/publish', methods=['GET', 'POST'])
@login_required()
def publish():
    if request.method == 'POST':
        news_text = request.form.get('news_text')
        image_file = request.files.get('image_file')
        if not news_text and (not image_file or image_file.filename == ""):
            flash("Новость не может быть пустой.", 'danger')
            return redirect(url_for('dashboard'))
        if image_file and image_file.filename != "":
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                'chat_id': CHAT_ID,
                'caption': f"📢 Новость:\n\n{news_text}" if news_text else ""
            }
            files = {'photo': image_file.stream}
            r = requests.post(url, data=data, files=files)
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': CHAT_ID,
                'text': f"📢 Новость:\n\n{news_text}"
            }
            r = requests.post(url, data=data)
        if r.ok:
            flash("Новость успешно опубликована!", 'success')
        else:
            flash("Ошибка при публикации новости.", 'danger')
        return redirect(url_for('dashboard'))
    return render_template("publish.html")

@app.route('/publish_group', methods=['GET', 'POST'])
@login_required()
def publish_group():
    if request.method == 'POST':
        news_text = request.form.get('news_text')
        image_file = request.files.get('image_file')
        if not news_text and (not image_file or image_file.filename == ""):
            flash("Новость не может быть пустой.", 'danger')
            return redirect(url_for('dashboard'))
        if image_file and image_file.filename != "":
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                'chat_id': GROUP_CHAT_ID,
                'caption': f"📢 Новость:\n\n{news_text}" if news_text else ""
            }
            files = {'photo': image_file.stream}
            r = requests.post(url, data=data, files=files)
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': GROUP_CHAT_ID,
                'text': f"📢 Новость:\n\n{news_text}"
            }
            r = requests.post(url, data=data)
        if r.ok:
            flash("Новость успешно опубликована в группе!", 'success')
        else:
            flash("Ошибка при публикации новости в группе.", 'danger')
        return redirect(url_for('dashboard'))
    return render_template("publish_group.html")

@app.route('/publish_channel', methods=['GET', 'POST'])
@login_required()
def publish_channel():
    if request.method == 'POST':
        news_text = request.form.get('news_text')
        image_file = request.files.get('image_file')
        if not news_text and (not image_file or image_file.filename == ""):
            flash("Новость не может быть пустой.", 'danger')
            return redirect(url_for('dashboard'))
        if image_file and image_file.filename != "":
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                'chat_id': CHANNEL_CHAT_ID,
                'caption': f"📢 Новость:\n\n{news_text}" if news_text else ""
            }
            files = {'photo': image_file.stream}
            r = requests.post(url, data=data, files=files)
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': CHANNEL_CHAT_ID,
                'text': f"📢 Новость:\n\n{news_text}"
            }
            r = requests.post(url, data=data)
        if r.ok:
            flash("Новость успешно опубликована в канале!", 'success')
        else:
            flash("Ошибка при публикации новости в канале.", 'danger')
        return redirect(url_for('dashboard'))
    return render_template("publish_channel.html")

@app.route('/notify', methods=['GET', 'POST'])
@login_required()
def notify():
    if request.method == 'POST':
        notify_text = request.form.get('notify_text')
        if notify_text:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM authorized_users")
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                user_id = row[0]
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                data = {
                    'chat_id': user_id,
                    'text': f"🔔 Уведомление:\n\n{notify_text}"
                }
                requests.post(url, data=data)
            flash("Уведомление отправлено всем пользователям!", 'success')
        return redirect(url_for('dashboard'))
    return render_template("notify.html")

@app.route('/schedule', methods=['GET', 'POST'])
@login_required()
def schedule():
    if request.method == 'POST':
        schedule_text = request.form.get('schedule_text')
        if schedule_text:
            lines = schedule_text.splitlines()
            entries = []
            month_year_set = set()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ':' not in line:
                    flash(f"Неверный формат строки: {line}", 'danger')
                    return redirect(url_for('schedule'))
                fio_part, date_part = line.split(':', 1)
                fio = fio_part.strip()
                date_str = date_part.strip()
                try:
                    date_obj = pd.to_datetime(date_str, format='%d-%m-%Y')
                    month_year = date_obj.strftime("%m-%Y")
                    month_year_set.add(month_year)
                    entries.append((fio, date_str))
                except Exception:
                    flash(f"Неверный формат даты: {date_str}", 'danger')
                    return redirect(url_for('schedule'))
            if len(month_year_set) != 1:
                flash("Все даты должны принадлежать одному месяцу и году.", 'danger')
                return redirect(url_for('schedule'))
            target_month_year = month_year_set.pop()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM coffee_schedule WHERE date LIKE ?", (f"%-{target_month_year}",))
            for fio, date_str in entries:
                cursor.execute("INSERT INTO coffee_schedule (fio, date) VALUES (?, ?)", (fio, date_str))
            conn.commit()
            conn.close()
            flash("График на месяц успешно обновлен.", 'success')
            return redirect(url_for('dashboard'))
    return render_template("schedule.html")



@app.route('/download_schedule')
@login_required()
def download_schedule():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM coffee_schedule", conn)
        conn.close()
        if df.empty:
            flash("В базе данных нет записей графика кофемашины.", 'warning')
            return redirect(url_for('dashboard'))
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Schedule')
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='coffee_schedule.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f"Ошибка при скачивании графика кофе: {e}", 'danger')
        return redirect(url_for('dashboard'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls'}

@app.route('/download_contacts')
@login_required()
def download_contacts():
    try:
        abs_path = os.path.abspath(EXCEL_FILE)
        if not os.path.exists(abs_path):
            flash(f"Файл контактов не найден: {abs_path}", 'danger')
            return redirect(url_for('dashboard'))
        directory = os.path.dirname(abs_path)
        filename = os.path.basename(abs_path)
        return send_from_directory(directory, filename, as_attachment=True, download_name='contacts.xlsx')
    except Exception as e:
        flash(f"Ошибка при скачивании файла контактов: {e}", 'danger')
        return redirect(url_for('dashboard'))

@app.route('/edit_contacts', methods=['GET', 'POST'])
@login_required()
def edit_contacts():
    if request.method == 'POST':
        if 'contacts_file' not in request.files:
            flash("Файл не найден в запросе.", 'danger')
            return redirect(url_for('edit_contacts'))
        file = request.files['contacts_file']
        if file.filename == '':
            flash("Файл не выбран.", 'danger')
            return redirect(url_for('edit_contacts'))
        if file and allowed_file(file.filename):
            try:
                file.save(EXCEL_FILE)
                flash("Файл контактов успешно обновлен.", 'success')
            except Exception as e:
                flash(f"Ошибка при сохранении файла: {e}", 'danger')
            return redirect(url_for('dashboard'))
        else:
            flash("Неподдерживаемый формат файла. Допустимые расширения: .xlsx, .xls", 'danger')
            return redirect(url_for('edit_contacts'))
    return render_template("edit_contacts.html")


# Маршрут управления авторизованными пользователями (только для администратора)
@app.route('/admin_users', methods=['GET'])
@login_required("admin")
def admin_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, fio, position, role FROM authorized_users")
    users = cursor.fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)

# Маршрут редактирования данных авторизованного пользователя (ФИО и должность)
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required("admin")
def edit_user(user_id):
    if request.method == 'POST':
        fio = request.form.get('fio')
        position = request.form.get('position')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE authorized_users SET fio = ?, position = ? WHERE user_id = ?", (fio, position, user_id))
        conn.commit()
        conn.close()
        flash("Пользователь обновлён.", "success")
        return redirect(url_for('admin_users'))
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT fio, position FROM authorized_users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            fio, position = user
        else:
            flash("Пользователь не найден.", "danger")
            return redirect(url_for('admin_users'))
        return render_template("admin_edit_user.html", user_id=user_id, fio=fio, position=position)



# Новый маршрут для удаления пользователей

@app.route('/delete_user/<int:user_id>', methods=['GET'])
@login_required("admin")
def delete_user(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        flash("Пользователь успешно удалён.", "success")
    except Exception as e:
        flash(f"Ошибка при удалении пользователя: {e}", "danger")
    return redirect(url_for('admin_users'))

# Новый маршрут для просмотра пользователей канала (для модератора)
@app.route('/channel_users', methods=['GET'])
@login_required()
def channel_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, fio FROM channel_subscribers")
    users = cursor.fetchall()
    conn.close()
    return render_template("channel_users.html", users=users)

# Маршрут для удаления пользователей канала

@app.route('/delete_channel_user/<int:user_id>', methods=['GET'])
@login_required()
def delete_channel_user(user_id):
    # Разрешаем выполнение только для модераторов и администраторов
    if session.get("role") not in ["admin", "moderator"]:
        flash("Недостаточно прав для выполнения данного действия.", "danger")
        return redirect(url_for('channel_users'))
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channel_subscribers WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        flash("Пользователь успешно удалён из базы подписчиков.", "success")
    except Exception as e:
        flash(f"Ошибка при удалении пользователя: {e}", "danger")
    return redirect(url_for('channel_users'))

#Маршрут для назначения модератора бота

@app.route('/assign_role/<int:user_id>/<string:role>', methods=['GET'])
@login_required("admin")
def assign_role(user_id, role):
    try:
        # Проверяем, что роль валидна
        valid_roles = ['user', 'moderator', 'admin', 'marketer']
        if role not in valid_roles:
            flash(f"Неверная роль: {role}. Допустимые роли: {', '.join(valid_roles)}", "danger")
            return redirect(url_for('admin_users'))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем, что пользователь существует
        cursor.execute("SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,))
        user_exists = cursor.fetchone()
        
        if not user_exists:
            flash(f"Пользователь с ID {user_id} не найден", "danger")
            conn.close()
            return redirect(url_for('admin_users'))
        
        # Обновляем роль
        cursor.execute("UPDATE authorized_users SET role = ? WHERE user_id = ?", (role, user_id))
        conn.commit()
        conn.close()
        
        flash(f"Роль пользователя {user_id} успешно изменена на {role}.", "success")
    except Exception as e:
        flash(f"Ошибка при назначении роли пользователю: {e}", "danger")
    return redirect(url_for('admin_users'))

# Маршрут для остановки Flask сервера
@app.route('/shutdown')
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_flask()
