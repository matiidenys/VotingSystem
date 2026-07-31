const App = {
    provider: null,
    signer: null,
    userAddress: null,
    config: null,
    factoryContract: null,
    currentPollContract: null,

    // ID мережі Sepolia (11155111 decimal = 0xaa36a7 hex)
    REQUIRED_CHAIN_ID: '0xaa36a7',

    // --- ДОПОМІЖНА ФУНКЦІЯ ФОРМАТУВАННЯ ДАТИ ---
    formatDate: (timestamp) => {
        const ts = parseInt(timestamp.toString());
        if (ts === 0) return "∞ (Безстроково)";
        // undefined = використовувати налаштування браузера користувача
        return new Date(ts * 1000).toLocaleString(undefined, {
            year: 'numeric', month: 'numeric', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    },

    // --- 1. ІНІЦІАЛІЗАЦІЯ ---
    init: async () => {
        console.log("App initializing...");

        // Завантаження конфігурації
        try {
            const response = await fetch('/config');
            if (!response.ok) throw new Error("Server unavailable");
            App.config = await response.json();
            console.log("Config loaded:", App.config);
        } catch (e) {
            console.error(e);
            return alert("Помилка: Не вдалося отримати конфігурацію з бекенду.");
        }

        let isConnected = false;

        // Налаштування Web3
        if (window.ethereum) {
            App.provider = new ethers.providers.Web3Provider(window.ethereum);

            // Авто-перезавантаження
            window.ethereum.on('accountsChanged', () => window.location.reload());
            window.ethereum.on('chainChanged', () => window.location.reload());

            const accounts = await App.provider.listAccounts();
            if (accounts.length > 0) {
                await App.connectWallet();
                isConnected = true;
            }
        }

        // Прив'язка кнопок (з перевіркою на існування)
        const connectBtn = document.getElementById("connectBtn");
        if (connectBtn) connectBtn.addEventListener("click", App.connectWallet);

        const createForm = document.getElementById("createPollForm");
        if (createForm) createForm.addEventListener("submit", App.handleCreateSubmit);

        // Завантаження даних (Read-Only)
        if (!isConnected) {
            if (document.getElementById("pollsList")) App.loadPolls();
            if (document.getElementById("pollTitle")) App.loadPollDetails();
        }

        // Логіка сторінки голосування
        if (document.getElementById("pollTitle")) {
            const voteForm = document.getElementById("voteForm");
            if(voteForm) voteForm.addEventListener("submit", App.handleVoteSubmit);

            // Кнопки адміна
            document.getElementById("closeVotingBtn").addEventListener("click", () => App.adminAction("close"));

            const enableWlBtn = document.getElementById("enableWhitelistBtn");
            if(enableWlBtn) enableWlBtn.addEventListener("click", () => App.adminAction("enableWhitelist"));

            document.getElementById("addToWlBtn").addEventListener("click", () => App.adminAction("addWL"));
            document.getElementById("removeFromWlBtn").addEventListener("click", () => App.adminAction("removeWL"));

            const addRegBtn = document.getElementById("addRegistryBtn");
            if (addRegBtn) addRegBtn.addEventListener("click", () => App.adminAction("addRegistry"));

            const upTimeBtn = document.getElementById("updateTimeBtn");
            if (upTimeBtn) upTimeBtn.addEventListener("click", () => App.adminAction("updateTime"));

            // Перемикач Масового режиму
            const bulkToggle = document.getElementById("bulkModeToggle");
            const singleInput = document.getElementById("whitelistAddrInput");
            const bulkInput = document.getElementById("whitelistBulkInput");

            if (bulkToggle) {
                bulkToggle.addEventListener("change", (e) => {
                    if (e.target.checked) {
                        singleInput.style.display = "none";
                        bulkInput.style.display = "block";
                    } else {
                        singleInput.style.display = "block";
                        bulkInput.style.display = "none";
                    }
                });
            }
        }
    },

    // --- 2. ПЕРЕВІРКА МЕРЕЖІ ---
    checkNetwork: async () => {
        if (!window.ethereum) return false;
        const chainId = await window.ethereum.request({ method: 'eth_chainId' });

        if (chainId !== App.REQUIRED_CHAIN_ID) {
            try {
                await window.ethereum.request({
                    method: 'wallet_switchEthereumChain',
                    params: [{ chainId: App.REQUIRED_CHAIN_ID }],
                });
                return true;
            } catch (switchError) {
                alert("Будь ласка, переключіть мережу на Sepolia у MetaMask!");
                return false;
            }
        }
        return true;
    },

    // --- 3. ПІДКЛЮЧЕННЯ ГАМАНЦЯ ---
    connectWallet: async () => {
        if (!window.ethereum) return alert("MetaMask not found");

        const isCorrectNetwork = await App.checkNetwork();
        if (!isCorrectNetwork) return;

        try {
            await App.provider.send("eth_requestAccounts", []);
            App.signer = App.provider.getSigner();
            App.userAddress = await App.signer.getAddress();

            const shortAddr = `${App.userAddress.substring(0, 6)}...${App.userAddress.substring(38)}`;
            const badge = document.getElementById("walletInfo");
            if (badge) badge.innerText = shortAddr;

            const btn = document.getElementById("connectBtn");
            if (btn) btn.style.display = "none";

            App.factoryContract = new ethers.Contract(
                App.config.factoryAddress,
                App.config.factoryABI,
                App.signer
            );

            if (document.getElementById("pollsList")) await App.loadPolls();
            if (document.getElementById("pollTitle")) await App.loadPollDetails();

        } catch (err) {
            console.error("Connection error:", err);
        }
    },

    // --- 4. UI HELPERS ---
    showStatus: (elementId, type, message, txHash = null) => {
        const div = document.getElementById(elementId);
        if (!div) return;

        let explorerLink = txHash ? `<br><a href="https://sepolia.etherscan.io/tx/${txHash}" target="_blank" style="text-decoration:underline; font-weight:bold;">Дивитись на Etherscan ↗</a>` : "";
        let colorClass = "";
        let icon = "";

        if (type === "loading") {
            colorClass = "status-loading";
            icon = '<div class="loader"></div>';
        } else if (type === "success") {
            colorClass = "status-success";
            icon = "✅";
        } else if (type === "error") {
            colorClass = "status-error";
            icon = "❌";
        }

        div.innerHTML = `<div class="status-box ${colorClass}">${icon} ${message} ${explorerLink}</div>`;
    },

    showConfirm: (message) => {
        return new Promise((resolve) => {
            const modal = document.getElementById("customModal");
            const msgBox = document.getElementById("modalMessage");
            const yesBtn = document.getElementById("modalConfirmBtn");
            const noBtn = document.getElementById("modalCancelBtn");

            if (!modal) return resolve(confirm(message));

            msgBox.innerText = message;
            modal.style.display = "flex";

            const cleanup = () => {
                modal.style.display = "none";
                yesBtn.replaceWith(yesBtn.cloneNode(true));
                noBtn.replaceWith(noBtn.cloneNode(true));
            };

            const newYesBtn = document.getElementById("modalConfirmBtn");
            const newNoBtn = document.getElementById("modalCancelBtn");

            newYesBtn.addEventListener("click", () => { cleanup(); resolve(true); });
            newNoBtn.addEventListener("click", () => { cleanup(); resolve(false); });
        });
    },

    // --- 5. ЗАВАНТАЖЕННЯ СПИСКУ (index.html) ---
    loadPolls: async () => {
        const list = document.getElementById("pollsList");
        if (!list || list.getAttribute("data-loading") === "true") return;
        list.setAttribute("data-loading", "true");
        list.innerHTML = "Завантаження списку...";

        let contract = App.factoryContract;
        if (!contract && App.provider) {
            contract = new ethers.Contract(App.config.factoryAddress, App.config.factoryABI, App.provider);
        }

        if (!contract) return list.innerHTML = "Помилка ініціалізації контракту";

        try {
            const polls = await contract.getDeployedVotings();
            list.innerHTML = "";
            list.removeAttribute("data-loading");

            if (polls.length === 0) return list.innerHTML = "<div style='text-align:center; padding:40px; color:#666;'>Голосувань ще немає.</div>";

            const uniquePolls = [...new Set(polls)];

            for (let i = uniquePolls.length - 1; i >= 0; i--) {
                const addr = uniquePolls[i];
                const div = document.createElement("div");
                div.className = "poll-card";
                div.innerHTML = `<div><h3>Завантаження...</h3><small>${addr}</small></div>`;
                list.appendChild(div);

                const tempC = new ethers.Contract(addr, App.config.votingABI, App.provider);

                // Додаємо перевірку прав (якщо підключені)
                const promises = [
                    tempC.title(),
                    tempC.isClosed(),
                    tempC.startTime(),
                    tempC.endTime(),
                    tempC.useWhitelist()
                ];

                if (App.userAddress) {
                    promises.push(tempC.checkAccess(App.userAddress).catch(() => false));
                } else {
                    promises.push(Promise.resolve(false));
                }

                Promise.all(promises)
                .then(([title, isClosed, startBn, endBn, useWl, hasAccess]) => {

                    let accessBadge = "";
                    if (!useWl) {
                        accessBadge = `<span class="status-badge" style="background:#E0F2FE; color:#0369A1;">🌍 Публічне</span>`;
                    } else {
                        if (!App.userAddress) {
                            accessBadge = `<span class="status-badge" style="background:#F3F4F6; color:#6B7280;">🔒 Whitelist</span>`;
                        } else if (hasAccess) {
                            accessBadge = `<span class="status-badge" style="background:#DCFCE7; color:#15803D;">🔓 Доступ є</span>`;
                        } else {
                            accessBadge = `<span class="status-badge" style="background:#FEE2E2; color:#991B1B;">🚫 Немає доступу</span>`;
                        }
                    }

                    div.innerHTML = `
                        <div style="flex: 1;">
                            <div style="display:flex; align-items:center; gap:10px; margin-bottom:5px;">
                                <h3 style="margin:0;">${title}</h3>
                                ${accessBadge}
                            </div>
                            <small style="color:#888; display:block; margin-bottom: 8px;">${addr}</small>
                            
                            <div style="font-size: 13px; color: #555; display: flex; gap: 15px; flex-wrap: wrap;">
                                <span>🕒 Старт: <strong>${App.formatDate(startBn)}</strong></span>
                                <span>🏁 Кінець: <strong>${App.formatDate(endBn)}</strong></span>
                            </div>
                        </div>
                        <div style="text-align:right; display: flex; flex-direction: column; justify-content: space-between; align-items: flex-end; min-width: 100px;">
                            <span class="status-badge ${isClosed ? 'status-closed' : 'status-active'}">
                                ${isClosed ? 'Завершене' : 'Активне'}
                            </span>
                            <a href="poll.html?address=${addr}" style="margin-top: 15px;">
                                <button class="btn-primary" style="padding: 8px 15px; font-size: 13px;">Перейти</button>
                            </a>
                        </div>
                    `;
                })
                .catch(e => {
                    console.warn(e);
                    div.innerHTML = `<div><h3>Помилка читання</h3><small>${addr}</small></div>`;
                });
            }
        } catch (e) {
            console.error(e);
            list.innerHTML = "Помилка завантаження списку.";
        }
    },

    // --- 6. СТВОРЕННЯ (create.html) ---
    handleCreateSubmit: async (e) => {
        e.preventDefault();
        if (!App.factoryContract) return App.showStatus("createStatus", "error", "Підключіть гаманець!");

        const isCorrect = await App.checkNetwork();
        if (!isCorrect) return;

        const btn = e.target.querySelector("button[type='submit']");
        const statusId = "createStatus";
        btn.disabled = true;
        App.showStatus(statusId, "loading", "Валідація та підпис...");

        try {
            const title = document.getElementById("pollTitle").value;
            const options = Array.from(document.querySelectorAll(".poll-option")).map(i => i.value).filter(v => v.trim() !== "");
            if (options.length < 2) throw new Error("Мінімум 2 варіанти відповіді!");

            // Роздільне зчитування дати
            const startD = document.getElementById("startDate").value;
            const startT = document.getElementById("startTime").value || "00:00";
            const endD = document.getElementById("endDate").value;
            const endT = document.getElementById("endTime").value || "23:59";

            const combine = (d, t) => {
                if (!d) return 0;
                const dateObj = new Date(`${d}T${t}`);
                if (isNaN(dateObj.getTime())) throw new Error("Некоректна дата");
                return Math.floor(dateObj.getTime() / 1000);
            };

            const sTime = combine(startD, startT);
            const eTime = combine(endD, endT);

            const now = Math.floor(Date.now() / 1000);
            if (eTime !== 0 && sTime !== 0 && eTime <= sTime) throw new Error("Час завершення має бути пізніше часу початку!");
            if (eTime !== 0 && eTime <= now) throw new Error("Час завершення має бути у майбутньому!");

            const vType = parseInt(document.getElementById("votingType").value);
            const useWl = document.getElementById("useWhitelist").checked;

            App.showStatus(statusId, "loading", "Відкрийте MetaMask для підпису...");

            const tx = await App.factoryContract.createVoting(title, options, sTime, eTime, useWl, vType);

            App.showStatus(statusId, "loading", "Транзакцію відправлено! Створюємо блок...", tx.hash);
            await tx.wait();

            App.showStatus(statusId, "success", "Голосування успішно створено!", tx.hash);
            setTimeout(() => window.location.href = "index.html", 2000);

        } catch (err) {
            App.showStatus(statusId, "error", err.reason || err.message);
            btn.disabled = false;
        }
    },

    // --- 7. ДЕТАЛІ ГОЛОСУВАННЯ (poll.html) ---
    loadPollDetails: async () => {
        const container = document.getElementById("pollInfoSection");
        if (!container || container.getAttribute("data-loading") === "true") return;
        container.setAttribute("data-loading", "true");

        const params = new URLSearchParams(window.location.search);
        const address = params.get("address");

        if (!address || !ethers.utils.isAddress(address)) {
            document.getElementById("pollTitle").innerText = "Голосування не знайдено";
            return;
        }

        const providerOrSigner = App.signer || App.provider;
        if (!providerOrSigner) return;

        App.currentPollContract = new ethers.Contract(address, App.config.votingABI, providerOrSigner);
        const poll = App.currentPollContract;

        try {
            const [title, organizer, isClosed, useWhitelist, options, results, votingType, registries, startTime, endTime] = await Promise.all([
                poll.title(), poll.organizer(), poll.isClosed(), poll.useWhitelist(),
                poll.getOptions(), poll.getResults(), poll.votingType(), poll.getRegistries(),
                poll.startTime(), poll.endTime()
            ]);

            // 1. Шапка
            document.getElementById("pollTitle").innerText = title;
            document.getElementById("organizerAddr").innerText = organizer;
            document.getElementById("displayStartTime").innerText = App.formatDate(startTime);
            document.getElementById("displayEndTime").innerText = App.formatDate(endTime);

            const statusSpan = document.getElementById("pollStatus");
            statusSpan.innerText = isClosed ? "Завершене" : "Активне";
            statusSpan.className = `status-badge ${isClosed ? 'status-closed' : 'status-active'}`;

            const wlStatus = document.getElementById("whitelistStatus");
            if (useWhitelist) {
                wlStatus.style.display = "inline-block";
                wlStatus.innerText = "Whitelist Only";
            } else {
                wlStatus.style.display = "none";
            }

            // 2. UI Логіка (Доступ)
            const voteForm = document.getElementById("voteForm");
            const hasVotedMsg = document.getElementById("hasVotedMsg");
            const pollClosedMsg = document.getElementById("pollClosedMsg");
            const notWhitelistedMsg = document.getElementById("notWhitelistedMsg");

            voteForm.style.display = "block";
            hasVotedMsg.style.display = "none";
            pollClosedMsg.style.display = "none";
            if(notWhitelistedMsg) notWhitelistedMsg.style.display = "none";

            let canVote = true;

            if (useWhitelist && App.userAddress) {
                try {
                    const isAllowed = await poll.checkAccess(App.userAddress);
                    if (!isAllowed) {
                        canVote = false;
                        if(notWhitelistedMsg) notWhitelistedMsg.style.display = "block";
                        voteForm.style.display = "none";
                    }
                } catch (err) { console.error(err); }
            }

            if (canVote) {
                if (isClosed) {
                    voteForm.style.display = "none";
                    pollClosedMsg.style.display = "block";
                }
                else if (App.userAddress) {
                    const hasVoted = await poll.hasVoted(App.userAddress);
                    if (hasVoted) {
                        voteForm.style.display = "none";
                        hasVotedMsg.style.display = "block";
                    }
                }
            }

            // 3. Адмін-панель
            const adminPanel = document.getElementById("adminPanel");
            if (App.userAddress && App.userAddress.toLowerCase() === organizer.toLowerCase()) {
                adminPanel.style.display = "block";

                const closeBtn = document.getElementById("closeVotingBtn");
                const enableWlBtn = document.getElementById("enableWhitelistBtn");
                const addWlBtn = document.getElementById("addToWlBtn");
                const removeWlBtn = document.getElementById("removeFromWlBtn");
                const addRegBtn = document.getElementById("addRegistryBtn");
                const upTimeBtn = document.getElementById("updateTimeBtn");

                const wlInput = document.getElementById("whitelistAddrInput");
                const bulkInput = document.getElementById("whitelistBulkInput");
                const regInput = document.getElementById("registryAddrInput");

                // Статус Whitelist
                const hintText = document.getElementById("whitelistStatusHint");
                if (useWhitelist) {
                    hintText.innerHTML = `<span style="color:green;">✅ АКТИВНИЙ (Доступ обмежено)</span>`;
                } else {
                    hintText.innerHTML = `<span style="color:gray;">⚪ НЕАКТИВНИЙ (Голосують всі)</span>`;
                }

                // Список реєстрів
                const regListDiv = document.getElementById("connectedRegistriesList");
                if (registries && registries.length > 0) {
                    regListDiv.innerHTML = "<strong>Підключені реєстри:</strong><br>" + registries.map(r => `• <small>${r}</small>`).join("<br>");
                } else {
                    regListDiv.innerHTML = "<em>Немає підключених зовнішніх реєстрів.</em>";
                }

                // Блокування кнопок
                if (isClosed) {
                    [closeBtn, enableWlBtn, addWlBtn, removeWlBtn, addRegBtn, upTimeBtn].forEach(b => { if(b) { b.disabled=true; b.style.background="gray"; b.style.cursor="not-allowed"; } });
                    if(wlInput) wlInput.disabled = true;
                    if(bulkInput) bulkInput.disabled = true;
                    if(regInput) regInput.disabled = true;
                    closeBtn.innerText = "Вже закрито";
                } else {
                    [closeBtn, addWlBtn, removeWlBtn, addRegBtn, upTimeBtn].forEach(b => { if(b) { b.disabled=false; b.style.background=""; b.style.cursor="pointer"; } });
                    if(wlInput) wlInput.disabled = false;
                    if(bulkInput) bulkInput.disabled = false;
                    if(regInput) regInput.disabled = false;
                    closeBtn.innerText = "Закрити голосування";

                    // Enable Whitelist кнопка
                    if (useWhitelist) {
                        enableWlBtn.disabled = true;
                        enableWlBtn.style.background = "gray";
                        enableWlBtn.style.cursor = "not-allowed";
                        enableWlBtn.innerText = "Whitelist активний";
                    } else {
                        enableWlBtn.disabled = false;
                        enableWlBtn.style.background = "#FF9800";
                        enableWlBtn.style.cursor = "pointer";
                        enableWlBtn.innerText = "Увімкнути Whitelist";
                    }
                }
            } else {
                adminPanel.style.display = "none";
            }

            // 4. Генерація варіантів
            const optionsContainer = document.getElementById("optionsContainer");
            optionsContainer.innerHTML = "";
            const inputType = (votingType === 0) ? "radio" : "checkbox";
            options.forEach((opt, index) => {
                const div = document.createElement("div");
                div.innerHTML = `<label style="cursor:pointer; display:flex; padding:10px; border-bottom:1px solid #eee;">
                    <input type="${inputType}" name="pollOption" value="${index}" style="margin-right:10px;"> ${opt}
                </label>`;
                optionsContainer.appendChild(div);
            });

            // 5. Результати
            const resultsDiv = document.getElementById("resultsChart");
            resultsDiv.innerHTML = "";
            let totalVotes = 0;
            const simpleResults = results.map(r => { const n = parseInt(r.toString()); totalVotes += n; return n; });

            options.forEach((opt, index) => {
                const count = simpleResults[index];
                const percent = totalVotes > 0 ? ((count / totalVotes) * 100).toFixed(1) : 0;
                resultsDiv.innerHTML += `
                    <div style="margin-bottom:15px;">
                        <div style="display:flex; justify-content:space-between;">
                            <strong>${opt}</strong>
                            <span>${count} (${percent}%)</span>
                        </div>
                        <div style="background:#eee; height:10px; border-radius:5px; overflow:hidden;">
                            <div style="background:#4CAF50; height:100%; width:${percent}%"></div>
                        </div>
                    </div>`;
            });

            container.removeAttribute("data-loading");

        } catch (e) {
            console.error(e);
            document.getElementById("pollTitle").innerText = "Помилка завантаження даних";
        }
    },

    // --- 8. ВІДПРАВКА ГОЛОСУ ---
    handleVoteSubmit: async (e) => {
        e.preventDefault();
        if (!App.currentPollContract) return;

        const isCorrect = await App.checkNetwork();
        if (!isCorrect) return;

        const checkboxes = document.querySelectorAll('input[name="pollOption"]:checked');
        const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.value));
        if (selectedIndices.length === 0) return App.showStatus("txStatus", "error", "Оберіть варіант!");

        const btn = document.getElementById("voteBtn");
        const statusId = "txStatus";

        btn.disabled = true;
        App.showStatus(statusId, "loading", "Підписуємо транзакцію...");

        try {
            const tx = await App.currentPollContract.vote(selectedIndices);
            App.showStatus(statusId, "loading", "Транзакцію відправлено! Очікуйте...", tx.hash);

            await tx.wait();

            App.showStatus(statusId, "success", "Голос зараховано!", tx.hash);
            await App.loadPollDetails();

        } catch (err) {
            App.showStatus(statusId, "error", err.reason || err.message);
            btn.disabled = false;
        }
    },

    // --- 9. АДМІН ДІЇ ---
    adminAction: async (actionType) => {
        if (!App.currentPollContract) return;

        const isCorrect = await App.checkNetwork();
        if (!isCorrect) return;

        // Визначаємо ID для помилок (щоб було під полем)
        let statusId = "adminStatus";
        if (actionType === "addWL" || actionType === "removeWL") statusId = "whitelistStatusMsg";
        else if (actionType === "addRegistry") statusId = "registryStatusMsg";

        // Очищаємо старі повідомлення
        ["adminStatus", "whitelistStatusMsg", "registryStatusMsg"].forEach(id => {
            const el = document.getElementById(id); if(el) el.innerHTML="";
        });

        App.showStatus(statusId, "loading", "Обробка запиту...");

        try {
            let tx;

            // --- ЗАКРИТТЯ ---
            if (actionType === "close") {
                const ok = await App.showConfirm("Ви впевнені, що хочете закрити голосування?\n\nУВАГА: Цю дію неможливо скасувати. Прийом голосів буде зупинено назавжди.");
                if (!ok) return App.showStatus(statusId, "", "");
                tx = await App.currentPollContract.closeVoting();
            }
            // --- ENABLE WHITELIST ---
            else if (actionType === "enableWhitelist") {
                const ok = await App.showConfirm("Увімкнути Whitelist?\n\nУВАГА: Цю дію неможливо скасувати. Після ввімкнення голосування стане приватним.");
                if (!ok) return App.showStatus(statusId, "", "");
                tx = await App.currentPollContract.enableWhitelist();
            }
            // --- ADD/REMOVE WHITELIST (SINGLE & BULK) ---
            else if (actionType === "addWL" || actionType === "removeWL") {
                const isBulk = document.getElementById("bulkModeToggle").checked;

                if (isBulk) {
                    // Масовий режим
                    const rawText = document.getElementById("whitelistBulkInput").value;
                    const addresses = rawText.split(/[\n, ]+/).map(s => s.trim()).filter(s => s !== "");

                    if (addresses.length === 0) throw new Error("Список адрес пустий!");

                    // Перевірка валідності
                    const invalidAddr = addresses.find(a => !ethers.utils.isAddress(a));
                    if (invalidAddr) throw new Error(`Невірна адреса: ${invalidAddr}`);

                    const opName = actionType === "addWL" ? "додавання" : "видалення";
                    const ok = await App.showConfirm(`Виконати ${opName} для ${addresses.length} адрес?`);
                    if (!ok) return App.showStatus(statusId, "", "");

                    if (actionType === "addWL") tx = await App.currentPollContract.addManyToWhitelist(addresses);
                    else tx = await App.currentPollContract.removeManyFromWhitelist(addresses);

                } else {
                    // Одинарний режим
                    const addr = document.getElementById("whitelistAddrInput").value.trim();
                    if (!addr) throw new Error("Введіть адресу!");
                    if (!ethers.utils.isAddress(addr)) throw new Error("Невірна адреса");

                    if (actionType === "addWL") tx = await App.currentPollContract.addToWhitelist(addr);
                    else tx = await App.currentPollContract.removeFromWhitelist(addr);
                }
            }
            // --- ADD REGISTRY ---
            else if (actionType === "addRegistry") {
                const addr = document.getElementById("registryAddrInput").value.trim();
                if (!addr) throw new Error("Введіть адресу контракту!");
                if (!ethers.utils.isAddress(addr)) throw new Error("Невірна адреса");

                const ok = await App.showConfirm(`Підключити зовнішній реєстр?\nЦе автоматично увімкне Whitelist.`);
                if (!ok) return App.showStatus(statusId, "", "");

                tx = await App.currentPollContract.addRegistry(addr);
            }
            // --- UPDATE TIME ---
            else if (actionType === "updateTime") {
                const startDateVal = document.getElementById("newStartDate").value;
                const startTimeVal = document.getElementById("newStartTime").value || "00:00";
                const endDateVal = document.getElementById("newEndDate").value;
                const endTimeVal = document.getElementById("newEndTime").value || "23:59";

                const combineToTimestamp = (dateStr, timeStr) => {
                    if (!dateStr) return 0;
                    const fullString = `${dateStr}T${timeStr}`;
                    const d = new Date(fullString);
                    if (isNaN(d.getTime())) throw new Error("Некоректна дата");
                    return Math.floor(d.getTime() / 1000);
                };

                const sTime = combineToTimestamp(startDateVal, startTimeVal);
                const eTime = combineToTimestamp(endDateVal, endTimeVal);

                if (eTime !== 0) {
                    const now = Math.floor(Date.now() / 1000);
                    if (eTime <= now) throw new Error("Час завершення має бути у майбутньому!");
                    if (sTime !== 0 && eTime <= sTime) throw new Error("Час завершення має бути пізніше початку!");
                }

                const msg = `Оновити час?\n\nПочаток: ${App.formatDate(sTime)}\nКінець: ${App.formatDate(eTime)}`;
                const ok = await App.showConfirm(msg);
                if (!ok) return App.showStatus(statusId, "", "");

                tx = await App.currentPollContract.updateVotingPeriod(sTime, eTime);
            }

            App.showStatus(statusId, "loading", "Відправлено в мережу...", tx.hash);
            await tx.wait();

            // Очищаємо поля після успіху
            if (actionType.includes("WL")) {
                document.getElementById("whitelistAddrInput").value = "";
                document.getElementById("whitelistBulkInput").value = "";
            }
            if (actionType === "addRegistry") document.getElementById("registryAddrInput").value = "";

            App.showStatus(statusId, "success", "Успішно виконано!", tx.hash);
            await App.loadPollDetails();

        } catch (err) {
            App.showStatus(statusId, "error", err.reason || err.message);
        }
    }
};

window.addEventListener('DOMContentLoaded', App.init);