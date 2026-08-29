from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, nullable=False, index=True)
    name     = Column(String, nullable=False)
    password = Column(String, nullable=False)  # hashed

    trips = relationship("Trip", back_populates="owner")


class Trip(Base):
    __tablename__ = "trips"

    id                = Column(Integer, primary_key=True, index=True)
    destination       = Column(String, nullable=False)
    days              = Column(Integer, nullable=False)
    budget            = Column(Float, nullable=False)
    daily_budget      = Column(Float, nullable=False)
    category          = Column(String, nullable=False)
    ai_recommendation = Column(Text, nullable=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="trips")
