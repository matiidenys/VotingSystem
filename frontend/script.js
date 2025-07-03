// script.js

// ==================== Оголошуємо глобальні змінні ====================
let provider; // ethers provider (from MetaMask)
let signer;   // ethers signer (MetaMask account)
let contract; // ethers contract object

// Contract info fetched from backend
let contractAddress = null;
let contractAbi = null;

// NEW: Глобальна змінна для зберігання адреси поточного активного акаунта MetaMask
let currentAccount = null;

// HTML element variables (initialized after DOMContentLoaded)
let connectButton;
let statusSpan;
let accountInfoDiv;
let accountsListDiv; // ЗМІНЕНО: Був accountListDiv, але ID в HTML має бути "accountsList"
let currentAccountSpan; // НОВИЙ ЕЛЕМЕНТ для відображення активного акаунта
let votingSectionDiv;
let contractAddressSpan;
let votingDetailsDiv;
let votingTitleSpan;
let votingOrganizerSpan;
let votingStartTimeSpan;
let votingEndTimeSpan;
let votingTypeSpan;
let votingUseWhitelistSpan;
let votingIsClosedSpan;
let voteControlsDiv;
let optionsListDiv;
let voteButton;
let resultsSectionDiv;
let resultsListDiv;


// ==================== Чекаємо, доки DOM буде повністю завантажений ====================
document.addEventListener('DOMContentLoaded', async () => {
    console.log("DOM fully loaded and parsed.");

    // ==================== Отримуємо посилання на HTML елементи ТУТ ====================
    connectButton = document.getElementById('connectButton');
    statusSpan = document.getElementById('status');
    accountInfoDiv = document.getElementById('accountInfo');
    accountsListDiv = document.getElementById('accountsList'); // ЗМІНЕНО ID
    currentAccountSpan = document.getElementById('currentAccount'); // НОВИЙ ЕЛЕМЕНТ ID в HTML (який ми додали)

    votingSectionDiv = document.getElementById('votingSection');
    contractAddressSpan = document.getElementById('contractAddress');

    votingDetailsDiv = document.getElementById('votingDetails');
    votingTitleSpan = document.getElementById('votingTitle');
    votingOrganizerSpan = document.getElementById('votingOrganizer');
    votingStartTimeSpan = document.getElementById('votingStartTime');
    votingEndTimeSpan = document.getElementById('votingEndTime');
    votingTypeSpan = document.getElementById('votingType');
    votingUseWhitelistSpan = document.getElementById('votingUseWhitelist');
    votingIsClosedSpan = document.getElementById('votingIsClosed');

    voteControlsDiv = document.getElementById('voteControls');
    optionsListDiv = document.getElementById('optionsList');
    voteButton = document.getElementById('voteButton');

    resultsSectionDiv = document.getElementById('resultsSection');
    resultsListDiv = document.getElementById('resultsList');


    // === Перевірка, чи знайдено критично важливі елементи ===
    if (!connectButton || !statusSpan || !accountInfoDiv || !accountsListDiv || !currentAccountSpan || !votingSectionDiv || !contractAddressSpan || !votingDetailsDiv || !votingTitleSpan || !votingOrganizerSpan || !votingStartTimeSpan || !votingEndTimeSpan || !votingTypeSpan || !votingUseWhitelistSpan || !votingIsClosedSpan || !voteControlsDiv || !optionsListDiv || !voteButton) {
         console.error("FATAL ERROR: One or more required HTML elements not found. Please check your index.html IDs.");
         if (statusSpan) statusSpan.textContent = 'Fatal Error: Cannot load page elements.';
         if (connectButton) connectButton.disabled = true;
         return;
    } else {
         console.log("All required HTML elements found.");
    }


    // ==================== Обробники подій ====================
    connectButton.addEventListener('click', connectWalletAndInitializeContract);
    console.log("Connect button event listener added.");

    if (voteButton) {
        voteButton.addEventListener('click', submitVote);
    }

    // --- ДОДАНО/ОНОВЛЕНО: Слухаємо зміни акаунта та мережі в MetaMask ---
    if (typeof window.ethereum !== 'undefined') {
        window.ethereum.on('accountsChanged', handleAccountsChanged);
        window.ethereum.on('chainChanged', handleChainChanged);
        console.log("MetaMask event listeners added for accountsChanged and chainChanged.");
    } else {
        if (statusSpan) statusSpan.textContent = 'Please install MetaMask!';
        if (connectButton) connectButton.disabled = true;
    }

    // ==================== Логіка при завантаженні сторінки (після DOM ready) ====================
    await fetchContractInfo(); // Завантажуємо інформацію про контракт з бекенду

    // Спроба автоматичного підключення, якщо користувач вже дозволив доступ раніше
    if (typeof window.ethereum !== 'undefined' && window.ethereum.selectedAddress) {
        console.log("MetaMask already has selectedAddress, attempting auto-reconnect...");
        await connectWalletAndInitializeContract();
    } else {
        console.log("No pre-connected MetaMask accounts found or MetaMask not detected.");
        // Якщо немає попередньо підключених акаунтів, кнопка підключення залишається активною.
    }

}); // Кінець обробника DOMContentLoaded


// ===================================
// Функції-обробники подій MetaMask
// ===================================

async function handleAccountsChanged(accounts) {
    console.log("MetaMask accounts changed to:", accounts);
    if (accounts.length === 0) {
        // Користувач відключив всі акаунти від сайту або переключився на акаунт, який не підключений
        console.log('User disconnected all accounts from this dApp or switched to an unconnected account.');
        if (statusSpan) statusSpan.textContent = 'Disconnected. Please connect your wallet.';
        currentAccount = null;
        if (currentAccountSpan) currentAccountSpan.textContent = 'Not connected';

        // Очистити UI та деініціалізувати об'єкти
        if (accountsListDiv) accountsListDiv.innerHTML = '<h4>Connected Accounts:</h4><p>No accounts connected.</p>';
        if (accountInfoDiv) accountInfoDiv.style.display = 'none'; // Сховати info блок
        if (votingSectionDiv) votingSectionDiv.style.display = 'none'; // Сховати секцію голосування

        provider = null;
        signer = null;
        contract = null;
        if (connectButton) {
            connectButton.textContent = 'Connect MetaMask';
            connectButton.disabled = false; // Знову активувати кнопку
        }
    } else {
        // Акаунти змінились (користувач переключився на інший підключений акаунт)
        console.log("Re-initializing contract and UI for new active account.");
        // Просто повторно викликаємо ініціалізацію, щоб оновити signer і відобразити новий активний акаунт
        await connectWalletAndInitializeContract();
    }
}

function handleChainChanged(chainId) {
    console.log("MetaMask chain changed to:", chainId);
    // Для уникнення проблем з провайдером та контрактом при зміні мережі, рекомендується перезавантажити сторінку
    alert('MetaMask network changed. The page will reload.');
    window.location.reload();
}


// ==================== Функції (переміщуємо їх поза обробником події) ====================

// Функція для завантаження даних контракту з бекенду
async function fetchContractInfo() {
    console.log("Fetching contract info from backend...");
    if (statusSpan) {
        statusSpan.textContent = 'Loading contract info...';
    }

    if (contractAddress && contractAbi) {
        console.log("Contract info already loaded.");
        if (statusSpan && statusSpan.textContent === 'Loading contract info...') {
            statusSpan.textContent = 'Contract info loaded. Ready to connect MetaMask.';
        }
        return; // Виходимо, якщо дані вже є
    }

    try {
        const response = await fetch('/contract_info');
        if (!response.ok) {
            const errorDetail = await response.text();
            if (response.status === 404) {
                throw new Error("Backend endpoint /contract_info not found. Ensure backend is running and endpoint is added.");
            }
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorDetail}`);
        }

        const data = await response.json();
        if (!data.address || !data.abi) {
            throw new Error("Backend returned invalid contract info format.");
        }

        contractAddress = data.address;
        contractAbi = data.abi;

        console.log("Contract info loaded successfully:", { address: contractAddress, abi: contractAbi });
        if (statusSpan && statusSpan.textContent === 'Loading contract info...') {
            statusSpan.textContent = 'Contract info loaded. Ready to connect MetaMask.';
        }
    } catch (error) {
        console.error("Error fetching contract info:", error);
        if (statusSpan) {
            statusSpan.textContent = `Error loading contract info: ${error.message}`;
        }
        if (connectButton) {
            connectButton.disabled = true;
        }
    }
}


// Функція для підключення до MetaMask та ініціалізації контракту
async function connectWalletAndInitializeContract() {
    // Перевірка, чи інформація про контракт завантажена.
    if (!contractAddress || !contractAbi) {
        console.warn("Contract info not loaded yet. Attempting to fetch...");
        await fetchContractInfo(); // Спробуємо завантажити info
        if (!contractAddress || !contractAbi) { // Перевіряємо ще раз
            console.error("Could not fetch contract info. Cannot connect wallet for contract interaction.");
            if (statusSpan) statusSpan.textContent = 'Error: Contract info not loaded. Cannot connect.';
            return;
        }
    }

    if (typeof window.ethereum === 'undefined') {
        console.error("MetaMask is not installed!");
        if (statusSpan) statusSpan.textContent = 'MetaMask not installed!';
        if (connectButton) connectButton.disabled = true;
        return;
    }

    console.log("Attempting to connect to MetaMask and initialize contract...");
    if (statusSpan) statusSpan.textContent = 'Connecting to MetaMask...';

    try {
        // 1. Запитуємо доступ до облікових записів MetaMask
        // Це також дозволяє MetaMask повернути поточний активний акаунт
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        console.log("MetaMask eth_requestAccounts responded with accounts:", accounts);

        if (accounts.length === 0) {
            console.warn("MetaMask connected, but no accounts provided.");
            if (statusSpan) statusSpan.textContent = 'MetaMask connected, no accounts provided.';
            currentAccount = null;
            if (currentAccountSpan) currentAccountSpan.textContent = 'Not connected';
            return;
        }

        // 2. Створюємо провайдера та підписувача ethers
        provider = new ethers.providers.Web3Provider(window.ethereum);
        // Асинхронно отримуємо підписувача з активним акаунтом MetaMask
        signer = await provider.getSigner(); // В ethers v5 getSigner() повертає Promise, якщо немає обраного, або Signer
                                            // В ethers v6 getSigner() завжди Promise

        currentAccount = await signer.getAddress(); // Отримуємо адресу поточного активного акаунта
        console.log("Active MetaMask account (signer address):", currentAccount);


        // 3. Ініціалізуємо об'єкт контракту ethers
        contract = new ethers.Contract(contractAddress, contractAbi, signer);
        console.log("Contract object initialized:", contract);

        // 4. Оновлюємо UI після успіху
        if (statusSpan) statusSpan.textContent = 'Connected!';
        if (connectButton) {
            connectButton.textContent = 'Wallet Connected';
            connectButton.disabled = true;
        }
        if (accountInfoDiv) accountInfoDiv.style.display = 'block'; // Показуємо блок з інформацією про акаунт
        if (votingSectionDiv) votingSectionDiv.style.display = 'block'; // Показуємо секцію голосування
        if (contractAddressSpan) contractAddressSpan.textContent = contractAddress;


        // 5. Отримуємо та відображаємо список дозволених облікових записів та поточний активний акаунт
        await displayAccounts(); // Ця функція оновлена, щоб відображати currentAccount
        displayCurrentAccount(currentAccount); // Явна функція для активного акаунта

        // 6. Завантажуємо та відображаємо деталі голосування
        await fetchVotingDetails();

    } catch (error) {
        console.error("MetaMask connection/initialization error:", error);
        if (statusSpan) {
            if (error.code === 4001) {
                statusSpan.textContent = 'MetaMask connection rejected.';
            } else {
                statusSpan.textContent = `Connection/Initialization failed: ${error.message}`;
            }
        }
        if (connectButton) connectButton.disabled = false; // Знову активувати кнопку
        currentAccount = null;
        if (currentAccountSpan) currentAccountSpan.textContent = 'Not connected';
    }
}

// Функція для відображення доступних облікових записів (без випадаючого списку)
async function displayAccounts() {
    if (!provider || !accountsListDiv || !currentAccountSpan) {
        console.error("Provider or required HTML elements for accounts display not initialized.");
        return;
    }

    try {
        // Отримуємо всі ДОЗВОЛЕНІ облікові записи на ПОТОЧНІЙ мережі провайдера
        const accounts = await provider.listAccounts(); // Це повертає масив об'єктів Account (з полем .address) в v6, або масив рядків в v5
        console.log("Available accounts from provider:", accounts);

        // Очищаємо попередній вміст
        accountsListDiv.innerHTML = '<h4>Connected Accounts:</h4>';
        const ul = document.createElement('ul');

        if (accounts.length > 0) {
            accounts.forEach(account => {
                const li = document.createElement('li');
                // Отримуємо адресу правильно залежно від версії ethers
                const accountAddress = typeof account === 'string' ? account : account.address;

                li.textContent = `${accountAddress}`;
                if (accountAddress.toLowerCase() === currentAccount.toLowerCase()) { // Порівнюємо з активним акаунтом
                    li.style.fontWeight = 'bold';
                    li.textContent += ' (Active)';
                }
                ul.appendChild(li);
            });
            accountsListDiv.appendChild(ul);
        } else {
            accountsListDiv.innerHTML += '<p>No accounts connected to this dApp.</p>';
        }

    } catch (error) {
        console.error("Error displaying accounts:", error);
        if (accountsListDiv) accountsListDiv.innerHTML = '<p>Error loading accounts data.</p>';
    }
}

// НОВА ФУНКЦІЯ: для явного відображення поточного активного акаунта
function displayCurrentAccount(accountAddress) {
    if (currentAccountSpan) {
        if (accountAddress) {
            currentAccountSpan.textContent = `${accountAddress.substring(0, 6)}...${accountAddress.substring(accountAddress.length - 4)}`;
        } else {
            currentAccountSpan.textContent = 'Not connected';
        }
    }
}


// Функція для ініціалізації об'єкта контракту ethers
function initializeContract() {
    if (!contractAddressSpan || !votingSectionDiv) {
        console.error("Required HTML elements for contract display not found!");
        if (votingSectionDiv) votingSectionDiv.style.display = 'none';
        return;
    }

    if (provider && contractAddress && contractAbi && signer) {
        try {
            contract = new ethers.Contract(contractAddress, contractAbi, signer);
            contractAddressSpan.textContent = contractAddress;
            votingSectionDiv.style.display = 'block';
            console.log("Contract object initialized:", contract);
        } catch (error) {
            console.error("Error initializing contract object:", error);
            if (votingSectionDiv) votingSectionDiv.style.display = 'none';
        }
    } else {
        console.error("Could not initialize contract. Provider, address, ABI, or signer missing.");
        if (votingSectionDiv) votingSectionDiv.style.display = 'none';
    }
}


// ==================== Функції для завантаження та відображення деталей голосування ====================
async function fetchVotingDetails() {
    console.log("Fetching voting details from backend...");
    if (!votingDetailsDiv || !optionsListDiv || !votingTitleSpan || !votingOrganizerSpan || !votingStartTimeSpan || !votingEndTimeSpan || !votingTypeSpan || !votingUseWhitelistSpan || !votingIsClosedSpan) {
        console.error("Cannot fetch/display voting details. Required HTML elements for details not found.");
        if (votingDetailsDiv) votingDetailsDiv.innerHTML = '<h3>Error: Details UI elements missing.</h3>';
        if (optionsListDiv) optionsListDiv.innerHTML = '<p>Error: Options UI elements missing.</p>';
        return;
    }

    if (!contract) {
        console.error("Cannot fetch voting details. Contract object not initialized.");
        if (votingDetailsDiv) votingDetailsDiv.innerHTML = '<h3>Error: Contract not initialized.</h3>';
        if (optionsListDiv) optionsListDiv.innerHTML = '<p>Error: Contract not initialized.</p>';
        return;
    }

    try {
        // === Завантаження деталей голосування (/voting_details) ===
        console.log("Fetching from /voting_details...");
        const detailsResponse = await fetch('/voting_details');
        if (!detailsResponse.ok) {
            const errorText = await detailsResponse.text();
            throw new Error(`HTTP error fetching voting details! status: ${detailsResponse.status}, detail: ${errorText}`);
        }
        const details = await detailsResponse.json();
        console.log("Voting Details loaded:", details);

        // === Завантаження варіантів голосування (/voting_options) ===
        console.log("Fetching from /voting_options...");
        const optionsResponse = await fetch('/voting_options');
        if (!optionsResponse.ok) {
            const errorText = await optionsResponse.text();
            throw new Error(`HTTP error fetching voting options! status: ${optionsResponse.status}, detail: ${errorText}`);
        }
        const optionsData = await optionsResponse.json();
        const options = optionsData.options;
        console.log("Voting Options loaded:", options);

        // === Відображення деталей на сторінці ===
        if (votingDetailsDiv) votingDetailsDiv.style.display = 'block';
        if (votingDetailsDiv && votingDetailsDiv.querySelector('h3')) {
            votingDetailsDiv.querySelector('h3').textContent = 'Voting Details';
        }
        if (votingTitleSpan) votingTitleSpan.textContent = details.title || '-';
        if (votingOrganizerSpan) votingOrganizerSpan.textContent = details.organizer || '-';
        if (votingStartTimeSpan) votingStartTimeSpan.textContent = details.startTime ? new Date(details.startTime * 1000).toLocaleString() : '-';
        if (votingEndTimeSpan) votingEndTimeSpan.textContent = details.endTime ? new Date(details.endTime * 1000).toLocaleString() : '-';

        if (votingTypeSpan) {
            const votingTypeMap = { 0: "Single Choice", 1: "Multiple Choice" };
            votingTypeSpan.textContent = votingTypeMap[details.votingType] || `Unknown Type (${details.votingType})`;
        }
        if (votingUseWhitelistSpan) votingUseWhitelistSpan.textContent = details.useWhitelist ? "Enabled" : "Disabled";
        if (votingIsClosedSpan) votingIsClosedSpan.textContent = details.isClosed ? "Yes" : "No";

        // === Відображення варіантів голосування ===
        if (optionsListDiv) {
            optionsListDiv.innerHTML = '';
            if (options && options.length > 0) {
                options.forEach((optionText, index) => {
                    const optionInputId = `option-${index}`;

                    const inputElement = document.createElement('input');
                    inputElement.type = details.votingType === 0 ? 'radio' : 'checkbox';
                    inputElement.name = 'voteOption';
                    inputElement.id = optionInputId;
                    inputElement.value = index;

                    const labelElement = document.createElement('label');
                    labelElement.htmlFor = optionInputId;
                    labelElement.textContent = optionText;

                    const divElement = document.createElement('div');
                    divElement.appendChild(inputElement);
                    divElement.appendChild(labelElement);

                    optionsListDiv.appendChild(divElement);
                });

                // Показати кнопку голосування, якщо вона знайдена і голосування не закрито
                if (voteButton && !details.isClosed) {
                    voteButton.style.display = 'block';

                    // Перевірка статусу Whitelist та чи користувач вже голосував, щоб активувати кнопку
                    // ЦЯ ПЕРЕВІРКА ПОВИННА БУТИ ТУТ!
                    const hasVoted = await contract.hasVoted(currentAccount); // Перевіряємо для поточного активного акаунта
                    const isWhitelisted = details.useWhitelist ? await contract.isWhitelisted(currentAccount) : true; // Перевіряємо Whitelist
                    const isVotingActive = (details.startTime === 0 || new Date() >= new Date(details.startTime * 1000)) &&
                                           (details.endTime === 0 || new Date() < new Date(details.endTime * 1000)) &&
                                           !details.isClosed;

                    if (hasVoted) {
                        voteButton.textContent = "You have already voted!";
                        voteButton.disabled = true;
                    } else if (!isWhitelisted) {
                        voteButton.textContent = "Not whitelisted!";
                        voteButton.disabled = true;
                    } else if (!isVotingActive) {
                        voteButton.textContent = "Voting not active!";
                        voteButton.disabled = true;
                    } else {
                        voteButton.textContent = "Submit Vote";
                        voteButton.disabled = false;
                    }
                } else if (voteButton) {
                    // Якщо голосування закрито, або кнопка не відображається
                    voteButton.textContent = "Voting is closed!";
                    voteButton.disabled = true;
                    voteButton.style.display = 'block'; // Показати, але вимкненою
                }


            } else {
                optionsListDiv.innerHTML += '<p>No voting options available.</p>';
            }
        }

    } catch (error) {
        console.error("Error fetching voting details:", error);
        if (votingDetailsDiv) votingDetailsDiv.innerHTML = '<h3>Error loading voting details.</h3>';
        if (optionsListDiv) optionsListDiv.innerHTML = '<p>Error loading options.</p>';
    }
}


// ==================== Функція для надсилання транзакції голосування ====================
async function submitVote() {
    console.log("SubmitVote function called.");

    if (!contract || !signer || !currentAccount) {
        console.error("Contract object, signer, or currentAccount not initialized. Cannot submit vote.");
        if (statusSpan) statusSpan.textContent = 'Error: Cannot submit vote - wallet not connected or contract not ready.';
        return;
    }
    if (!optionsListDiv) {
        console.error("Voting options UI element not found. Cannot get selected vote.");
        if (statusSpan) statusSpan.textContent = 'Error: Cannot submit vote - options UI missing.';
        return;
    }

    console.log("Attempting to collect selected options.");
    const selectedOptionIndices = [];
    const votingTypeEnum = votingTypeSpan.textContent === 'Single Choice' ? 0 : 1; // Отримуємо тип голосування з UI

    if (votingTypeEnum === 0) { // Single Choice
        const selectedRadio = optionsListDiv.querySelector('input[type="radio"]:checked');
        if (selectedRadio) {
            selectedOptionIndices.push(parseInt(selectedRadio.value));
        }
    } else { // Multiple Choice
        optionsListDiv.querySelectorAll('input[type="checkbox"]:checked').forEach(input => {
            selectedOptionIndices.push(parseInt(input.value));
        });
    }

    console.log("Finished collecting selected options. Selected indices:", selectedOptionIndices);

    if (selectedOptionIndices.length === 0) {
        console.warn("No voting options selected.");
        if (statusSpan) statusSpan.textContent = 'Please select at least one option.';
        return;
    }

    try {
        console.log(`Submitting vote from active account: ${currentAccount}`);
        console.log("Submitting vote with indices:", selectedOptionIndices);

        if (statusSpan) statusSpan.textContent = 'Submitting vote transaction...';
        if (voteButton) voteButton.disabled = true;

        const transactionResponse = await contract.vote(selectedOptionIndices);
        console.log("Vote transaction sent. Transaction hash:", transactionResponse.hash);

        if (statusSpan) statusSpan.textContent = `Transaction sent: ${transactionResponse.hash.substring(0, 6)}... Waiting for confirmation...`;

        console.log("Waiting for transaction confirmation for hash:", transactionResponse.hash);
        const receipt = await transactionResponse.wait();

        console.log("Transaction confirmed:", receipt);

        if (receipt && receipt.status === 1) {
            console.log("Vote transaction successful!");
            if (statusSpan) statusSpan.textContent = 'Vote successful!';
            if (voteButton) {
                voteButton.textContent = "Voted!";
                voteButton.disabled = true; // Вимкнути кнопку після успішного голосування
            }
            // Оновити стан UI, щоб відобразити, що користувач проголосував
            // Це може бути зроблено через повторний виклик fetchVotingDetails, який оновить стан кнопки
            await fetchVotingDetails(); // Перезавантажити деталі, щоб оновився статус кнопки
        } else {
            console.error("Vote transaction failed on chain!");
            if (statusSpan) statusSpan.textContent = 'Vote failed!';
        }
    } catch (error) {
        console.error("Error submitting vote:", error);
        if (statusSpan) {
            if (error.code === 4001) {
                statusSpan.textContent = 'Vote rejected by user.';
                console.log("Transaction rejected by user (MetaMask error code 4001).");
            } else {
                statusSpan.textContent = `Error submitting vote: ${error.message}`;
                console.error("An unexpected error occurred during vote submission:", error.message);
            }
        }
        if (voteButton) voteButton.disabled = false; // Знову активувати кнопку при помилці
    }
}


// ==================== TODO: Функції для отримання результатів ====================

async function fetchVotingResults() {
    console.log("Fetching voting results...");
    if (!contract || !resultsListDiv) {
        console.error("Contract object or resultsListDiv not initialized. Cannot fetch results.");
        if (resultsListDiv) resultsListDiv.innerHTML = '<p>Error: Results UI elements missing or contract not ready.</p>';
        return;
    }

    try {
        const results = await contract.getResults(); // Викликаємо getResults() з контракту
        const options = await contract.getOptionsList(); // Також отримуємо варіанти для відображення назв

        console.log("Voting Results:", results);
        console.log("Voting Options for results:", options);

        if (resultsListDiv) {
            resultsListDiv.innerHTML = '<h4>Current Results:</h4>';
            if (results && results.length === options.length) {
                const ul = document.createElement('ul');
                options.forEach((optionText, index) => {
                    const li = document.createElement('li');
                    li.textContent = `${optionText}: ${results[index]} votes`;
                    ul.appendChild(li);
                });
                resultsListDiv.appendChild(ul);
            } else {
                resultsListDiv.innerHTML += '<p>No results available yet or data mismatch.</p>';
            }
        }
        if (resultsSectionDiv) resultsSectionDiv.style.display = 'block'; // Показуємо секцію результатів
    } catch (error) {
        console.error("Error fetching results:", error);
        if (resultsListDiv) {
             let errorMessage = `Error fetching results: ${error.message}`;
             if (error.message.includes("Results are not available yet")) {
                 errorMessage = "Results are not available yet. Voting must be closed or ended by time.";
             }
             resultsListDiv.innerHTML = `<p>${errorMessage}</p>`;
        }
    }
}

// TODO: Цю функцію fetchVotingResults можна викликати:
// - Після закриття голосування
// - Після закінчення часу голосування
// - Кнопкою "Показати результати" на UI
// - Після успішного голосування (якщо потрібно одразу бачити оновлення, хоча може бути занадто рано для підрахунку на ланцюжку)