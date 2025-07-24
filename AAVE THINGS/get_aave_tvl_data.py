import eth_typing
from web3 import Web3
from web3.exceptions import ContractLogicError
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONSTANTS ---
RAY_MATH_PRECISION = 10 ** 27
SECONDS_PER_YEAR = 31536000  # 365 * 24 * 60 * 60

# Aave ABI field indexes by version
# These indexes correspond to the `AggregatedReserveData` struct returned by `getReservesData`
AAVE_V2_INDEXES = {
    "symbol": 2,
    "asset_decimals": 3,
    "is_active": 11,
    "is_frozen": 12,
    "available_liquidity_raw": 23,
    "total_scaled_variable_debt_raw": 27,
    "price_in_market_reference_currency": 28,
    "variable_borrow_rate_raw": 16,
    "variable_borrow_index_raw": 14,
    "last_update_timestamp": 18,
}

AAVE_V3_INDEXES = {
    "symbol": 2,
    "asset_decimals": 3,
    "is_active": 10,
    "is_frozen": 11,
    "available_liquidity_raw": 20,
    "total_scaled_variable_debt_raw": 21,
    "price_in_market_reference_currency": 22,
    "variable_borrow_rate_raw": 15,
    "variable_borrow_index_raw": 13,
    "last_update_timestamp": 16,
}

# Mapping for easy lookup
AAVE_VERSION_INDEXES = {
    "v2": AAVE_V2_INDEXES,
    "v3": AAVE_V3_INDEXES,
}


# --- Helper Functions ---

def connect_to_web3(rpc_url: str) -> Web3:
    """
    Establishes a connection to the Blockchain network via an RPC URL.
    Raises ConnectionError if connection fails.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to Blockchain network at: {rpc_url}. Please check the RPC_URL.")
    return w3


def load_abi_from_file(abi_path: str) -> list:
    """
    Loads a contract ABI from a JSON file.
    Raises FileNotFoundError if the file does not exist, or ValueError if JSON is invalid.
    """
    if not os.path.exists(abi_path):
        raise FileNotFoundError(f"ABI file not found: '{abi_path}'. Please provide a valid path.")
    try:
        with open(abi_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in ABI file: '{abi_path}'. Please ensure the file is correct.")


def load_addresses_config(config_path: str) -> dict:
    """
    Loads address configuration from a JSON file.
    Raises FileNotFoundError if the file does not exist, or ValueError if JSON is invalid.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Address configuration file not found: '{config_path}'. Please create it.")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in address configuration file: '{config_path}'.")


def get_aave_reserves_data(web3_instance: Web3, data_provider_address: eth_typing.ChecksumAddress, provider_abi: list,
                           pool_addresses_provider: eth_typing.ChecksumAddress) -> tuple:
    """
    Calls the getReservesData function on the UiPoolDataProvider contract.
    Returns reserve data and market base currency information.
    """
    try:
        contract = web3_instance.eth.contract(address=data_provider_address, abi=provider_abi)
        # Gas limit not explicitly set; Web3.py will estimate if not provided.
        # This aligns with minimalism unless specific gas limits are required.
        # In case of failures of calls, set ~30kk gas limit.
        reserves, base_currency_info = contract.functions.getReservesData(pool_addresses_provider).call()
        return reserves, base_currency_info
    except ContractLogicError as e:
        raise ContractLogicError(f"Contract logic error calling getReservesData: {e}")
    except Exception as e:
        raise Exception(f"Unknown error fetching reserve data: {e}")


def calculate_projected_variable_borrow_index(
        variable_borrow_rate: int,
        variable_borrow_index: int,
        last_update_timestamp: int,
        current_timestamp: int
) -> int:
    """
    Calculates the projected variable borrow index, accounting for elapsed time.
    Mimics Aave's interest accumulation logic.
    """
    if current_timestamp <= last_update_timestamp:
        return variable_borrow_index

    time_delta = current_timestamp - last_update_timestamp
    cumulated_interest_factor = (variable_borrow_rate * time_delta) // SECONDS_PER_YEAR + RAY_MATH_PRECISION
    projected_index = (variable_borrow_index * cumulated_interest_factor) // RAY_MATH_PRECISION
    return projected_index


def calculate_aave_metrics_from_reserves(
        reserves_data: list,
        base_currency_info: list,
        include_inactive_frozen: bool,
        aave_version: str
) -> tuple[float, float, float]:
    """
    Calculates Aave's total market size (TVL), total borrows, and total available liquidity.
    Uses 'totalScaledVariableDebt' and 'variableBorrowIndex' for variable borrows,
    and asset prices for USD conversion.

    Args:
        reserves_data: Reserve data obtained from UiPoolDataProvider.
        base_currency_info: Market base currency information.
        include_inactive_frozen: Whether to include inactive/frozen reserves in calculations.
        aave_version: Aave version ('v2' or 'v3') to determine correct field indexes.

    Returns:
        A tuple: (total_market_size_usd, total_available_usd, total_borrows_usd)
    """
    total_market_size_usd = 0.0
    total_borrows_usd = 0.0
    total_available_usd = 0.0

    current_timestamp = int(time.time())

    market_ref_currency_unit = base_currency_info[0]
    market_ref_currency_price_in_usd_raw = base_currency_info[1]
    network_base_token_price_decimals = base_currency_info[3]

    market_ref_currency_price_in_usd = (
        market_ref_currency_price_in_usd_raw / (10 ** network_base_token_price_decimals)
        if network_base_token_price_decimals > 0
        else float(market_ref_currency_price_in_usd_raw)
    )

    # Get version-specific indexes
    INDEXES = AAVE_VERSION_INDEXES.get(aave_version)
    if not INDEXES:
        raise ValueError(f"Unsupported Aave version: {aave_version}. Use 'v2' or 'v3'.")

    for i, reserve in enumerate(reserves_data):
        try:
            symbol = reserve[INDEXES["symbol"]]
            asset_decimals = reserve[INDEXES["asset_decimals"]]
            is_active = reserve[INDEXES["is_active"]]
            is_frozen = reserve[INDEXES["is_frozen"]]

            # Skip if not active/frozen and not configured to include
            if not include_inactive_frozen and (not is_active or is_frozen):
                continue

            # Skip if crucial data is missing or zero
            if market_ref_currency_unit == 0 or reserve[INDEXES["price_in_market_reference_currency"]] == 0:
                print(f"Warning: Zero market currency unit or asset price for {symbol}. Skipping.")
                continue

            available_liquidity_raw = reserve[INDEXES["available_liquidity_raw"]]
            total_scaled_variable_debt_raw = reserve[INDEXES["total_scaled_variable_debt_raw"]]
            price_in_market_reference_currency = reserve[INDEXES["price_in_market_reference_currency"]]
            variable_borrow_rate_raw = reserve[INDEXES["variable_borrow_rate_raw"]]
            variable_borrow_index_raw = reserve[INDEXES["variable_borrow_index_raw"]]
            last_update_timestamp = reserve[INDEXES["last_update_timestamp"]]

            projected_variable_borrow_index = calculate_projected_variable_borrow_index(
                variable_borrow_rate=variable_borrow_rate_raw,
                variable_borrow_index=variable_borrow_index_raw,
                last_update_timestamp=last_update_timestamp,
                current_timestamp=current_timestamp
            )

            total_variable_debt_actual_raw = (
                    (total_scaled_variable_debt_raw * projected_variable_borrow_index) // RAY_MATH_PRECISION
            )

            normalized_available_liquidity = available_liquidity_raw / (10 ** asset_decimals)
            normalized_total_variable_debt_actual = total_variable_debt_actual_raw / (10 ** asset_decimals)

            # Aave defines total supplied as available + total variable debt
            normalized_total_supplied_asset = normalized_available_liquidity + normalized_total_variable_debt_actual

            asset_price_in_usd = (
                    (price_in_market_reference_currency / market_ref_currency_unit) * market_ref_currency_price_in_usd
            )

            value_total_borrowed_in_usd = normalized_total_variable_debt_actual * asset_price_in_usd
            value_total_available_in_usd = normalized_available_liquidity * asset_price_in_usd
            value_total_supplied_in_usd = normalized_total_supplied_asset * asset_price_in_usd

            total_borrows_usd += value_total_borrowed_in_usd
            total_available_usd += value_total_available_in_usd
            total_market_size_usd += value_total_supplied_in_usd

        except IndexError as ie:
            print(
                f"Error: Index error for reserve {i + 1} ({symbol}) on Aave {aave_version.upper()}: {ie}. Check ABI and indexes. Skipping.")
        except Exception as ex:
            print(
                f"Error: Unknown error processing reserve {i + 1} ({symbol}) on Aave {aave_version.upper()}: {ex}. Skipping.")

    return total_market_size_usd, total_available_usd, total_borrows_usd


def get_aave_total_metrics(
        network: str = "ethereum",
        aave_version: str = "v3",
        market_name: str = "default",
        include_inactive_frozen: bool = False
) -> tuple[float, float, float]:
    """
    Retrieves total Aave metrics (market size, available liquidity, borrows)
    for a specified network, version, and market.

    Args:
        network: The blockchain network (e.g., 'ethereum', 'polygon', 'avalanche'). Defaults to 'ethereum'.
        aave_version: Aave version (e.g., 'v3', 'v2'). Defaults to 'v3'.
        market_name: The name of the specific market (e.g., 'Core', 'Ethereum'). Defaults to 'default',
                     which processes all available markets for the given network and version.
        include_inactive_frozen: Whether to include inactive/frozen reserves in calculations. Defaults to False.

    Returns:
        A tuple with (total_market_size_usd, total_available_usd, total_borrows_usd).
    """
    network = network.lower()
    aave_version = aave_version.lower()

    rpc_urls = {key.replace('_RPC_URL', '').lower(): value for key, value in os.environ.items() if
                key.endswith('_RPC_URL')}
    addresses_config = load_addresses_config("aave_addresses_config.json")

    # Validate configurations
    if network not in rpc_urls or not rpc_urls[network]:
        raise ValueError(f"RPC URL for network '{network}' not found or not set in .env file.")
    if network not in addresses_config:
        raise ValueError(f"Address configuration for network '{network}' not found in aave_addresses_config.json.")
    if aave_version not in addresses_config[network]:
        raise ValueError(f"Address configuration for Aave version '{aave_version}' on network '{network}' not found.")

    network_config = addresses_config[network][aave_version]

    markets_to_process = []
    if market_name == "default":
        markets_to_process = list(network_config.keys())
    elif market_name in network_config:
        markets_to_process = [market_name]
    else:
        raise ValueError(
            f"Market '{market_name}' not found for network '{network}' and version '{aave_version}'. Available markets: {', '.join(network_config.keys())}"
        )

    total_market_size_agg = 0.0
    total_available_agg = 0.0
    total_borrows_agg = 0.0

    print(f"\n--- Fetching Aave Metrics for {network.upper()} ({aave_version.upper()}) ---")

    rpc_url = rpc_urls[network]
    w3 = connect_to_web3(rpc_url)
    print(f"Connected to {network.upper()} RPC: {rpc_url}. Latest block: {w3.eth.block_number}")

    abi_path = f"aave_{aave_version}_uipool_abi.json"
    provider_abi = load_abi_from_file(abi_path)

    for current_market_name in markets_to_process:
        print(f"\nProcessing market: {current_market_name}")
        market_addresses = network_config[current_market_name]

        pool_addresses_provider_address = Web3.to_checksum_address(market_addresses["pool_addresses_provider"])
        ui_pool_data_provider_address = Web3.to_checksum_address(market_addresses["ui_pool_data_provider"])

        try:
            reserves_data, base_currency_info = get_aave_reserves_data(
                w3,
                ui_pool_data_provider_address,
                provider_abi,
                pool_addresses_provider_address
            )

            market_size, available_liquidity, borrows = calculate_aave_metrics_from_reserves(
                reserves_data, base_currency_info, include_inactive_frozen, aave_version
            )

            total_market_size_agg += market_size
            total_available_agg += available_liquidity
            total_borrows_agg += borrows
            print(
                f"  Results for '{current_market_name}' market: TVL=${market_size:,.2f}, Available=${available_liquidity:,.2f}, Borrows=${borrows:,.2f}"
            )

        except Exception as e:
            print(f"  Error processing market '{current_market_name}': {e}")

    print(f"\n--- Aggregated Results for {network.upper()} ({aave_version.upper()}) ---")
    print(f"Total Market Size (TVL): **${total_market_size_agg:,.2f}**")
    print(f"Total Available Liquidity: **${total_available_agg:,.2f}**")
    print(f"Total Borrows: **${total_borrows_agg:,.2f}**")

    return total_market_size_agg, total_available_agg, total_borrows_agg


# --- MAIN SCRIPT LOGIC ---
def main():
    # Example usages:

    # 1. Get metrics for Ethereum V3 Core, excluding inactive/frozen reserves
    print("Fetching data for Ethereum V2 (Core market), including inactive/frozen:")
    try:
        eth_v2_core_metrics = get_aave_total_metrics(
            network="ethereum", aave_version="v2", market_name="default", include_inactive_frozen=True
        )
        print(
            f"Summary Ethereum V2 Core: TVL=${eth_v2_core_metrics[0]:,.2f}, Available=${eth_v2_core_metrics[1]:,.2f}, Borrows=${eth_v2_core_metrics[2]:,.2f}"
        )
    except Exception as e:
        print(f"Failed to fetch Ethereum V3 Core metrics: {e}")

    print("\n" + "=" * 80 + "\n")

    # 2. Get metrics for Polygon V3 (default market), including inactive/frozen reserves
    print("Fetching data for Polygon V3 (Default market), including inactive/frozen:")
    try:
        poly_v3_default_metrics = get_aave_total_metrics(
            network="polygon", aave_version="v3", include_inactive_frozen=True
        )
        print(
            f"Summary Polygon V3 Default: TVL=${poly_v3_default_metrics[0]:,.2f}, Available=${poly_v3_default_metrics[1]:,.2f}, Borrows=${poly_v3_default_metrics[2]:,.2f}"
        )
    except Exception as e:
        print(f"Failed to fetch Polygon V3 Default metrics: {e}")

    print("\n" + "=" * 80 + "\n")

    # 3. Get aggregated metrics for Ethereum V3 (all markets), excluding inactive/frozen
    # market_name="default" will iterate through every market in the specific network+aave_version
    print("Fetching aggregated data for Ethereum V3 (all markets), excluding inactive/frozen:")
    try:
        eth_v3_all_markets_metrics = get_aave_total_metrics(
            network="ethereum", aave_version="v3", market_name="default", include_inactive_frozen=False
        )
        print(
            f"Summary Ethereum V2 (All Markets): TVL=${eth_v3_all_markets_metrics[0]:,.2f}, Available=${eth_v3_all_markets_metrics[1]:,.2f}, Borrows=${eth_v3_all_markets_metrics[2]:,.2f}"
        )
    except Exception as e:
        print(f"Failed to fetch Ethereum V2 (All Markets) metrics: {e}")


if __name__ == "__main__":
    main()