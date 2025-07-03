from fastapi import FastAPI, HTTPException
from web3 import Web3
import os
from dotenv import load_dotenv
import json
from pydantic import BaseModel # <<< Імпортуємо BaseModel з Pydantic
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

# --- Модель Pydantic для даних розгортання голосування ---
# Ця модель описує структуру JSON, яку ми очікуємо в тілі POST-запиту
class DeployVotingRequest(BaseModel): # <<< Оголошуємо Pydantic модель
    title: str
    options: list[str]
    startTime: int
    endTime: int
    useWhitelist: bool
    votingType: int # Відповідає VotingType enum в Solidity (uint8)
    # TODO: Можливо, додати OrganizerAddress сюди, якщо він не береться з приватного ключа

# --- Модель Pydantic для даних голосування ---
class VoteRequest(BaseModel): # <<< Додано нову модель
    # !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    # У реальному додатку це НЕБЕЗПЕЧНО!
    voter_private_key: str # Приватний ключ виборця (для тестування)
    option_indices: list[int] # Масив індексів обраних варіантів


class AddToWhitelistRequest(BaseModel): # <<< Додано нову модель
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    # У реальному додатку це НЕБЕЗПЕЧНО!
    organizer_private_key: str # Приватний ключ організатора (для тестування)
    voter_address: str       # Адреса виборця, яку потрібно додати

class OrganizerPrivateKeyRequest(BaseModel): # <<< НОВА МОДЕЛЬ
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    organizer_private_key: str # Приватний ключ організатора (для тестування)

class AddManyToWhitelistRequest(BaseModel): # <<< Додайте цю модель
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    organizer_private_key: str # Приватний ключ організатора (для тестування)
    voter_addresses: list[str] # Список адрес виборців, які потрібно додати

# --- Модель Pydantic для видалення з Whitelist (одна адреса) ---
class RemoveFromWhitelistRequest(BaseModel): # <<< Додайте цю модель
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    organizer_private_key: str # Приватний ключ організатора (для тестування)
    voter_address: str       # Адреса виборця, яку потрібно видалити

# --- Модель Pydantic для масового видалення з Whitelist'у ---
class RemoveManyFromWhitelistRequest(BaseModel): # <<< Нова модель для масового видалення
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    organizer_private_key: str # Приватний ключ організатора (для тестування)
    voter_addresses: list[str] # Список адрес виборців, які потрібно видалити

# --- Модель Pydantic для встановлення хешу IPFS ---
class SetIpfsHashRequest(BaseModel): # <<< Нова модель для встановлення хешу IPFS
    # !!! УВАГА: Приватний ключ організатора тут тільки для ТЕСТУВАННЯ на Ganache !!!
    organizer_private_key: str # Приватний ключ організатора (для тестування)
    ipfs_hash: str           # Хеш IPFS файлу Whitelist'у

# Завантажуємо змінні оточення з файлу .env
load_dotenv()

# Ініціалізуємо FastAPI додаток
app = FastAPI()

app.mount("/static", StaticFiles(directory="frontend", html=True), name="static") # <<< Переконайтесь, що цей рядок є

# --- Налаштування підключення до блокчейну ---
GANACHE_RPC_URL = os.getenv("GANACHE_RPC_URL", "http://127.0.0.1:7545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

if not CONTRACT_ADDRESS:
    print("Error: CONTRACT_ADDRESS not found in .env file!")
    # raise ValueError("CONTRACT_ADDRESS not set.")


# Підключаємося до Ethereum-ноди (Ganache)
w3 = Web3(Web3.HTTPProvider(GANACHE_RPC_URL))

# Перевіряємо підключення
if w3.is_connected():
    print(f"Successfully connected to Ethereum node: {GANACHE_RPC_URL}")
    latest_block = w3.eth.block_number
    print(f"Latest block number: {latest_block}")
else:
    print(f"Failed to connect to Ethereum node: {GANACHE_RPC_URL}")
    # TODO: Додати більш надійну обробку помилки підключення


# --- ABI вашого смартконтракту (завантажуємо з файлу) ---
ABI_FILE_PATH = "contract_abi.json" # <<< Назва файлу з ABI
try:
    with open(ABI_FILE_PATH, 'r') as abi_file:
        CONTRACT_ABI = json.load(abi_file) # <<< Завантажуємо ABI з файлу
    print(f"Successfully loaded contract ABI from {ABI_FILE_PATH}")

except FileNotFoundError:
    print(f"Error: ABI file not found at {ABI_FILE_PATH}")
    # TODO: Обробка помилки, якщо файл ABI відсутній
    CONTRACT_ABI = None # Або вийти з додатку

except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from ABI file at {ABI_FILE_PATH}")
    # TODO: Обробка помилки, якщо файл ABI містить некоректний JSON
    CONTRACT_ABI = None

# Перевірка, чи ABI успішно завантажено
if not CONTRACT_ABI:
     print("Error: Contract ABI not loaded. Cannot create contract instance.")
     # raise Exception("Contract ABI not loaded.")


# --- Створюємо об'єкт контракту ---
contract = None # Ініціалізуємо змінну contract
if CONTRACT_ADDRESS and CONTRACT_ABI: # Перевіряємо, чи є адреса та ABI
    try:
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
        print(f"Smart contract instance created for address: {CONTRACT_ADDRESS}")

    except Exception as e:
        print(f"Error creating smart contract instance: {e}")
        # Обробка помилки, якщо адреса неправильна або ABI не відповідає адресі




# --- Ендпоінт для отримання деталей голосування ---
@app.get("/voting_details")
async def get_voting_details():
    """
    Отримує загальну інформацію про голосування зі смартконтракту.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract: # Перевіряємо, чи об'єкт контракту був успішно створений
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Check address and ABI.")


    try:
        # Викликаємо view функцію getVotingDetails() з контракту
        details = contract.functions.getVotingDetails().call()

        # Функція getVotingDetails повертає кортеж. Розпакуємо його в словник для зручності.
        voting_info = {
            "title": details[0],
            "organizer": details[1],
            "startTime": details[2],
            "endTime": details[3],
            "votingType": details[4], # enum повертається як число (0 для SingleChoice, 1 для MultipleChoice)
            "useWhitelist": details[5],
            "isClosed": details[6]
        }

        return voting_info

    except Exception as e:
        # Обробка помилок при взаємодії з контрактом
        print(f"Error calling getVotingDetails: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching voting details: {e}")

# --- Ендпоінт для отримання статусу голосування ---
@app.get("/voting_status")
async def get_voting_status():
    """
    Отримує поточний статус голосування зі смартконтракту.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Check address and ABI.")

    try:
        # Викликаємо view функцію getVotingStatus() з контракту
        # .call() використовується для читання даних
        status = contract.functions.getVotingStatus().call()

        return {"status": status} # Повертаємо статус у словнику

    except Exception as e:
        # Обробка помилок
        print(f"Error calling getVotingStatus: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching voting status: {e}")

# --- Ендпоінт для отримання списку варіантів голосування ---
# --- Ендпоінт для отримання списку варіантів голосування ---
@app.get("/voting_options")
async def get_voting_options():
    """
    Отримує список варіантів голосування зі смартконтракту.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Check address and ABI.")

    try:
        # Викликаємо ЯВНУ view функцію getOptionsList() з контракту
        options_list = contract.functions.getOptionsList().call() # <<< ВИКЛИКАЄМО НОВУ ФУНКЦІЮ

        return {"options": options_list} # Повертаємо список варіантів

    except Exception as e:
        # Обробка помилок
        print(f"Error calling getOptionsList: {e}") # Змінено повідомлення про помилку
        raise HTTPException(status_code=500, detail=f"Error fetching voting options: {e}")

# --- Ендпоінт для отримання результатів голосування ---
@app.get("/voting_results")
async def get_voting_results():
    """
    Отримує результати голосування зі смартконтракту.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Check address and ABI.")

    try:
        # Викликаємо view функцію getResults() з контракту
        # Увага: Ця функція в контракті обмежена за часом/статусом!
        results_list = contract.functions.getResults().call()

        # Результати повертаються як масив uint (кількість голосів за кожен варіант)
        # Можливо, ви захочете скомбінувати їх з варіантами з /voting_options на фронтенді
        return {"results": results_list} # Повертаємо список результатів

    except Exception as e:
        # Обробка помилок при взаємодії з контрактом
        # Якщо контракт відхилить виклик (наприклад, результати ще недоступні),
        # Web3.py кине виняток, і він буде спійманий тут.
        print(f"Error calling getResults: {e}")
        # Можливо, варто перевіряти статус голосування ПЕРЕД викликом getResults
        # або повертати більш специфічну помилку, якщо причина в обмеженні контракту.
        raise HTTPException(status_code=500, detail=f"Error fetching voting results: {e}")


# TODO: Додати інші ендпоінти для взаємодії зі смартконтрактом (створення голосування, голосування, управління Whitelist тощо)

# --- Базовий ендпоінт для перевірки роботи FastAPI ---
@app.get("/")
def read_root():
    return {"message": "Voting Backend is running!"}


# Отримуємо приватний ключ організатора зі змінних оточення
ORGANIZER_PRIVATE_KEY = os.getenv("ORGANIZER_PRIVATE_KEY")

# Перевірка, чи завантажився приватний ключ
if not ORGANIZER_PRIVATE_KEY:
     print("Error: ORGANIZER_PRIVATE_KEY not found in .env file!")
     # TODO: Обробка помилки, якщо ключ відсутній

# Додаємо префікс 0x до приватного ключа, якщо його немає
if ORGANIZER_PRIVATE_KEY and not ORGANIZER_PRIVATE_KEY.startswith("0x"):
    ORGANIZER_PRIVATE_KEY = "0x" + ORGANIZER_PRIVATE_KEY

# --- Байткод вашого смартконтракту ---
# Вставте сюди ВЕСЬ скопійований шістнадцятковий рядок байткоду
# Обов'язково вставте його як рядок

BYTECODE_FILE_PATH = "contract_bytecode.json" # <<< Назва файлу з байткодом
try:
    with open(BYTECODE_FILE_PATH, 'r') as bytecode_file:
        CONTRACT_BYTECODE = json.load(bytecode_file) # <<< Завантажуємо байткод з файлу
    print(f"Successfully loaded contract bytecode from {BYTECODE_FILE_PATH}")

except FileNotFoundError:
    print(f"Error: Bytecode file not found at {BYTECODE_FILE_PATH}")
    CONTRACT_BYTECODE = None # Або обробка помилки

except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from bytecode file at {BYTECODE_FILE_PATH}")
    CONTRACT_BYTECODE = None # Або обробка помилки

# Перевірка, чи байткод успішно завантажено
if not CONTRACT_BYTECODE:
     print("Error: Contract Bytecode not loaded. Cannot deploy contract.")
     # TODO: Обробка помилки, якщо байткод відсутній
# --- Створюємо об'єкт контракту (з ABI та Байткодом) ---
# Об'єкт контракту тепер створюємо тут, використовуючи ABI та Байткод
VotingContract = None
contract = None # Змінна для розгорнутого контракту (ініціалізується пізніше)

if CONTRACT_ABI and CONTRACT_BYTECODE:
    try:
        # Цей об'єкт VotingContract використовується для БУДІВНИЦТВА транзакцій (наприклад, розгортання)
        VotingContract = w3.eth.contract(abi=CONTRACT_ABI, bytecode=CONTRACT_BYTECODE)
        print("VotingContract factory object created (for deployment/transaction building).")

        # Якщо у вас вже є розгорнутий контракт (його адреса в .env),
        # можна створити об'єкт для взаємодії з НИМ
        if CONTRACT_ADDRESS:
             try:
                 contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
                 print(f"Smart contract instance created for address: {CONTRACT_ADDRESS} (for interactions).")
             except Exception as e:
                 print(f"Error creating smart contract instance for address {CONTRACT_ADDRESS}: {e}")

    except Exception as e:
        print(f"Error creating VotingContract factory object: {e}")

# --- Ендпоінт для розгортання нового голосування ---
# Цей ендпоінт буде приймати параметри для конструктора контракту
# --- Ендпоінт для розгортання нового голосування ---
# Тепер ендпоінт приймає один аргумент типу DeployVotingRequest
@app.post("/deploy_voting")
async def deploy_voting(request_data: DeployVotingRequest): # <<< Змінено сигнатуру функції
    """
    Розгортає новий екземпляр смартконтракту Voting.
    Приймає параметри для конструктора контракту в тілі запиту (JSON).
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not ORGANIZER_PRIVATE_KEY:
         raise HTTPException(status_code=500, detail="Organizer private key not configured.")
    if not CONTRACT_ABI or not CONTRACT_BYTECODE:
         raise HTTPException(status_code=500, detail="Contract ABI or Bytecode not loaded.")
    if not VotingContract: # Перевіряємо, чи об'єкт VotingContract успішно створено
         raise HTTPException(status_code=500, detail="Contract factory not available. Check ABI and Bytecode loading.")


    try:
        # 1. Створюємо об'єкт контракту за ABI та Байткодом (VotingContract вже створено при старті)

        # 2. Будуємо транзакцію розгортання
        nonce = w3.eth.get_transaction_count(w3.eth.account.from_key(ORGANIZER_PRIVATE_KEY).address)

        # Аргументи конструктора беремо з об'єкта request_data
        constructor_txn = VotingContract.constructor(
            request_data.title, # <<< Використовуємо дані з моделі
            request_data.options,
            request_data.startTime,
            request_data.endTime,
            request_data.useWhitelist,
            request_data.votingType
        ).build_transaction({
            'from': w3.eth.account.from_key(ORGANIZER_PRIVATE_KEY).address,
            'nonce': nonce,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
        })

        # ... (підписання, надсилання, очікування, повернення адреси залишаються без змін) ...
        signed_txn = w3.eth.account.sign_transaction(constructor_txn, ORGANIZER_PRIVATE_KEY)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            deployed_address = txn_receipt.contractAddress
            print(f"Contract deployed successfully at address: {deployed_address}")
            return {"message": "Contract deployed successfully", "address": deployed_address}
        else:
            print(f"Contract deployment failed. Transaction receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Contract deployment failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error deploying contract: {e}")
        raise HTTPException(status_code=500, detail=f"Error deploying contract: {e}")

# Отримуємо приватний ключ виборця зі змінних оточення (для тестування!)
VOTER_PRIVATE_KEY = os.getenv("VOTER_PRIVATE_KEY")
# TODO: Додати перевірку та префікс 0x для VOTER_PRIVATE_KEY аналогічно ORGANIZER_PRIVATE_KEY

# --- Ендпоінт для надсилання голосу (транзакція) ---
@app.post("/vote")
async def submit_vote(request_data: VoteRequest): # <<< Додано новий ендпоінт
    """
    Надсилає транзакцію для голосування.
    Приймає приватний ключ виборця (для тестування) та індекси обраних варіантів.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract: # Використовуємо об'єкт розгорнутого контракту
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    # Перевірка наявності приватного ключа в запиті (для тестування)
    if not request_data.voter_private_key:
         raise HTTPException(status_code=400, detail="Voter private key is required in request body (for testing).")

    # Додаємо префікс 0x до приватного ключа з запиту, якщо його немає
    voter_private_key_with_prefix = request_data.voter_private_key
    if not voter_private_key_with_prefix.startswith("0x"):
        voter_private_key_with_prefix = "0x" + voter_private_key_with_prefix


    try:
        # Отримуємо адресу виборця з приватного ключа
        voter_address = w3.eth.account.from_key(voter_private_key_with_prefix).address

        # Отримуємо nonce для адреси виборця
        nonce = w3.eth.get_transaction_count(voter_address)

        # Будуємо транзакцію виклику функції vote()
        # contract.functions.<назва_функції>(<аргументи>).build_transaction({...})
        vote_txn = contract.functions.vote(
            request_data.option_indices # Передаємо масив індексів з запиту
        ).build_transaction({
            'from': voter_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ та ціну газу динамічно
            'gas': 2000000, # Достатній ліміт газу (можна оцінити)
            'gasPrice': w3.eth.gas_price,
        })

        # Підписуємо транзакцію приватним ключем виборця
        signed_txn = w3.eth.account.sign_transaction(vote_txn, voter_private_key_with_prefix)

        # Надсилаємо підписану транзакцію
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction) # <<< ЗВЕРНІТЬ УВАГУ: rawTransaction знову тут!

        # Чекаємо на підтвердження транзакції
        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        # Перевіряємо статус транзакції у квитанції
        if txn_receipt.status == 1:
            print(f"Vote transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Vote submitted successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Vote transaction failed. Receipt: {txn_receipt}")
            # TODO: Можливо, додати логіку для отримання причини revert
            raise HTTPException(status_code=500, detail=f"Vote transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error submitting vote: {e}")
        # Web3.py може кидати різні винятки (наприклад, замало газу, помилка підписання, VM Exception від require)
        raise HTTPException(status_code=500, detail=f"Error submitting vote: {e}")


# --- Ендпоінт для закриття голосування (транзакція) ---
# --- Ендпоінт для закриття голосування (транзакція) ---
# Тепер використовуємо нову модель OrganizerPrivateKeyRequest
@app.post("/close_voting")
async def close_voting(request_data: OrganizerPrivateKeyRequest): # <<< ЗМІНЕНО МОДЕЛЬ
    """
    Надсилає транзакцію для закриття голосування організатором.
    Приймає приватний ключ організатора (для тестування).
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    # Перевірка наявності приватного ключа (тепер вона в новій моделі)
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")

    # Решта коду функції close_voting залишається без змін, оскільки voter_address все одно не використовувався
    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix

    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        close_txn = contract.functions.closeVoting().build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(close_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Close voting transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Voting closed successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Close voting transaction failed. Receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Close voting transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error closing voting: {e}")
        raise HTTPException(status_code=500, detail=f"Error closing voting: {e}")


@app.post("/disable_whitelist")
async def disable_whitelist(request_data: OrganizerPrivateKeyRequest):
    """
    Надсилає транзакцію для вимкнення Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування).
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")

    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix

    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції disableWhitelist()
        disable_txn = contract.functions.disableWhitelist().build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ
            'gas': 2000000, # Достатній ліміт газу
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(disable_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction) # <<< raw_transaction

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Disable whitelist transaction successful. Hash: {txn_hash.hex()}")
            # Перевірка useWhitelist через /voting_details або Remix має показати false
            return {"message": "Whitelist disabled successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Disable whitelist transaction failed. Receipt: {txn_receipt}")
            # Тут, якщо контракт відхилить виклик (наприклад, бо голосування закрито),
            # Web3.py кине виняток, і він буде спійманий у блоці except.
            raise HTTPException(status_code=500, detail=f"Disable whitelist transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error disabling whitelist: {e}")
        raise HTTPException(status_code=500, detail=f"Error disabling whitelist: {e}")

# ... (решта ендпоінтів) ...

# --- Ендпоінт для додавання адреси до Whitelist'у (транзакція) ---
@app.post("/add_to_whitelist")
async def add_to_whitelist(request_data: AddToWhitelistRequest): # <<< Додано новий ендпоінт
    """
    Надсилає транзакцію для додавання адреси до Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування) та адресу виборця.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")
    if not w3.is_address(request_data.voter_address): # Перевірка, чи адреса валідна
         raise HTTPException(status_code=400, detail="Invalid voter address provided.")

    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix


    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції addToWhitelist(address)
        add_txn = contract.functions.addToWhitelist(
            request_data.voter_address # Передаємо адресу виборця з запиту
        ).build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ
            'gas': 2000000, # Достатній ліміт газу
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(add_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction) # <<< raw_transaction

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Add to whitelist transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Address added to whitelist successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Add to whitelist transaction failed. Receipt: {txn_receipt}")
            # TODO: Можливо, додати логіку для отримання причини revert (наприклад, якщо голосування вже почалося)
            raise HTTPException(status_code=500, detail=f"Add to whitelist transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error adding to whitelist: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding to whitelist: {e}")


# --- Ендпоінт для масового видалення адрес з Whitelist'у (транзакція) ---
@app.post("/remove_many_from_whitelist")
async def remove_many_from_whitelist(request_data: RemoveManyFromWhitelistRequest): # <<< Новий ендпоінт
    """
    Надсилає транзакцію для масового видалення адрес з Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування) та список адрес виборців.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")
    if not request_data.voter_addresses:
         raise HTTPException(status_code=400, detail="List of voter addresses is required.")

    # TODO: Додати валідацію кожної адреси у списку w3.is_address()

    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix

    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції removeManyFromWhitelist(address[])
        remove_many_txn = contract.functions.removeManyFromWhitelist(
            request_data.voter_addresses # Передаємо список адрес з запиту
        ).build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ (для масових операцій газ може бути вищим!)
            'gas': 3000000, # Збільшено ліміт газу для масової операції (можливо, потрібно більше)
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(remove_many_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Remove many from whitelist transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Addresses removed from whitelist successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Remove many from whitelist transaction failed. Receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Remove many from whitelist transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error removing many from whitelist: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing many from whitelist: {e}")

# ... (решта ендпоінтів) ...

@app.post("/add_many_to_whitelist")
async def add_many_to_whitelist(request_data: AddManyToWhitelistRequest): # <<< Код для масового додавання
    """
    Надсилає транзакцію для масового додавання адрес до Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування) та список адрес виборців.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")
    if not request_data.voter_addresses:
         raise HTTPException(status_code=400, detail="List of voter addresses is required.")

    # TODO: Додати валідацію кожної адреси у списку w3.is_address()

    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix

    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції addManyToWhitelist(address[])
        add_many_txn = contract.functions.addManyToWhitelist(
            request_data.voter_addresses # Передаємо список адрес з запиту
        ).build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ (для масових операцій газ може бути вищим!)
            'gas': 3000000, # Збільшено ліміт газу для масової операції (можливо, потрібно більше)
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(add_many_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Add many to whitelist transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Addresses added to whitelist successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Add many to whitelist transaction failed. Receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Add many to whitelist transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error adding many to whitelist: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding many to whitelist: {e}")


# --- Ендпоінт для видалення адреси з Whitelist'у (транзакція) ---
@app.post("/remove_from_whitelist")
async def remove_from_whitelist(request_data: RemoveFromWhitelistRequest): # <<< Код для видалення однієї адреси
    """
    Надсилає транзакцію для видалення адреси з Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування) та адресу виборця.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")
    if not w3.is_address(request_data.voter_address): # Перевірка, чи адреса валідна
         raise HTTPException(status_code=400, detail="Invalid voter address provided.")


    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix


    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції removeFromWhitelist(address)
        remove_txn = contract.functions.removeFromWhitelist(
            request_data.voter_address # Передаємо адресу виборця з запиту
        ).build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ
            'gas': 2000000, # Достатній ліміт газу
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(remove_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Remove from whitelist transaction successful. Hash: {txn_hash.hex()}")
            return {"message": "Address removed from whitelist successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Remove from whitelist transaction failed. Receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Remove from whitelist transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error removing from whitelist: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing from whitelist: {e}")

# ... (решта ендпоінтів) ...

# ... (існуючі імпорти, моделі, налаштування w3, ABI, BYTECODE, об'єкти контракту, ендпоінти) ...

# --- Ендпоінт для встановлення хешу IPFS (транзакція) ---
@app.post("/set_ipfs_hash")
async def set_ipfs_hash(request_data: SetIpfsHashRequest): # <<< Додано новий ендпоінт
    """
    Надсилає транзакцію для встановлення хешу IPFS файлу Whitelist'у організатором.
    Приймає приватний ключ організатора (для тестування) та хеш IPFS.
    !!! УВАГА: Передача приватного ключа тут тільки для ТЕСТУВАННЯ на Ganache !!!
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not request_data.organizer_private_key:
         raise HTTPException(status_code=400, detail="Organizer private key is required in request body (for testing).")
    if not request_data.ipfs_hash: # Проста перевірка на порожній хеш
         raise HTTPException(status_code=400, detail="IPFS hash is required.")

    organizer_private_key_with_prefix = request_data.organizer_private_key
    if not organizer_private_key_with_prefix.startswith("0x"):
        organizer_private_key_with_prefix = "0x" + organizer_private_key_with_prefix

    try:
        organizer_address = w3.eth.account.from_key(organizer_private_key_with_prefix).address
        nonce = w3.eth.get_transaction_count(organizer_address)

        # Будуємо транзакцію виклику функції setWhitelistIpfsHash(string)
        set_hash_txn = contract.functions.setWhitelistIpfsHash(
            request_data.ipfs_hash # Передаємо хеш IPFS з запиту
        ).build_transaction({
            'from': organizer_address,
            'nonce': nonce,
            # TODO: Краще оцінювати газ
            'gas': 2000000, # Достатній ліміт газу
            'gasPrice': w3.eth.gas_price,
        })

        signed_txn = w3.eth.account.sign_transaction(set_hash_txn, organizer_private_key_with_prefix)
        txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        txn_receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

        if txn_receipt.status == 1:
            print(f"Set IPFS hash transaction successful. Hash: {txn_hash.hex()}")
            # Перевірка whitelistIpfsHash через ендпоінт або Remix має показати встановлений хеш
            return {"message": "IPFS hash set successfully", "transactionHash": txn_hash.hex()}
        else:
            print(f"Set IPFS hash transaction failed. Receipt: {txn_receipt}")
            raise HTTPException(status_code=500, detail=f"Set IPFS hash transaction failed. Receipt: {txn_receipt}")

    except Exception as e:
        print(f"Error setting IPFS hash: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting IPFS hash: {e}")

# ... (решта ендпоінтів) ...

# --- Ендпоінт для перевірки, чи адреса в Whitelist ---
@app.get("/is_whitelisted")
async def check_is_whitelisted(address: str): # <<< Приймаємо адресу як query параметр
    """
    Перевіряє, чи вказана адреса знаходиться у Whitelist'і.
    Приймає адресу виборця як query параметр у URL: /is_whitelisted?address=0x...
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not w3.is_address(address): # Перевірка, чи адреса валідна
         raise HTTPException(status_code=400, detail="Invalid address format.")

    try:
        # Викликаємо view функцію isWhitelisted(address) з контракту
        # isWhitelisted - це public змінна (mapping), Web3.py генерує getter
        # Передаємо адресу як аргумент функції
        is_listed = contract.functions.isWhitelisted(address).call()

        return {"address": address, "is_whitelisted": is_listed} # Повертаємо статус

    except Exception as e:
        # Обробка помилок
        print(f"Error calling isWhitelisted(): {e}")
        raise HTTPException(status_code=500, detail=f"Error checking whitelist status: {e}")


# --- Ендпоінт для перевірки, чи адреса вже проголосувала ---
@app.get("/has_voted")
async def check_has_voted(address: str): # <<< Приймаємо адресу як query параметр
    """
    Перевіряє, чи вказана адреса вже проголосувала.
    Приймає адресу виборця як query параметр у URL: /has_voted?address=0x...
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")
    if not w3.is_address(address): # Перевірка, чи адреса валідна
         raise HTTPException(status_code=400, detail="Invalid address format.")

    try:
        # Викликаємо view функцію hasVoted(address) з контракту
        # hasVoted - це public змінна (mapping), Web3.py генерує getter
        # Передаємо адресу як аргумент функції
        has_voted_status = contract.functions.hasVoted(address).call()

        return {"address": address, "has_voted": has_voted_status} # Повертаємо статус

    except Exception as e:
        # Обробка помилок
        print(f"Error calling hasVoted(): {e}")
        raise HTTPException(status_code=500, detail=f"Error checking voted status: {e}")

# --- Ендпоінт для перевірки, чи голосування закрито ---
@app.get("/is_closed")
async def check_is_closed(): # <<< Не приймає аргументів
    """
    Перевіряє, чи голосування закрито організатором.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")

    try:
        # Викликаємо view функцію isClosed() з контракту (автоматичний getter)
        is_closed_status = contract.functions.isClosed().call()

        return {"is_closed": is_closed_status} # Повертаємо статус

    except Exception as e:
        # Обробка помилок
        print(f"Error calling isClosed(): {e}")
        raise HTTPException(status_code=500, detail=f"Error checking closed status: {e}")


# --- Ендпоінт для перевірки, чи Whitelist увімкнено ---
@app.get("/use_whitelist")
async def check_use_whitelist(): # <<< Не приймає аргументів
    """
    Перевіряє, чи механізм Whitelist'у увімкнено.
    """
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail="Backend not connected to Ethereum node.")
    if not contract:
         raise HTTPException(status_code=500, detail="Smart contract instance not available. Deploy or configure contract address.")

    try:
        # Викликаємо view функцію useWhitelist() з контракту (автоматичний getter)
        use_whitelist_status = contract.functions.useWhitelist().call()

        return {"use_whitelist": use_whitelist_status} # Повертаємо статус

    except Exception as e:
        # Обробка помилок
        print(f"Error calling useWhitelist(): {e}")
        raise HTTPException(status_code=500, detail=f"Error checking useWhitelist status: {e}")



# --- Ендпоінт для отримання адреси контракту та ABI ---
@app.get("/contract_info")
async def get_contract_info():
    """
    Надає фронтенду адресу розгорнутого контракту та його ABI.
    """
    # Перевіряємо, чи дані були успішно завантажені при старті бекенду
    if not CONTRACT_ADDRESS or not CONTRACT_ABI:
         # Якщо дані не завантажено, повертаємо помилку 500
         raise HTTPException(status_code=500, detail="Contract address or ABI not loaded on backend.")

    # Повертаємо адресу та ABI у форматі JSON
    # ABI вже є списком (масивом) у Python, що відповідає JSON масиву
    return {
        "address": CONTRACT_ADDRESS,
        "abi": CONTRACT_ABI
    }
