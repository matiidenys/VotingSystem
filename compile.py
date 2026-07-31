import json
import os
from solcx import compile_standard, install_solc

# 1. НАЛАШТУВАННЯ
# Версія має точно співпадати з тією, що була в Remix під час деплою
SOLC_VERSION = '0.8.30'
SOURCE_FILENAME = "Voting.sol"

print(f"🔍 Checking/Installing solc version {SOLC_VERSION}...")
install_solc(SOLC_VERSION)

# 2. ЧИТАННЯ КОНТРАКТУ
if not os.path.exists(SOURCE_FILENAME):
    print(f"❌ Error: File '{SOURCE_FILENAME}' not found. Make sure it is in the same folder.")
    exit(1)

with open(SOURCE_FILENAME, "r", encoding="utf-8") as file:
    source_content = file.read()

print("🚀 Compiling contracts... This may take a moment.")

# 3. КОМПІЛЯЦІЯ
# Ми використовуємо Standard JSON Input - це стандартний формат для солідіті
compiled_sol = compile_standard(
    {
        "language": "Solidity",
        "sources": {SOURCE_FILENAME: {"content": source_content}},
        "settings": {
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode"]  # Нам потрібні ABI та Байткод
                }
            },
            # Важливо: Вмикаємо оптимізацію, щоб співпадало з Etherscan
            "optimizer": {
                "enabled": True,
                "runs": 200
            }
        },
    },
    solc_version=SOLC_VERSION,
)


# 4. ЗБЕРЕЖЕННЯ JSON
def save_contract_json(contract_name):
    # Шлях до даних у результаті компіляції
    try:
        contract_data = compiled_sol["contracts"][SOURCE_FILENAME][contract_name]
    except KeyError:
        print(f"⚠️ Warning: Contract '{contract_name}' not found in source file.")
        return

    abi = contract_data["abi"]

    # Ми зберігаємо просто список ABI, бо це найпростіше для Ethers.js
    # Якщо вам колись знадобиться байткод для деплою через Python,
    # можна змінити це на: {"abi": abi, "bytecode": contract_data["evm"]["bytecode"]["object"]}

    output_filename = f"{contract_name}.json"

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(abi, f, indent=2)

    print(f"✅ Saved ABI to: {output_filename}")


# Зберігаємо файли для всіх наших контрактів
save_contract_json("VotingFactory")
save_contract_json("Voting")
save_contract_json("WhitelistRegistry")

print("\n🎉 Compilation complete! You can now start the backend.")