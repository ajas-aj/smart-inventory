from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector

app = Flask(__name__)

app.secret_key = "smart-inventory-secret-key"


# =========================
# DATABASE CONNECTION
# =========================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smart_inventory"
    )


# =========================
# ADMIN ACCESS
# =========================

def admin_required():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Admin":
        return render_template("access_denied.html"), 403

    return None


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return redirect(url_for("login"))


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, email, password, role, business_id
            FROM users
            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and user["password"] == password:

            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["user"] = user["email"]
            session["role"] = user["role"]
            session["business_id"] = user["business_id"]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password"
        )

    return render_template("login.html")

# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        business_name = request.form["business_name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        if not business_name or not email or not password:
            return render_template(
                "register.html",
                error="All fields are required."
            )

        db = get_db_connection()
        cursor = db.cursor()

        try:

            # Check whether email already exists
            cursor.execute("""
                SELECT id
                FROM users
                WHERE email = %s
            """, (email,))

            existing_user = cursor.fetchone()

            if existing_user:
                cursor.close()
                db.close()

                return render_template(
                    "register.html",
                    error="This email already exists."
                )

            # Create business
            cursor.execute("""
    INSERT INTO businesses (business_name)
    VALUES (%s)
""", (business_name,))
            business_id = cursor.lastrowid

            # Create Admin account
            cursor.execute("""
                INSERT INTO users
                (email, password, role, business_id)
                VALUES (%s, %s, 'Admin', %s)
            """, (
                email,
                password,
                business_id
            ))

            db.commit()

        except mysql.connector.Error as e:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "register.html",
                error=f"Registration failed: {e}"
            )

        cursor.close()
        db.close()

        return redirect(url_for("login"))

    return render_template("register.html")

# =========================
# TEST DATABASE
# =========================

@app.route("/test-db")
def test_db():

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT DATABASE()")

        result = cursor.fetchone()

        cursor.close()
        db.close()

        return f"Database connected successfully: {result[0]}"

    except Exception as e:

        return f"Database connection failed: {e}"


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Total Products
    cursor.execute("""
        SELECT COUNT(*) AS total_products
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
    """, (business_id,))

    total_products = cursor.fetchone()["total_products"]

    # Total Stock
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS total_stock
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
    """, (business_id,))

    total_stock = cursor.fetchone()["total_stock"]

    # Stock Value
    cursor.execute("""
        SELECT COALESCE(SUM(price * quantity), 0) AS total_value
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
    """, (business_id,))

    total_value = cursor.fetchone()["total_value"]

    # Low Stock
    cursor.execute("""
        SELECT COUNT(*) AS low_stock
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        AND quantity > 0
        AND quantity <= minimum_stock
    """, (business_id,))

    low_stock = cursor.fetchone()["low_stock"]

    # Out of Stock
    cursor.execute("""
        SELECT COUNT(*) AS out_of_stock
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        AND quantity = 0
    """, (business_id,))

    out_of_stock = cursor.fetchone()["out_of_stock"]

    # Recent Products
    cursor.execute("""
        SELECT id, name, category, price, quantity, minimum_stock
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        ORDER BY id DESC
        LIMIT 5
    """, (business_id,))

    recent_products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_stock=total_stock,
        total_value=total_value,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        recent_products=recent_products
    )


# =========================
# CATEGORIES
# =========================

@app.route("/categories")
def categories():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, COUNT(*) AS product_count
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        AND category IS NOT NULL
        AND category != ''
        GROUP BY category
        ORDER BY category
    """, (business_id,))

    categories = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "categories.html",
        categories=categories
    )


# =========================
# PRODUCTS
# =========================

@app.route("/products")
def products():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        ORDER BY id DESC
    """, (business_id,))

    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "products.html",
        products=products
    )


# =========================
# SUPPLIERS
# =========================

@app.route("/suppliers")
def suppliers():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT supplier, COUNT(*) AS product_count
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        AND supplier IS NOT NULL
        AND supplier != ''
        GROUP BY supplier
        ORDER BY supplier
    """, (business_id,))

    suppliers = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "suppliers.html",
        suppliers=suppliers
    )


# =========================
# STOCK MANAGEMENT
# =========================

@app.route("/stock-management")
def stock_management():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity, minimum_stock
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        ORDER BY quantity ASC
    """, (business_id,))

    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "stock_management.html",
        products=products
    )


# =========================
# SALES
# =========================

@app.route("/sales")
def sales():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            sales.id,
            products.name AS product_name,
            sales.quantity_sold,
            sales.sale_price,
            (sales.quantity_sold * sales.sale_price) AS total_amount,
            sales.sale_date
        FROM sales
        JOIN products
            ON sales.product_id = products.id
        WHERE products.business_id = %s
        ORDER BY sales.id DESC
    """, (business_id,))

    sales_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "sales.html",
        sales=sales_data
    )


# =========================
# ADD SALE
# =========================

@app.route("/add-sale", methods=["GET", "POST"])
def add_sale():

    if "user_id" not in session:
        return redirect(url_for("login"))

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        product_id = request.form["product_id"]
        quantity_sold = int(request.form["quantity_sold"])
        sale_price = request.form["sale_price"]

        # Check active product
        cursor.execute("""
            SELECT id, quantity
            FROM products
            WHERE id = %s
            AND business_id = %s
            AND status = 'Active'
        """, (product_id, business_id))

        product = cursor.fetchone()

        if product and quantity_sold > 0 and quantity_sold <= product["quantity"]:

            # Insert sale
            cursor.execute("""
                INSERT INTO sales
                (product_id, quantity_sold, sale_price)
                VALUES (%s, %s, %s)
            """, (
                product_id,
                quantity_sold,
                sale_price
            ))

            # Reduce stock
            cursor.execute("""
                UPDATE products
                SET quantity = quantity - %s
                WHERE id = %s
                AND business_id = %s
                AND status = 'Active'
            """, (
                quantity_sold,
                product_id,
                business_id
            ))

            db.commit()

            cursor.close()
            db.close()

            return redirect(url_for("sales"))

    # Only active products with stock
    cursor.execute("""
        SELECT id, name, price, quantity
        FROM products
        WHERE business_id = %s
        AND status = 'Active'
        AND quantity > 0
        ORDER BY name
    """, (business_id,))

    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "add_sale.html",
        products=products
    )


# =========================
# ADD PRODUCT
# =========================

@app.route("/add-product", methods=["GET", "POST"])
def add_product():

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    if request.method == "POST":

        name = request.form["name"]
        category = request.form["category"]
        supplier = request.form["supplier"]
        price = request.form["price"]
        quantity = request.form["quantity"]
        minimum_stock = request.form["minimum_stock"]

        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute("""
                INSERT INTO products
                (
                    name,
                    category,
                    supplier,
                    price,
                    quantity,
                    minimum_stock,
                    business_id,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
            """, (
                name,
                category,
                supplier,
                price,
                quantity,
                minimum_stock,
                business_id
            ))

            db.commit()

        except mysql.connector.Error as e:

            db.rollback()

            cursor.close()
            db.close()

            return f"Failed to add product: {e}"

        cursor.close()
        db.close()

        return redirect(url_for("products"))

    return render_template("add_product.html")


# =========================
# REMOVE PRODUCT
# =========================

@app.route("/delete-product/<int:id>")
def delete_product(id):

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor()

    # Soft remove product
    # This keeps old sales history safe.

    cursor.execute("""
        UPDATE products
        SET status = 'Removed'
        WHERE id = %s
        AND business_id = %s
        AND status = 'Active'
    """, (id, business_id))

    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("products"))


# =========================
# EDIT PRODUCT
# =========================

@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM products
        WHERE id = %s
        AND business_id = %s
        AND status = 'Active'
    """, (id, business_id))

    product = cursor.fetchone()

    if not product:

        cursor.close()
        db.close()

        return "Product not found", 404

    if request.method == "POST":

        name = request.form["name"]
        category = request.form["category"]
        supplier = request.form["supplier"]
        price = request.form["price"]
        quantity = request.form["quantity"]
        minimum_stock = request.form["minimum_stock"]

        cursor.execute("""
            UPDATE products
            SET
                name = %s,
                category = %s,
                supplier = %s,
                price = %s,
                quantity = %s,
                minimum_stock = %s
            WHERE id = %s
            AND business_id = %s
            AND status = 'Active'
        """, (
            name,
            category,
            supplier,
            price,
            quantity,
            minimum_stock,
            id,
            business_id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for("products"))

    cursor.close()
    db.close()

    return render_template(
        "edit_product.html",
        product=product
    )


# =========================
# STAFF MANAGEMENT
# =========================

@app.route("/staff")
def staff():

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, email, role, created_at
        FROM users
        WHERE business_id = %s
        AND role = 'Staff'
        ORDER BY id DESC
    """, (business_id,))

    staff_members = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "staff.html",
        staff_members=staff_members
    )


# =========================
# ADD STAFF
# =========================

@app.route("/add-staff", methods=["GET", "POST"])
def add_staff():

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Check empty fields
        if not email or not password:

            return render_template(
                "add_staff.html",
                error="Email and password are required."
            )

        db = get_db_connection()
        cursor = db.cursor()

        try:

            # Check if email already exists
            cursor.execute("""
                SELECT id
                FROM users
                WHERE email = %s
            """, (email,))

            existing_user = cursor.fetchone()

            if existing_user:

                cursor.close()
                db.close()

                return render_template(
                    "add_staff.html",
                    error="This email already exists."
                )

            # IMPORTANT:
            # There are 3 %s placeholders below,
            # so only 3 Python parameters are supplied.

            cursor.execute("""
                INSERT INTO users
                (email, password, role, business_id)
                VALUES (%s, %s, 'Staff', %s)
            """, (
                email,
                password,
                business_id
            ))

            db.commit()

        except mysql.connector.Error as e:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "add_staff.html",
                error=f"Failed to add staff: {e}"
            )

        cursor.close()
        db.close()

        return redirect(url_for("staff"))

    return render_template("add_staff.html")


# =========================
# REMOVE STAFF
# =========================

@app.route("/remove-staff/<int:id>")
def remove_staff(id):

    access = admin_required()

    if access:
        return access

    business_id = session["business_id"]

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM users
        WHERE id = %s
        AND business_id = %s
        AND role = 'Staff'
    """, (
        id,
        business_id
    ))

    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("staff"))


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    app.run(debug=True)