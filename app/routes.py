import uuid
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .extensions import db
from .models import Admin, MenuItem, Order, OrderItem, Restaurant, Review, User
from .services.payments import (
    create_razorpay_order,
    razorpay_configured,
    verify_razorpay_signature,
)
from .services.recommendations import (
    build_diet_recommendation,
    haversine_distance,
    history_based_recommendations,
    is_popular_item,
    menu_item_tags,
)

main_bp = Blueprint("main", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped_view


def current_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def admin_logged_in():
    return session.get("admin_id") is not None


def current_admin():
    admin_id = session.get("admin_id")
    return Admin.query.get(admin_id) if admin_id else None


def get_cart():
    return session.setdefault("cart", {})


def cart_context():
    cart = get_cart()
    entries = []
    total = 0
    count = 0
    if not cart:
        return {"entries": entries, "total": total, "count": count}

    menu_items = MenuItem.query.filter(MenuItem.id.in_(list(map(int, cart.keys())))).all()
    menu_map = {item.id: item for item in menu_items}

    for item_id, quantity in cart.items():
        menu_item = menu_map.get(int(item_id))
        if not menu_item:
            continue
        subtotal = menu_item.price * quantity
        total += subtotal
        count += quantity
        entries.append({"menu_item": menu_item, "quantity": quantity, "subtotal": subtotal})

    return {"entries": entries, "total": total, "count": count}


@main_bp.app_context_processor
def inject_globals():
    return {
        "nav_user": current_user(),
        "cart_meta": cart_context(),
        "admin_logged_in": admin_logged_in(),
        "nav_admin": current_admin(),
        "menu_item_tags": menu_item_tags,
        "is_popular_item": is_popular_item,
    }


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not admin_logged_in():
            flash("Please log in as admin to continue.", "warning")
            return redirect(url_for("main.admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


@main_bp.route("/")
def index():
    restaurants = Restaurant.query.order_by(Restaurant.rating.desc()).all()
    recommendations = (
        history_based_recommendations(session["user_id"])
        if "user_id" in session
        else MenuItem.query.filter_by(healthy_badge=True).limit(6).all()
    )
    return render_template("index.html", restaurants=restaurants, recommendations=recommendations)


@main_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("main.signup"))

        user = User(
            name=request.form["name"].strip(),
            email=email,
            phone=request.form["phone"].strip(),
            location=request.form["location"].strip(),
        )
        user.set_password(request.form["password"])
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Welcome aboard. Your account is ready.", "success")
        return redirect(url_for("main.index"))

    return render_template("signup.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(request.form["password"]):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("main.login"))

        session["user_id"] = user.id
        flash("Welcome back.", "success")
        return redirect(url_for("main.index"))

    return render_template("login.html")


@main_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        admin = Admin.query.filter_by(email=email).first()
        if not admin and email == current_app.config["ADMIN_EMAIL"].strip().lower():
            seeded_admin = Admin(
                name="Platform Admin",
                email=current_app.config["ADMIN_EMAIL"].strip().lower(),
            )
            seeded_admin.set_password(current_app.config["ADMIN_PASSWORD"])
            db.session.add(seeded_admin)
            db.session.commit()
            admin = seeded_admin

        if admin and admin.check_password(password):
            session["admin_id"] = admin.id
            flash("Admin access granted.", "success")
            return redirect(url_for("main.admin_dashboard"))

        flash("Invalid admin credentials.", "danger")
        return redirect(url_for("main.admin_login"))

    return render_template("admin_login.html")


@main_bp.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if Admin.query.filter_by(email=email).first():
            flash("An admin account with that email already exists.", "danger")
            return redirect(url_for("main.admin_register"))

        admin = Admin(name=request.form["name"].strip(), email=email)
        admin.set_password(request.form["password"])
        db.session.add(admin)
        db.session.commit()
        session["admin_id"] = admin.id
        flash("Admin account created successfully.", "success")
        return redirect(url_for("main.admin_dashboard"))

    return render_template("admin_register.html")


@main_bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    flash("Admin session closed.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    restaurants = Restaurant.query.order_by(Restaurant.name.asc()).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    total_menu_items = MenuItem.query.count()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(10).all()
    order_summaries = []
    for order in recent_orders:
        grouped_restaurants = {}
        for order_item in order.order_items:
            restaurant = order_item.menu_item.restaurant
            summary = grouped_restaurants.setdefault(
                restaurant.id,
                {
                    "restaurant": restaurant,
                    "item_names": [],
                    "quantity": 0,
                },
            )
            summary["item_names"].append(order_item.menu_item.name)
            summary["quantity"] += order_item.quantity
        order_summaries.append({"order": order, "restaurants": list(grouped_restaurants.values())})

    return render_template(
        "admin_dashboard.html",
        restaurants=restaurants,
        recent_orders=recent_orders,
        order_summaries=order_summaries,
        total_menu_items=total_menu_items,
        recent_reviews=recent_reviews,
    )


@main_bp.route("/admin/restaurants/new", methods=["POST"])
@admin_required
def admin_create_restaurant():
    restaurant = Restaurant(
        name=request.form["name"].strip(),
        city=request.form["city"].strip(),
        area=request.form["area"].strip(),
        lat=float(request.form["lat"]),
        lng=float(request.form["lng"]),
        rating=float(request.form["rating"]),
        category=request.form["category"].strip(),
        cuisine=request.form["cuisine"].strip(),
        image_url=request.form["image_url"].strip(),
        delivery_time=int(request.form["delivery_time"]),
        description=request.form["description"].strip(),
    )
    db.session.add(restaurant)
    db.session.commit()
    flash("Restaurant added successfully.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.route("/admin/menu/new", methods=["POST"])
@admin_required
def admin_create_menu_item():
    item = MenuItem(
        restaurant_id=int(request.form["restaurant_id"]),
        name=request.form["name"].strip(),
        description=request.form["description"].strip(),
        price=float(request.form["price"]),
        image_url=request.form["image_url"].strip(),
        category=request.form["category"].strip(),
        food_type=request.form["food_type"].strip(),
        calories=int(request.form["calories"]) if request.form.get("calories") else None,
        healthy_badge=bool(request.form.get("healthy_badge")),
    )
    db.session.add(item)
    db.session.commit()
    flash("Menu item added successfully.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.route("/restaurants/<int:restaurant_id>")
def restaurant_detail(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    related = MenuItem.query.filter_by(restaurant_id=restaurant.id).all()
    reviews = (
        Review.query.filter_by(restaurant_id=restaurant.id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )
    recommended_items = sorted(
        related,
        key=lambda item: (
            "Popular 🔥" not in menu_item_tags(item),
            "Healthy 🥗" not in menu_item_tags(item),
            item.price,
        ),
    )[:4]
    return render_template(
        "restaurant_detail.html",
        restaurant=restaurant,
        menu_items=related,
        reviews=reviews,
        recommended_items=recommended_items,
    )


@main_bp.route("/restaurants/<int:restaurant_id>/reviews", methods=["POST"])
@login_required
def add_review(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    menu_item_id = request.form.get("menu_item_id", type=int)
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()

    if rating is None or rating < 1 or rating > 5 or not comment:
        flash("Please submit a rating between 1 and 5 and write a review comment.", "danger")
        return redirect(url_for("main.restaurant_detail", restaurant_id=restaurant.id))

    review = Review(
        user_id=session["user_id"],
        restaurant_id=restaurant.id,
        menu_item_id=menu_item_id if menu_item_id else None,
        rating=rating,
        comment=comment,
    )
    db.session.add(review)
    db.session.commit()
    flash("Thanks for sharing your review.", "success")
    return redirect(url_for("main.restaurant_detail", restaurant_id=restaurant.id))


@main_bp.route("/cart")
def cart():
    return render_template("cart.html", cart_data=cart_context())


@main_bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    payload = request.get_json(silent=True) or {}
    item_id = request.form.get("item_id") or payload.get("item_id")
    quantity = int(request.form.get("quantity", 1) or payload.get("quantity", 1))
    MenuItem.query.get_or_404(item_id)
    cart = get_cart()
    cart[str(item_id)] = cart.get(str(item_id), 0) + quantity
    session.modified = True

    if request.is_json:
        meta = cart_context()
        return jsonify({"ok": True, "count": meta["count"], "total": meta["total"]})

    flash("Item added to cart.", "success")
    return redirect(request.referrer or url_for("main.cart"))


@main_bp.route("/cart/update", methods=["POST"])
def update_cart():
    payload = request.get_json(silent=True) or {}
    item_id = str(request.form.get("item_id") or payload.get("item_id"))
    quantity = int(request.form.get("quantity") or payload.get("quantity", 1))
    cart = get_cart()
    if quantity <= 0:
        cart.pop(item_id, None)
    else:
        cart[item_id] = quantity
    session.modified = True

    if request.is_json:
        meta = cart_context()
        return jsonify({"ok": True, "count": meta["count"], "total": meta["total"]})

    return redirect(url_for("main.cart"))


@main_bp.route("/restaurants/data")
def restaurants_data():
    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", type=float, default=10)
    search = request.args.get("search", "").strip().lower()
    food_type = request.args.get("food_type", "").strip().lower()
    healthy = request.args.get("healthy", "").strip().lower() == "true"
    min_rating = request.args.get("rating", type=float, default=0)

    restaurants = Restaurant.query.all()
    payload = []
    for restaurant in restaurants:
        if search and search not in restaurant.name.lower() and search not in restaurant.city.lower():
            continue
        if food_type and restaurant.category != food_type:
            continue
        if restaurant.rating < min_rating:
            continue
        if healthy and restaurant.category not in {"diet", "veg"}:
            continue

        distance = None
        if user_lat is not None and user_lng is not None:
            distance = haversine_distance(user_lat, user_lng, restaurant.lat, restaurant.lng)
            if radius and distance > radius:
                continue

        payload.append(
            {
                "id": restaurant.id,
                "name": restaurant.name,
                "city": restaurant.city,
                "area": restaurant.area,
                "rating": restaurant.rating,
                "category": restaurant.category,
                "cuisine": restaurant.cuisine,
                "image_url": restaurant.image_url,
                "distance": round(distance, 1) if distance is not None else None,
                "lat": restaurant.lat,
                "lng": restaurant.lng,
                "delivery_time": restaurant.delivery_time,
                "description": restaurant.description,
                "popular": restaurant.rating >= 4.6,
            }
        )

    payload.sort(key=lambda item: (item["distance"] is None, item["distance"] or 9999, -item["rating"]))
    return jsonify(payload)


@main_bp.route("/diet", methods=["GET", "POST"])
def diet():
    goal = request.values.get("goal", "balanced_diet")
    result = build_diet_recommendation(goal)
    return render_template("diet.html", result=result, selected_goal=goal)


def create_local_order(meta, payment_status="pending", status="Awaiting Payment"):
    order = Order(
        user_id=session["user_id"],
        total_amount=meta["total"],
        payment_status=payment_status,
        status=status,
    )
    db.session.add(order)
    db.session.flush()
    for item in meta["entries"]:
        db.session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=item["menu_item"].id,
                quantity=item["quantity"],
                price=item["menu_item"].price,
            )
        )
    db.session.commit()
    return order


@main_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    meta = cart_context()
    if meta["count"] == 0:
        flash("Add items to your cart before checkout.", "warning")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        order = create_local_order(meta, payment_status="paid", status="Preparing")
        order.payment_reference = f"DEMO-{uuid.uuid4().hex[:10].upper()}"
        db.session.commit()
        session["cart"] = {}
        flash("Demo payment completed successfully.", "success")
        return redirect(url_for("main.order_confirmation", order_id=order.id))

    return render_template(
        "checkout.html",
        cart_data=meta,
        razorpay_enabled=razorpay_configured(),
        razorpay_key_id=current_app.config["RAZORPAY_KEY_ID"],
    )


@main_bp.route("/payments/razorpay/order", methods=["POST"])
@login_required
def create_razorpay_checkout_order():
    meta = cart_context()
    if meta["count"] == 0:
        return jsonify({"ok": False, "message": "Cart is empty."}), 400
    if not razorpay_configured():
        return jsonify({"ok": False, "message": "Razorpay is not configured."}), 400

    try:
        order = create_local_order(meta)
        gateway_order = create_razorpay_order(order)
        order.payment_reference = gateway_order["id"]
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Unable to initialize Razorpay order."}), 502

    return jsonify(
        {
            "ok": True,
            "internal_order_id": order.id,
            "razorpay_order_id": gateway_order["id"],
            "amount": gateway_order["amount"],
            "currency": gateway_order["currency"],
            "key": current_app.config["RAZORPAY_KEY_ID"],
            "name": "FoodSprint",
            "description": "Telangana smart food ordering",
            "prefill": {
                "name": current_user().name,
                "email": current_user().email,
                "contact": current_user().phone,
            },
        }
    )


@main_bp.route("/payments/razorpay/verify", methods=["POST"])
@login_required
def verify_razorpay_payment():
    payload = request.get_json(silent=True) or {}
    order = Order.query.get_or_404(payload.get("internal_order_id"))
    if order.user_id != session["user_id"]:
        return jsonify({"ok": False, "message": "Unauthorized order access."}), 403

    signature_ok = verify_razorpay_signature(
        payload.get("razorpay_order_id", ""),
        payload.get("razorpay_payment_id", ""),
        payload.get("razorpay_signature", ""),
    )
    if not signature_ok:
        order.payment_status = "failed"
        order.status = "Payment Failed"
        db.session.commit()
        return jsonify({"ok": False, "message": "Signature verification failed."}), 400

    order.payment_status = "paid"
    order.status = "Preparing"
    order.payment_reference = payload.get("razorpay_payment_id")
    db.session.commit()
    session["cart"] = {}
    return jsonify(
        {"ok": True, "redirect_url": url_for("main.order_confirmation", order_id=order.id)}
    )


@main_bp.route("/payment/failure")
@login_required
def payment_failure():
    order = None
    order_id = request.args.get("order_id", type=int)
    if order_id:
        order = Order.query.get(order_id)
        if order:
            order.payment_status = "failed"
            order.status = "Payment Failed"
            db.session.commit()
    return render_template("payment_failure.html", order=order)


@main_bp.route("/orders/<int:order_id>/confirmation")
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != session["user_id"]:
        flash("That order is not available for your account.", "danger")
        return redirect(url_for("main.index"))
    recommendations = history_based_recommendations(session["user_id"])
    return render_template(
        "order_confirmation.html", order=order, recommendations=recommendations
    )
