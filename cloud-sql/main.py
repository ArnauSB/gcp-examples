from flask import Flask, render_template, request, redirect, url_for
import psycopg2

app = Flask(__name__)

# Configura los datos de conexión a tu instancia de Cloud SQL
DB_HOST = '127.0.0.1'
DB_PORT = 5432
DB_USER = 'postgres'
DB_PASSWORD = 'password'
DB_NAME = 'todo'

# Conexión a la base de datos
def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn

# Ruta principal para mostrar todas las tareas
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY id DESC")
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', tasks=tasks)

# Ruta para agregar una nueva tarea
@app.route('/add', methods=['POST'])
def add_task():
    title = request.form['title']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title) VALUES (%s)", (title,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# Ruta para eliminar una tarea
@app.route('/delete/<int:id>')
def delete_task(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
