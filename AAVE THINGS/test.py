from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://virulent-palpable-patina.quiknode.pro/efb8706fe4dd4d0cf30351499c10eb43ff159d16"))

if not w3.is_connected():
  print("Failed to connect to the HTTP provider!")
  exit()

latest_block_number = w3.eth.call

print(f"Latest Block Number: {latest_block_number}")