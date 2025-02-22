from flask import Flask, render_template, request, session, redirect, flash, url_for, jsonify,send_from_directory
import os
import cv2
import numpy as np
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import MySQLdb.cursors
import razorpay
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
import time
import pandas as pd
import hmac
import hashlib


RAZORPAY_KEY_ID = "rzp_test_thbnstH0BXXXX"
RAZORPAY_KEY_SECRET = "oc86adrgm685ECs3WzdXXXX"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

app = Flask(__name__)


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Messipratham30'
app.config['MYSQL_DB'] = 'clothing_recommendations'

mysql = MySQL(app)

app.secret_key = os.urandom(24)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = ''
app.config['MAIL_PASSWORD'] = ''
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)
s = URLSafeTimedSerializer(app.secret_key)

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Helper function to check if uploaded file has allowed extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_hair(image):
    time.sleep(3)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

    if len(faces) == 0:
        return "Face not detected"

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3]) 

    hair_region = image[y + h : y + h + h//2, x : x + w]  

    hair_gray = cv2.cvtColor(hair_region, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(hair_gray, 50, 150)

    hair_edge_count = np.sum(edges)

    if hair_edge_count > 50000:  
        return "Long Hair"
    else:
        return "Short Hair"
def analyze_face(image):
    time.sleep(3)
    height, width, _ = image.shape
    aspect_ratio = width / height
    if aspect_ratio > 1.2:
        return "Oval Face"
    elif aspect_ratio > 0.9:
        return "Round Face"
    else:
        return "Square Face"

def analyze_body(image):
    time.sleep(3)
    height, width, _ = image.shape
    if height > width * 1.3:
        return "Rectangular Body"
    elif width > height * 1.1:
        return "Pear-Shaped Body"
    else:
        return "Inverted Triangle Body"

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('gender_selection'))
        else:
            flash('Invalid username or password.')

    return render_template('login.html', title="Login", action_url=url_for('login'), button_text="Login", signup=False, show_confirm=False, signup_url=url_for('signup'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match!')
            return redirect(url_for('signup'))

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Username already exists!')
        else:
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, hashed_password))
            mysql.connection.commit()
            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))

    return render_template('login.html', title="Sign Up", action_url=url_for('signup'), button_text="Sign Up", signup=True, show_confirm=True, login_url=url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        
        if user:
            token = s.dumps(email, salt='email-confirm')
            link = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request', sender='noreply@domain.com', recipients=[email])
            msg.body = f"Click the link to reset your password: {link}"
            mail.send(msg)

            flash('An email with password reset instructions has been sent to your email.')
            return redirect(url_for('login'))
        else:
            flash('Email not found.')

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)
    except:
        flash('The reset link is invalid or has expired.')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('reset_password', token=token))
        
        hashed_password = generate_password_hash(password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE users SET password = %s WHERE email = %s', (hashed_password, email))
        mysql.connection.commit()

        flash('Your password has been reset successfully.')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)

@app.route('/auth/google')
def google_login():
    flash('Google login is not implemented yet.')
    return redirect(url_for('login'))


@app.route('/auth/facebook')
def facebook_login():
    flash('Facebook login is not implemented yet.')
    return redirect(url_for('login'))

@app.route('/gender', methods=['GET', 'POST'])
def gender_selection():
    if 'logged_in' not in session or not session['logged_in']:
        flash('Please log in first.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        gender = request.form.get('gender')
        session['gender'] = gender
        return redirect(url_for('home'))
    
    return render_template('gender_selection.html')

@app.route('/recommendations')
def recommendations():
    if 'logged_in' not in session or not session['logged_in']:
        flash('Please log in to access recommendations.')
        return redirect(url_for('login'))

    gender = session.get('gender')
    hair_type = session.get('hair_type')
    face_shape = session.get('face_shape')
    body_shape = session.get('body_shape')

    if not gender:
        flash('Please complete the analysis first.')
        return redirect(url_for('home'))

    sort_option = request.args.get('sort')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    query = "SELECT id, name, price, image, size, material FROM recommended_clothes WHERE gender = %s"
    values = [gender]

    if hair_type:
        query += " AND hair_type = %s"
        values.append(hair_type)

    if face_shape:
        query += " AND face_shape = %s"
        values.append(face_shape)

    if body_shape:
        query += " AND body_shape = %s"
        values.append(body_shape)

    if sort_option == 'price_asc':
        query += " ORDER BY price ASC"
    elif sort_option == 'price_desc':
        query += " ORDER BY price DESC"

    cursor.execute(query, tuple(values))
    recommended_clothes = cursor.fetchall()
    cursor.close()

    return render_template('recommendations.html', clothes=recommended_clothes, sort=sort_option)

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'logged_in' not in session or not session['logged_in']:
        flash('Please log in to access the home page.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No image file uploaded.')
            return render_template('index.html')

        file = request.files['image']
        if file.filename == '':
            flash('No file selected.')
            return render_template('index.html')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            image = cv2.imread(filepath)
            if image is None:
                flash('Error loading image.')
                return render_template('index.html')

            hair_type = analyze_hair(image)
            face_shape = analyze_face(image)
            body_shape = analyze_body(image)

            session['hair_type'] = hair_type
            session['face_shape'] = face_shape
            session['body_shape'] = body_shape

            return render_template('index.html', hair_type=hair_type, face_shape=face_shape, body_shape=body_shape)

    return render_template('index.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/product/<int:product_id>')
def product_page(product_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = "SELECT * FROM recommended_clothes WHERE id = %s"
        cur.execute(query, (product_id,))
        product = cur.fetchone()

        cur.execute("SELECT * FROM recommended_clothes WHERE material = %s AND id != %s LIMIT 4", (product['material'], product_id))
        related_products = cur.fetchall()

        cur.execute("SELECT r.rating, r.review_text, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.product_id = %s", (product_id,))
        reviews = cur.fetchall()
        cur.close()

        if product:
            return render_template('product_page.html', product=product, reviews=reviews, related_products=related_products)
        else:
            flash("Product not found.")
            return redirect(url_for('recommendations'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for('recommendations'))

@app.route('/add_to_wishlist/<int:product_id>', methods=['POST'])
def add_to_wishlist(product_id):
    if 'logged_in' in session:
        user_id = session['user_id']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, product_id))
        mysql.connection.commit()
        cur.close()
        flash('Added to your wishlist!')
    else:
        flash('Please log in to add items to your wishlist.')
    
    return redirect(url_for('product_page', product_id=product_id))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id, name, price, image FROM recommended_clothes WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()

    if product:
        cart_item = {
            'id': product['id'],
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1  
        }

        if 'cart' not in session:
            session['cart'] = []

        for item in session['cart']:
            if item['id'] == product_id:
                item['quantity'] += 1
                break
        else:
            session['cart'].append(cart_item)

        flash(f"{product['name']} has been added to your cart.")
    else:
        flash("Product not found.")

    return redirect(url_for('product_page', product_id=product_id))

@app.route('/update_quantity/<int:product_id>', methods=['POST'])
def update_quantity(product_id):
    action = request.form.get('action')
    
    if 'cart' in session:
        for item in session['cart']:
            if item['id'] == product_id:
                if action == 'increase':
                    item['quantity'] += 1
                elif action == 'decrease' and item['quantity'] > 1:
                    item['quantity'] -= 1

                item['subtotal'] = item['price'] * item['quantity']
                break
    
    # Recalculate the total price
    total = sum(item['price'] * item['quantity'] for item in session['cart'])
    session['total'] = total

    # After updating quantity, redirect to the cart view
    return redirect(url_for('view_cart'))



@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['id'] != product_id]
    
    return redirect(url_for('view_cart'))


@app.route('/checkout')
def checkout_page():
    if 'checkout_item' in session:
        
        items = [session['checkout_item']]
        total = session['checkout_item']['price'] * session['checkout_item']['quantity']

    elif 'cart' in session and session['cart']:
        items = session['cart']
        total = sum(item['price'] * item['quantity'] for item in items) 
    else:
        flash("Your cart is empty.")
        return redirect(url_for('view_cart'))

    return render_template('checkout.html', items=items, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'shipping_address' in session:
        email = session['shipping_address'].get('email')
        name = session['shipping_address'].get('name')
        address = session['shipping_address'].get('address')
        city = session['shipping_address'].get('city')
        pincode = session['shipping_address'].get('pincode')

        if email:
            try:
                msg = Message('Order Confirmation',
                              sender='your-gmail@example.com',
                              recipients=[email])
                msg.body = f"Dear {name},\n\nYour order has been successfully placed.\n\nShipping to: {address}, {city}, {pincode}\n\nThank you for shopping with us!"
                mail.send(msg)
                flash('Confirmation email sent successfully!')
            except Exception as e:
                flash(f"Failed to send confirmation email: {str(e)}")

    flash('Your order has been placed successfully!')
    session.pop('cart', None)
    session.pop('checkout_item', None)

    return redirect(url_for('order_success'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', [])

    total = sum(item['price'] * item['quantity'] for item in cart)

    return render_template('cart.html', cart=cart, total=total)

@app.route('/clear_cart')
def clear_cart():
    try:
        session.pop('cart', None)  # Remove 'cart' from session if it exists
        flash('Cart cleared successfully.')
    except KeyError:
        flash('No cart found to clear.')  # In case 'cart' key doesn't exist
    except Exception as e:
        flash(f"An error occurred: {str(e)}")  # Catch any other exceptions
    return redirect(url_for('view_cart'))

@app.route('/address', methods=['GET'])
def address():
    if 'checkout_item' not in session and 'cart' not in session:
        flash("Please proceed to checkout first.")
        return redirect(url_for('view_cart'))

    return render_template('address.html')

@app.route('/submit_address', methods=['POST'])
def submit_address():
    name = request.form.get('name')
    address = request.form.get('address')
    city = request.form.get('city')
    pincode = request.form.get('pincode')
    phone = request.form.get('phone')
    email = request.form.get('email')  

    session['shipping_address'] = {
        'name': name,
        'address': address,
        'city': city,
        'pincode': pincode,
        'phone': phone,
        'email': email
    }

    return redirect(url_for('payment'))

@app.route('/payment')
def payment():
    if 'shipping_address' not in session:
        flash('Please enter your shipping address first.')
        return redirect(url_for('address'))

    if 'checkout_item' in session:
        cart = [session['checkout_item']] 
        total = session['checkout_item']['price'] * session['checkout_item']['quantity']
    elif 'cart' in session and session['cart']:
        cart = session['cart']
        total = sum(item['price'] * item['quantity'] for item in cart)
    else:
        flash("Your cart is empty.")
        return redirect(url_for('view_cart'))

    return render_template('payment.html', cart=cart, total=total)


@app.route('/buy_now/<int:product_id>', methods=['POST'])
def buy_now(product_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id, name, price, image FROM recommended_clothes WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()

    if product:
        session['checkout_item'] = {
            'id': product['id'],
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1  # Default quantity to 1 for "Buy Now"
        }
        return redirect(url_for('payment')) 
    else:
        flash("Product not found.")
        return redirect(url_for('product_page', product_id=product_id))


@app.route('/process_paypal', methods=['POST'])
def process_paypal():
    if 'cart' in session and 'shipping_address' in session:
        order_details = {
            'payment_method': 'PayPal',
            'cart_items': session['cart'],
            'shipping_address': session['shipping_address']
        }

        session.pop('cart', None)
        
        flash("Payment completed successfully via PayPal.")
        return redirect(url_for('order_success'))
    else:
        flash("There was an error with your order. Please try again.")
        return redirect(url_for('payment'))


@app.route('/process_cod', methods=['POST'])
def process_cod():
    if 'cart' in session and 'shipping_address' in session:

        session.pop('cart', None)
        flash("Order placed successfully with Cash on Delivery.")
        return redirect(url_for('order_success'))
    else:
        flash("There was an error with your order. Please try again.")
        return redirect(url_for('payment'))

@app.route('/order_success')
def order_success():
    return render_template('order_success.html')

def create_order(amount, currency="INR", receipt=None, notes=None):
    try:
        order = razorpay_client.order.create({
            "amount": amount,  # Amount in paise (e.g., 1000 = ₹10)
            "currency": currency,
            "receipt": receipt,
            "notes": notes,
        })
        return order
    except Exception as e:
        return {"error": str(e)}

# Verify Razorpay payment signature
def verify_payment_signature(payment_id, order_id, signature):
    try:
        payload = f"{order_id}|{payment_id}"
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return generated_signature == signature
    except Exception as e:
        return False

# Route to create an order
@app.route('/create_order', methods=['POST'])
def handle_create_order():
    data = request.json
    amount = data.get('amount')
    currency = data.get('currency', 'INR')
    receipt = data.get('receipt')
    notes = data.get('notes')

    if not amount:
        return jsonify({"error": "Amount is required"}), 400

    order = create_order(amount, currency, receipt, notes)
    if "error" in order:
        return jsonify(order), 500

    return jsonify(order), 200

# Route to verify payment and display success page
@app.route('/payment_success', methods=['POST'])
def handle_payment_success():
    data = request.form  # Use form data for HTML form submissions
    payment_id = data.get('razorpay_payment_id')
    order_id = data.get('razorpay_order_id')
    signature = data.get('razorpay_signature')

    if not all([payment_id, order_id, signature]):
        return jsonify({"error": "Missing required fields"}), 400

    is_valid = verify_payment_signature(payment_id, order_id, signature)
    if is_valid:
        # Render the success page
        return render_template('order.success.html', payment_id=payment_id, order_id=order_id)
    else:
        return jsonify({"status": "error", "message": "Invalid signature"}), 400




if __name__ == '__main__':
    app.run(debug=True)

