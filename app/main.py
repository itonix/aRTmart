import os
from pwdlib import PasswordHash
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from fastapi import HTTPException
from dotenv import load_dotenv 
load_dotenv()
from .database import engine, SessionLocal, Base
from . import models
# for image processing
from PIL import Image
import io
#--------------#
#redis----------#
from .redis_client import redis_client
import json
#--------------#

import uuid

password_hash = PasswordHash.recommended()

####botos3###
from .database import get_db
import boto3
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from . import models

############




# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")


# -------------------------
# Database session dependency
# -------------------------


# -------------------------
# Home page
# -------------------------
# @app.get("/", response_class=HTMLResponse)
# def read_home(request: Request, db: Session = Depends(get_db)):
#     artworks = db.query(models.Artwork).all()
#     return templates.TemplateResponse(
#         "index.html",
#         {"request": request, "artworks": artworks}
#     )
@app.get("/", response_class=HTMLResponse)
def read_home(request: Request, db=Depends(get_db)):
    cache_key = "homepage_artworks"

    # 1️⃣ Try to get cached data from Redis
    cached = redis_client.get(cache_key)
    if cached:
        artworks = json.loads(cached)
        print("Cache hit!")  # debug
    else:
        # 2️⃣ Cache miss → query database
        db_artworks = db.query(models.Artwork).all()
        artworks = [
            {
                "id": art.id,
                "title": art.title,
                "artist_name": art.artist_name,
                "price": float(art.price),
                "thumbnail_url": art.thumbnail_url
            }
            for art in db_artworks
        ]
        # 3️⃣ Save to Redis with 10-minute TTL
        redis_client.setex(cache_key, 600, json.dumps(artworks))
        print("Cache miss! Loaded from DB.")  # debug

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "artworks": artworks}
    )
# -------------------------
# Login page
# -------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )




# -------------------------
# Register page
# -------------------------
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )

# password_hash = PasswordHash.recommended()


# -------------------------
# Register form submission
# -------------------------
@app.post("/register")
def register_user(
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if email already exists
    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if existing_user:
        return {"error": "Email already registered"}
    if role not in ["buyer", "seller"]:
        return {"error": "Invalid role selected"}

    # Hash password using Argon2
    hashed_password = password_hash.hash(password)

    # Store user
    new_user = models.User(
        username=username,
        email=email,
        password=hashed_password,
        role=role
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/login", status_code=303)


# -------------------------
# Login
# -------------------------
@app.post("/login")
def login_user(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find user
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        return {"error": "Invalid credentials"}

    # Verify password using Argon2
    if not password_hash.verify(password, user.password):
        return {"error": "Invalid credentials"}

    # Success
    response = RedirectResponse(url="/dashboard", status_code=303)

    # Store identity in cookie
    response.set_cookie(
        key="user_id",
        value=str(user.id),
        httponly=True
    )

    return response
# -------------------------#
# User dashboard (placeholder)
# -------------------------#
# -------------------------
# Dashboard page
# -------------------------
@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db), uploaded: int = 0):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()

    if user.role == "seller":
        # Show artworks uploaded by this seller
        artworks = db.query(models.Artwork).filter(models.Artwork.user_id == user.id).all()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "artworks": artworks,
                "message": "Artwork uploaded successfully!" if uploaded else None,
                "is_seller": True
            }
        )
    else:
        # Buyer sees all available artworks
        artworks = db.query(models.Artwork).all()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "artworks": artworks,
                "is_seller": False
            }
        )
# -------------------------
# Upload artwork (placeholder)
# -------------------------
# -------------------------
# Upload page (GET)
# -------------------------
@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "user": user}
    )
# -------------------------#
# Upload artwork to S3
# -------------------------#

s3 = boto3.client(
    "s3",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
BUCKET_NAME = "artworkbuck"
# -------------------------
# Upload artwork (POST)
# -------------------------


@app.post("/upload", response_class=HTMLResponse)
def upload_artwork(
    request: Request,
    title: str = Form(...),
    price: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter(
        models.User.id == int(user_id)
    ).first()

    if not user:
        return RedirectResponse("/login", status_code=303)

    # read file into memory
    contents = file.file.read()

    # open image
    image = Image.open(io.BytesIO(contents))

    # generate unique filename
    ext = file.filename.split(".")[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{ext}"

    # original image key
    original_key = f"user_arts/user_{user.id}/{unique_filename}"

    # thumbnail key
    thumb_key = f"thumb_arts/user_{user.id}/{unique_filename}"

    # upload original image
    s3.upload_fileobj(
        io.BytesIO(contents),
        BUCKET_NAME,
        original_key
    )

    # create thumbnail (max 300x300)
    thumbnail = image.copy()
    thumbnail.thumbnail((300, 300))

    thumb_buffer = io.BytesIO()
    thumbnail.save(thumb_buffer, format=image.format)
    thumb_buffer.seek(0)

    # upload thumbnail
    s3.upload_fileobj(
        thumb_buffer,
        BUCKET_NAME,
        thumb_key
    )

    # URLs
    origin_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{original_key}"
    thumb_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{thumb_key}"

    # save in DB
    new_artwork = models.Artwork(
        title=title,
        artist_name=user.username,
        price=price,
        original_url=origin_url,
        thumbnail_url=thumb_url,   # add this column
        user_id=user.id
    )

    db.add(new_artwork)
    db.commit()
    redis_client.delete("homepage_artworks")

    return RedirectResponse("/dashboard?uploaded=1", status_code=303)



# -------------------------
# Downloads page (placeholder)
# -------------------------
@app.get("/downloads", response_class=HTMLResponse)
def downloads_page(request: Request):
    return templates.TemplateResponse(
        "downloads.html",
        {"request": request}
    )


# -------------------------
# Users list page (placeholder)
# -------------------------
@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users}
    )

# -------------------------
#logout
# -------------------------
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("user_id")
    return response




###----------------------#
@app.get("/art/{artwork_id}", response_class=HTMLResponse)
def view_artwork(artwork_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")

    # Fetch artwork
    artwork = db.query(models.Artwork).filter(models.Artwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    # Fetch user if logged in
    user = None
    if user_id:
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()

    return templates.TemplateResponse(
        "art_detail.html",
        {
            "request": request,
            "artwork": artwork,
            "user": user  # used in template to enable "Add to Cart"
        }
    )



@app.post("/cart/add/{artwork_id}")
def add_to_cart(artwork_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    artwork = db.query(models.Artwork).filter(models.Artwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    # Check if already in cart
    existing = db.query(models.Cart).filter_by(user_id=user.id, artwork_id=artwork.id).first()
    if existing:
        return {"message": "Artwork already in cart"}

    cart_item = models.Cart(user_id=user.id, artwork_id=artwork.id)
    db.add(cart_item)
    db.commit()

    return RedirectResponse("/cart", status_code=303)






@app.get("/cart", response_class=HTMLResponse)
def view_cart(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Get all cart items for this user
    cart_items = db.query(models.Cart).filter(models.Cart.user_id == user.id).all()

    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "user": user,
            "cart_items": cart_items
        }
    )




@app.post("/cart/remove/{cart_id}")
def remove_from_cart(cart_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    cart_item = db.query(models.Cart).filter(
        models.Cart.id == cart_id,
        models.Cart.user_id == int(user_id)
    ).first()

    if cart_item:
        db.delete(cart_item)
        db.commit()

    return RedirectResponse("/cart", status_code=303)




@app.post("/checkout")
def checkout(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    cart_items = db.query(models.Cart).filter(models.Cart.user_id == user.id).all()
    if not cart_items:
        return RedirectResponse("/cart", status_code=303)

    total_amount = sum(item.artwork.price for item in cart_items)

    try:
        # 1️⃣ Generate unique payment reference
        payment_ref = str(uuid.uuid4())

        # 2️⃣ Create Payment record
        payment = models.Payment(
            user_id=user.id,
            amount=total_amount,
            status="completed",  # simulate success
            payment_provider="internal_demo",
            payment_reference=payment_ref
        )
        db.add(payment)
        db.flush()  # get payment.id

        # 3️⃣ Create Purchase records
        for item in cart_items:
            purchase = models.Purchase(
                buyer_id=user.id,
                artwork_id=item.artwork.id,
                payment_id=payment.id,
                price=item.artwork.price
            )
            db.add(purchase)

        # 4️⃣ Clear Cart
        for item in cart_items:
            db.delete(item)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Checkout failed: {e}")

    # 5️⃣ Redirect to success page with payment reference
    return RedirectResponse(f"/checkout/success/{payment_ref}", status_code=303)


@app.get("/checkout/success/{payment_ref}", response_class=HTMLResponse)
def checkout_success(payment_ref: str, request: Request, db: Session = Depends(get_db)):
    payment = db.query(models.Payment).filter(
        models.Payment.payment_reference == payment_ref
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    purchases = db.query(models.Purchase).filter(
        models.Purchase.payment_id == payment.id
    ).all()

    return templates.TemplateResponse(
        "invoice.html",
        {
            "request": request,
            "payment": payment,
            "purchases": purchases,
            "invoice_id": payment_ref
        }
    )
