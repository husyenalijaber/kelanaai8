from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db, engine
from db import models
from services.trip_service import calculate_daily_budget, get_trip_category
from services.bedrock_service import generate_travel_recommendation
from services.auth_service import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="KelanaAI", description="Smart Travel Planner API", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    email:    str
    password: str

class LoginRequest(BaseModel):
    email:    str
    password: str

class TripRequest(BaseModel):
    destination: str
    days:        int
    budget:      float

class TripUpdateRequest(BaseModel):
    budget: float


# ── Auth Endpoints ─────────────────────────────────────────────────────────────
@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        name=payload.name, email=payload.email, password=hash_password(payload.password)
    )
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/api/v1/auth/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {"id": current_user.id, "name": current_user.name, "email": current_user.email}


# ── Basic Endpoints ────────────────────────────────────────────────────────────
@app.get("/")
def root(): return {"message": "Welcome to KelanaAI"}

@app.get("/health")
def health(): return {"status": "OK"}

@app.get("/api/v1/recommendations")
def get_recommendations(): return ["Tokyo Tower", "Mount Fuji", "Shibuya"]

@app.get("/api/v1/transportations")
def get_transportations(): return ["Bus", "Train", "Flight"]


# ── Protected CRUD ─────────────────────────────────────────────────────────────
@app.post("/api/v1/trips", status_code=201)
def create_trip(trip: TripRequest, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    db_trip = models.Trip(
        destination=trip.destination, days=trip.days, budget=trip.budget,
        daily_budget=calculate_daily_budget(trip.budget, trip.days),
        category=get_trip_category(trip.budget), user_id=current_user.id,
    )
    db.add(db_trip); db.commit(); db.refresh(db_trip)
    return db_trip


@app.get("/api/v1/trips")
def get_all_trips(db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    return db.query(models.Trip).filter(models.Trip.user_id == current_user.id).all()


@app.get("/api/v1/trips/{id}")
def get_trip(id: int, db: Session = Depends(get_db),
             current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == id).first()
    if not trip: raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your trip")
    return trip


@app.put("/api/v1/trips/{id}")
def update_trip(id: int, payload: TripUpdateRequest, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == id).first()
    if not trip: raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your trip")
    trip.budget = payload.budget
    trip.daily_budget = calculate_daily_budget(payload.budget, trip.days)
    trip.category = get_trip_category(payload.budget)
    db.commit(); db.refresh(trip)
    return trip


@app.delete("/api/v1/trips/{id}")
def delete_trip(id: int, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == id).first()
    if not trip: raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your trip")
    db.delete(trip); db.commit()
    return {"message": f"Trip with id {id} has been deleted"}


@app.post("/api/v1/trips/{id}/generate")
def generate_recommendation(id: int, db: Session = Depends(get_db),
                             current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == id).first()
    if not trip: raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your trip")
    trip.ai_recommendation = generate_travel_recommendation(
        destination=trip.destination, days=trip.days,
        budget=trip.budget, category=trip.category,
    )
    db.commit(); db.refresh(trip)
    return trip
