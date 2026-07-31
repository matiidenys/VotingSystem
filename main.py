from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import json

# Завантажуємо .env
load_dotenv()

app = FastAPI()

# Дозволяємо запити з браузера (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключаємо папку frontend як статичні файли
app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")


# --- ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ ---

def load_abi(filename):
    """Допоміжна функція для читання JSON файлів"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Warning: {filename} not found. Did you run compile.py?")
        return []


# Завантажуємо ABI один раз при старті сервера
FACTORY_ABI = load_abi("VotingFactory.json")
VOTING_ABI = load_abi("Voting.json")
REGISTRY_ABI = load_abi("WhitelistRegistry.json")

# Отримуємо адресу фабрики з .env
FACTORY_ADDRESS = os.getenv("FACTORY_ADDRESS")


# --- API ENDPOINTS ---

@app.get("/config")
async def get_dapp_config():
    """
    Цей ендпоінт викликає фронтенд при завантаженні сторінки.
    """
    if not FACTORY_ADDRESS:
        raise HTTPException(status_code=500, detail="FACTORY_ADDRESS is not set in .env file")

    return {
        "factoryAddress": FACTORY_ADDRESS,
        "factoryABI": FACTORY_ABI,
        "votingABI": VOTING_ABI,
        "registryABI": REGISTRY_ABI
    }


@app.get("/")
async def read_root():
    return {"message": "Voting DApp Backend is running. Go to /static/index.html"}