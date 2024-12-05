from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def superusuario_requerido(func):
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session or session.get('usuario_correo') != 'superusuario@gmail.com':
            flash('Acceso denegado: Permiso exclusivo del superusuario.')
            return redirect(url_for('catalogo'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def conectar_bd():
    conn = sqlite3.connect('db.sqlite')
    return conn

def login_requerido(func):
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('registro'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/', methods=['GET'])
@login_requerido
def catalogo():
    busqueda = request.args.get('busqueda', '')
    conn = conectar_bd()
    cursor = conn.cursor()
    if busqueda:
        cursor.execute("SELECT * FROM zapatillas WHERE nombre LIKE ?", ('%' + busqueda + '%',))
    else:
        cursor.execute("SELECT * FROM zapatillas")
    productos = cursor.fetchall()
    conn.close()
    return render_template('catalogo.html', productos=productos)

@app.before_request
def iniciar_carrito():
    if 'carrito' not in session:
        session['carrito'] = []

# Ruta para agregar un producto al carrito
@app.route('/agregar_al_carrito/<int:producto_id>')
def agregar_al_carrito(producto_id):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, precio FROM zapatillas WHERE id = ?", (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    
    if producto:
        item = {
            'id': producto[0],
            'nombre': producto[1],
            'precio': producto[2],
            'cantidad': 1
        }

        # Verifica si el producto ya está en el carrito
        for prod in session['carrito']:
            if prod['id'] == producto_id:
                prod['cantidad'] += 1
                break
        else:
            session['carrito'].append(item)

        session.modified = True
        flash('Producto agregado al carrito.')
    else:
        flash('El producto no existe.')
    
    return redirect(url_for('catalogo'))

# Ruta para ver el carrito
@app.route('/carrito')
def carrito():
    total_carrito = sum(item['precio'] * item['cantidad'] for item in session['carrito'])
    return render_template('carrito.html', carrito=session['carrito'], total_carrito=total_carrito)

# Ruta para actualizar la cantidad de un producto en el carrito
@app.route('/actualizar_carrito/<int:producto_id>', methods=['POST'])
def actualizar_carrito(producto_id):
    nueva_cantidad = int(request.form['cantidad'])
    for item in session['carrito']:
        if item['id'] == producto_id:
            item['cantidad'] = nueva_cantidad
            break
    session.modified = True
    return redirect(url_for('carrito'))

# Ruta para eliminar un producto del carrito
@app.route('/eliminar_del_carrito/<int:producto_id>', methods=['POST'])
def eliminar_del_carrito(producto_id):
    session['carrito'] = [item for item in session['carrito'] if item['id'] != producto_id]
    session.modified = True
    flash('Producto eliminado del carrito.')
    return redirect(url_for('carrito'))

# Ruta para procesar el pago
@app.route('/pago')
def pago():
    # Aquí puedes agregar lógica para procesar el pago
    flash('Procesando pago...')
    return render_template('pago.html')

@app.route('/agregar_producto', methods=['GET', 'POST'])
@login_requerido
@superusuario_requerido
def agregar_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = request.form['precio']
        imagen = request.files['imagen']
        if imagen:
            imagen_filename = secure_filename(imagen.filename)
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename))
            imagen_url = f"{app.config['UPLOAD_FOLDER']}/{imagen_filename}"
            conn = conectar_bd()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO zapatillas (nombre, precio, imagen) VALUES (?, ?, ?)", (nombre, precio, imagen_url))
            conn.commit()
            conn.close()
            flash('Producto agregado correctamente')
            return redirect(url_for('catalogo'))
        else:
            flash('Por favor selecciona una imagen para el producto')
    return render_template('agregar_producto.html')

# Función para enviar correos
def enviar_correo(destinatario, asunto, mensaje):
    remitente = "milagrosesterfarias@gmail.com"
    contraseña = "Leoteamo1"  # Reemplazar con la contraseña de aplicación

    # Configurar el mensaje
    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(mensaje, 'plain'))

    try:
        # Conectar al servidor SMTP de Gmail
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remitente, contraseña)
        servidor.send_message(msg)
        servidor.quit()
        print("Correo enviado exitosamente.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

# Ruta de registro con envío de correo
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        contraseña_hash = generate_password_hash(contraseña)
        conn = conectar_bd()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (nombre, correo, contraseña) VALUES (?, ?, ?)", (nombre, correo, contraseña_hash))
            conn.commit()
            usuario_id = cursor.lastrowid
            session['usuario_id'] = usuario_id
            session['usuario_correo'] = correo  # Guarda el correo en la sesión
            conn.close()
            
            # Enviar correo de agradecimiento
            asunto = "Gracias por registrarte con nosotros"
            mensaje = f"Hola {nombre},\n\nGracias por registrarte con nosotros. El registro fue un éxito.\n\nSaludos,\nEl equipo de ventas de zapatillas."
            enviar_correo(correo, asunto, mensaje)

            return redirect(url_for('catalogo'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("El correo ya está registrado, por favor utiliza otro.")
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("SELECT id, contraseña FROM usuarios WHERE correo = ?", (correo,))
        usuario = cursor.fetchone()
        conn.close()
        if usuario and check_password_hash(usuario[1], contraseña):
            session['usuario_id'] = usuario[0]
            session['usuario_correo'] = correo  # Guarda el correo en la sesión
            return redirect(url_for('catalogo'))
        else:
            flash("Correo o contraseña incorrectos.")
    return render_template('login.html')

@app.route('/stock')
@login_requerido
@superusuario_requerido
def stock():
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM zapatillas")
    productos = cursor.fetchall()
    conn.close()
    return render_template('stock.html', productos=productos)

@app.route('/editar_producto/<int:producto_id>', methods=['GET', 'POST'])
@login_requerido
@superusuario_requerido
def editar_producto(producto_id):
    conn = conectar_bd()
    cursor = conn.cursor()
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = request.form['precio']
        imagen = request.files['imagen']
        imagen_url = None
        if imagen:
            imagen_filename = secure_filename(imagen.filename)
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename))
            imagen_url = f"{app.config['UPLOAD_FOLDER']}/{imagen_filename}"
        if imagen_url:
            cursor.execute("UPDATE zapatillas SET nombre = ?, precio = ?, imagen = ? WHERE id = ?", (nombre, precio, imagen_url, producto_id))
        else:
            cursor.execute("UPDATE zapatillas SET nombre = ?, precio = ? WHERE id = ?", (nombre, precio, producto_id))
        conn.commit()
        conn.close()
        return redirect(url_for('stock'))
    cursor.execute("SELECT * FROM zapatillas WHERE id = ?", (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    return render_template('editar_producto.html', producto=producto)

@app.route('/eliminar_producto/<int:producto_id>')
@login_requerido
@superusuario_requerido
def eliminar_producto(producto_id):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM zapatillas WHERE id = ?", (producto_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('stock'))

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    session.pop('usuario_correo', None)  # Limpia el correo de la sesión
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
