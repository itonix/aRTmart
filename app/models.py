from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Numeric, ForeignKey, DateTime, func
from .database import Base
from datetime import datetime
from sqlalchemy import Enum




class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    password: Mapped[str] = mapped_column(String, nullable=False)

    role: Mapped[str] = mapped_column(
        Enum("admin", "buyer", "seller", name="user_role"),
        default="buyer",
        nullable=False
    )

    artworks: Mapped[list["Artwork"]] = relationship(back_populates="owner")
    cart_items: Mapped[list["Cart"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="buyer")

class Artwork(Base):
    __tablename__ = "artwork"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    title: Mapped[str] = mapped_column(String, nullable=False)

    artist_name: Mapped[str] = mapped_column(String, nullable=False)

    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    thumbnail_url: Mapped[str] = mapped_column(String, nullable=False)

    original_url: Mapped[str] = mapped_column(String, nullable=False)
    
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))

    owner: Mapped["User"] = relationship(back_populates="artworks")

    cart_items: Mapped[list["Cart"]] = relationship(back_populates="artwork")

    purchases: Mapped[list["Purchase"]] = relationship(back_populates="artwork")




class Cart(Base):
    __tablename__ = "cart"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"), nullable=False)
    artwork_id: Mapped[int] = mapped_column(ForeignKey("artwork.id"), nullable=False)

    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    user: Mapped["User"] = relationship(back_populates="cart_items")
    artwork: Mapped["Artwork"] = relationship(back_populates="cart_items")


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(default="pending")
    payment_provider: Mapped[str] = mapped_column()
    payment_reference: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    user: Mapped["User"] = relationship(back_populates="payments")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="payment")


class Purchase(Base):
    __tablename__ = "purchase"

    id: Mapped[int] = mapped_column(primary_key=True)

    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id")
    )

    artwork_id: Mapped[int] = mapped_column(
        ForeignKey("artwork.id")
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payment.id")
    )

    price: Mapped[float] = mapped_column(Numeric(10,2))

    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # relationships
    buyer: Mapped["User"] = relationship(back_populates="purchases")

    artwork: Mapped["Artwork"] = relationship(back_populates="purchases")

    payment: Mapped["Payment"] = relationship(back_populates="purchases")
