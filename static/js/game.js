// GrandMaster Chess - COMPLETE FEATURE-RICH VERSION
// Features: Online counter, Queue, Chat, Theme toggle, Sounds, Analysis, Email verification

let gameId = null;
let gameMode = null;
let selectedMode = null;
let difficulty = 15;
let selectedSquare = null;
let validMoves = [];
let boardState = null;
let isWhiteTurn = true;
let isAIThinking = false;
let boardFlipped = false;
let draggedPiece = null;
let dragFrom = null;
let lastMoveSquares = [];

// Clock variables
let whiteTime = 600;
let blackTime = 600;
let currentIncrement = 0;
let clockInterval = null;
let lastUpdateTime = Date.now();
let clocksEnabled = true;
let selectedTimeControl = '10+0';

// Player info
let whitePlayerName = 'White';
let blackPlayerName = 'Black';
let whiteRating = 1500;
let blackRating = 1500;

// Analysis mode
let isAnalysisMode = false;
let currentMoveIndex = 0;
let totalMoves = 0;
let isGameComplete = false;
let gameAnalysis = null;

// Online multiplayer
let socket = null;
let isOnlineGame = false;
let myColor = null;
let isMyTurn = false;
let inQueue = false;
let currentUser = null;
let onlinePlayerCount = 0;
let queuePosition = 0;

// Chat
let chatMessages = [];
let unreadMessages = 0;
let isChatOpen = false;

// Theme
let currentTheme = localStorage.getItem('theme') || 'dark';

// Sounds
let soundEnabled = localStorage.getItem('soundEnabled') !== 'false';

// ============================================================================
// PROFESSIONAL CHESS SOUND ENGINE
// Modelled after real wooden piece acoustics — dry, short, subtle.
// ============================================================================
let audioCtx = null;
function getAudioCtx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
}

/**
 * Core primitive: synthesise a wooden piece impact.
 * Real wood contact sound = broadband noise (the attack transient)
 * + a fast-decaying lowpass body. Duration: 40-80ms. Zero reverb.
 *
 * @param {number} vol        - overall gain (0-1)
 * @param {number} bodyFreq   - lowpass cutoff (Hz) for wood resonance
 * @param {number} decayMs    - total length in milliseconds
 * @param {number} delayS     - schedule offset from ctx.currentTime
 */
function woodImpact(vol, bodyFreq, decayMs, delayS = 0) {
    const ctx = getAudioCtx();
    const t = ctx.currentTime + delayS;
    const decayS = decayMs / 1000;
    const sr = ctx.sampleRate;

    // -- Noise source (the broadband transient)
    const frames = Math.ceil(sr * decayS);
    const noiseBuf = ctx.createBuffer(1, frames, sr);
    const nd = noiseBuf.getChannelData(0);
    for (let i = 0; i < frames; i++) nd[i] = Math.random() * 2 - 1;

    const noiseNode = ctx.createBufferSource();
    noiseNode.buffer = noiseBuf;

    // -- Two-stage filter: highpass strips sub-bass rumble, lowpass gives wood body
    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = 80;

    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = bodyFreq;
    lp.Q.value = 0.8;

    // -- Gain envelope: sharp attack, exponential decay
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(vol, t + 0.001);        // 1ms attack
    env.gain.exponentialRampToValueAtTime(0.001, t + decayS); // decay

    noiseNode.connect(hp);
    hp.connect(lp);
    lp.connect(env);
    env.connect(ctx.destination);
    noiseNode.start(t);
    noiseNode.stop(t + decayS + 0.002);
}

/**
 * Clean sine-bell tone for UI notifications.
 * Single frequency with natural exponential decay — no wobble.
 */
function bellTone(freq, vol, decayS, delayS = 0) {
    const ctx = getAudioCtx();
    const t = ctx.currentTime + delayS;

    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = freq;

    const env = ctx.createGain();
    env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(vol, t + 0.003);
    env.gain.exponentialRampToValueAtTime(0.001, t + decayS);

    // Subtle high-cut to keep it warm, not piercing
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = freq * 3;

    osc.connect(filter);
    filter.connect(env);
    env.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + decayS + 0.01);
}

const sounds = {
    /**
     * MOVE — A crisp, dry wooden tap.
     * Modelled as a piece placed firmly on a board square.
     * ~50ms, medium frequency wood body. Quiet.
     */
    move: () => {
        woodImpact(0.55, 2200, 50);
        // Subtle low-end body thud underneath
        woodImpact(0.25, 180, 45);
    },

    /**
     * CAPTURE — Heavier impact, slightly longer sustain.
     * Two overlapping impacts: the capturing piece being placed,
     * and the captured piece "leaving" (softer second hit).
     */
    capture: () => {
        woodImpact(0.75, 2000, 65);          // main impact
        woodImpact(0.35, 150, 55);           // low body
        woodImpact(0.20, 3500, 30, 0.025);  // high click of removal
    },

    /**
     * CHECK — A clean, round notification tone.
     * Two soft bell notes, the second slightly lower (tension).
     * Sounds like Lichess's check sound — understated but clear.
     */
    check: () => {
        bellTone(1046, 0.22, 0.55);          // C6
        bellTone(880, 0.16, 0.45, 0.18);    // A5 (slightly unsettled interval)
    },

    /**
     * GAME START — A gentle ascending two-note chime.
     * Clean, professional — like a meeting starting.
     */
    gameStart: () => {
        bellTone(659, 0.20, 0.5, 0.0);   // E5
        bellTone(1046, 0.18, 0.7, 0.18);  // C6 (perfect 4th up)
    },

    /**
     * GAME END — A soft descending closure chime.
     * Resolved, final — like a door closing.
     */
    gameEnd: () => {
        bellTone(880, 0.20, 0.5, 0.0);   // A5
        bellTone(698, 0.18, 0.6, 0.2);   // F5
        bellTone(523, 0.16, 0.9, 0.42);  // C5 (final resolution)
    },

    /**
     * BUTTON CLICK — Almost inaudible. A tiny 8ms tap.
     * Should feel like a physical key press, not a sound effect.
     */
    btnClick: () => {
        woodImpact(0.18, 4000, 18);
    }
};

const PIECES = {
    'wK': '♔', 'wQ': '♕', 'wR': '♖', 'wB': '♗', 'wN': '♘', 'wp': '♙',
    'bK': '♚', 'bQ': '♛', 'bR': '♜', 'bB': '♝', 'bN': '♞', 'bp': '♟'
};

let pendingPromotion = null;

function completePromotion(choice) {
    document.getElementById('promotion-modal').style.display = 'none';
    if (pendingPromotion) {
        if (isOnlineGame) {
            sendOnlineMove(pendingPromotion.from, pendingPromotion.to, choice);
        } else {
            makeMove(pendingPromotion.from, pendingPromotion.to, choice);
        }
        pendingPromotion = null;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('difficulty-slider');
    if (slider) {
        slider.addEventListener('input', updateDifficultyDisplay);
    }

    document.addEventListener('keydown', handleKeyPress);

    initializeSocketIO();
    checkAuthStatus();
    applyTheme(currentTheme);
    initializeSoundControls();
    initializeTimeControls();
});

// Mobile touch improvements
document.addEventListener("touchstart", function () { }, true);

// Prevent double zoom on mobile
document.addEventListener("dblclick", function (e) {
    e.preventDefault();
}, { passive: false });

function handleKeyPress(event) {
    if (!isAnalysisMode) return;

    if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goToPrevious();
    } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        goToNext();
    } else if (event.key === 'Home') {
        event.preventDefault();
        goToFirst();
    } else if (event.key === 'End') {
        event.preventDefault();
        goToLast();
    }
}

// ============================================================================
// THEME SYSTEM
// ============================================================================

function applyTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
}

function toggleTheme() {
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
}

// ============================================================================
// SOUND SYSTEM
// ============================================================================

function initializeSoundControls() {
    const soundBtn = document.getElementById('sound-toggle-btn');
    if (soundBtn) {
        soundBtn.textContent = soundEnabled ? '🔊 Sound On' : '🔇 Sound Off';
    }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    localStorage.setItem('soundEnabled', soundEnabled);
    const soundBtn = document.getElementById('sound-toggle-btn');
    if (soundBtn) {
        soundBtn.textContent = soundEnabled ? '🔊 Sound On' : '🔇 Sound Off';
    }
    showToast(soundEnabled ? 'Sound enabled' : 'Sound disabled');
}

function playSound(soundName) {
    if (!soundEnabled || !sounds[soundName]) return;
    try { sounds[soundName](); } catch (e) { console.log('Sound error:', e); }
}

// ============================================================================
// TIME CONTROLS
// ============================================================================

function initializeTimeControls() {
    const timeControls = ['1+0', '3+0', '3+2', '5+0', '10+0', '15+10', '30+0'];
    const selector = document.getElementById('time-control-selector');

    if (selector) {
        selector.innerHTML = timeControls.map(tc =>
            `<option value="${tc}" ${tc === '10+0' ? 'selected' : ''}>${tc}</option>`
        ).join('');

        selector.addEventListener('change', (e) => {
            selectedTimeControl = e.target.value;
        });
    }
}

function parseTimeControl(tc) {
    const [minutes, increment] = tc.split('+').map(Number);
    return {
        initialTime: minutes * 60,
        increment: increment
    };
}

// ============================================================================
// AUTHENTICATION
// ============================================================================

async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/me');
        const data = await response.json();

        if (data.success) {
            currentUser = data.user;
            updateUIForLoggedInUser(currentUser);
        } else {
            currentUser = null;
            updateUIForGuest();
        }
    } catch (error) {
        console.log('Not logged in');
        currentUser = null;
        updateUIForGuest();
    }
}

function updateUIForLoggedInUser(user) {
    const profileBtn = document.querySelector('.profile-btn');
    if (profileBtn) {
        profileBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M11 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0"/>
                <path fill-rule="evenodd" d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8m8-7a7 7 0 0 0-5.468 11.37C3.242 11.226 4.805 10 8 10s4.757 1.225 5.468 2.37A7 7 0 0 0 8 1"/>
            </svg>
            ${user.username} (${user.rating})
        `;
        profileBtn.onclick = showProfileMenu;
    }

    // Show online indicator
    updateOnlineStatus(true);
}

function updateUIForGuest() {
    const profileBtn = document.querySelector('.profile-btn');
    if (profileBtn) {
        profileBtn.onclick = () => window.location.href = '/auth';
    }
}

function showProfileMenu() {
    const menu = `
        <div class="profile-dropdown">
            <button onclick="viewProfile()">👤 Profile</button>
            <button onclick="viewStats()">📊 Stats</button>
            <button onclick="viewHistory()">📜 History</button>
            <button onclick="toggleTheme()">🎨 Toggle Theme</button>
            <button onclick="toggleSound()">🔊 Toggle Sound</button>
            <button onclick="logout()">🚪 Logout</button>
        </div>
    `;
    // Implementation depends on your UI
    if (confirm('Logout?')) {
        logout();
    }
}

function viewProfile() {
    if (currentUser) {
        window.location.href = `/profile/${currentUser.username}`;
    }
}

function viewStats() {
    showToast('Stats feature coming soon!');
}

function viewHistory() {
    showToast('History feature coming soon!');
}

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/auth';
    } catch (error) {
        console.error('Logout error:', error);
    }
}

// ============================================================================
// SOCKET.IO - REAL-TIME MULTIPLAYER
// ============================================================================

function initializeSocketIO() {
    socket = io({
        transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
        console.log('✅ Connected to server');
        socket.emit('get_online_count');
    });

    socket.on('disconnect', () => {
        console.log('❌ Disconnected from server');
        if (inQueue) {
            inQueue = false;
            showToast('Disconnected from matchmaking');
        }
        updateOnlineStatus(false);
    });

    socket.on('online_count', (data) => {
        onlinePlayerCount = data.count;
        updateOnlineCounter(data.count);
    });

    socket.on('queue_joined', (data) => {
        console.log('🔍 In matchmaking queue');
        showToast('Searching for opponent...');
        updateQueueUI(true);
    });

    socket.on('queue_position', (data) => {
        queuePosition = data.position;
        updateQueuePosition(data.position, data.total);
    });

    socket.on('game_found', (data) => {
        console.log('🎮 Game found!', data);
        inQueue = false;
        updateQueueUI(false);
        playSound('gameStart');
        startOnlineGame(data);
    });

    socket.on('opponent_move', (data) => {
        handleOpponentMove(data);
    });

    socket.on('chat_message', (data) => {
        receiveChatMessage(data);
    });

    socket.on('game_end', (data) => {
        handleGameEnd(data);
    });

    socket.on('draw_offered', (data) => {
        const modal = document.getElementById('draw-modal');
        const text = document.getElementById('draw-offer-text');
        text.textContent = `${data.offered_by} offers a draw.`;
        modal.style.display = 'flex';
        playSound('check'); // Reuse check sound for attention
    });

    socket.on('draw_declined', (data) => {
        showToast(`${data.declined_by} declined the draw offer.`);
    });

    socket.on('error', (data) => {
        console.error('Socket error:', data);
        showToast(data.message || 'An error occurred');
    });
}

function updateOnlineCounter(count) {
    const counter = document.getElementById('online-counter');
    if (counter) {
        counter.textContent = `🟢 ${count} online`;
        counter.style.display = 'block';
    }
}

function updateOnlineStatus(isOnline) {
    const statusIndicator = document.getElementById('status-indicator');
    if (statusIndicator) {
        statusIndicator.className = isOnline ? 'status-online' : 'status-offline';
    }
}

function updateQueueUI(inQueue) {
    const queueIndicator = document.getElementById('queue-indicator');
    if (queueIndicator) {
        if (inQueue) {
            queueIndicator.innerHTML = `
                <div class="queue-searching">
                    <div class="spinner-small"></div>
                    <span>Searching for opponent...</span>
                </div>
            `;
            queueIndicator.style.display = 'block';
        } else {
            queueIndicator.style.display = 'none';
        }
    }
}

function updateQueuePosition(position, total) {
    const queueIndicator = document.getElementById('queue-indicator');
    if (queueIndicator && position > 0) {
        queueIndicator.innerHTML = `
            <div class="queue-info">
                Queue position: ${position} of ${total}
            </div>
        `;
    }
}

// ============================================================================
// TIME CONTROL MODALS
// ============================================================================

let selectedOnlineTC = '10+0';
let selectedPvPTC = '10+0';

function showOnlineTimeControl() {
    playSound('btnClick');
    const modal = document.getElementById('online-tc-modal');
    if (modal) { modal.style.display = 'flex'; }
}

function closeOnlineTC() {
    const modal = document.getElementById('online-tc-modal');
    if (modal) modal.style.display = 'none';
}

function selectOnlineTC(tc, el) {
    playSound('btnClick');
    selectedOnlineTC = tc;
    selectedTimeControl = tc;
    // Reset all cards
    document.querySelectorAll('#online-tc-modal .tc-card').forEach(c => {
        c.classList.remove('tc-selected');
        c.style.borderColor = '#3f3f46';
        c.style.background = 'transparent';
    });
    el.classList.add('tc-selected');
    el.style.borderColor = 'rgba(255,45,120,0.8)';
    el.style.background = 'rgba(255,45,120,0.1)';
}

function confirmOnlineMatch() {
    playSound('btnClick');
    closeOnlineTC();
    joinMatchmaking();
}

function showPvPTimeControl() {
    playSound('btnClick');
    const modal = document.getElementById('pvp-tc-modal');
    if (modal) { modal.style.display = 'flex'; }
}

function closePvPTC() {
    const modal = document.getElementById('pvp-tc-modal');
    if (modal) modal.style.display = 'none';
}

function selectPvPTC(tc, el) {
    playSound('btnClick');
    selectedPvPTC = tc;
    selectedTimeControl = tc;
    document.querySelectorAll('#pvp-tc-modal .tc-card').forEach(c => {
        c.classList.remove('tc-selected-pvp');
        c.style.borderColor = '#3f3f46';
        c.style.background = 'transparent';
    });
    el.classList.add('tc-selected-pvp');
    el.style.borderColor = 'rgba(57,255,20,0.8)';
    el.style.background = 'rgba(57,255,20,0.08)';
}

function confirmPvPGame() {
    playSound('btnClick');
    closePvPTC();
    startGame('pvp');
}

function confirmPvPMatch() {
    confirmPvPGame();
}

function joinMatchmaking() {
    if (!currentUser) {
        alert('Please login to play online!');
        window.location.href = '/auth';
        return;
    }

    if (inQueue) {
        socket.emit('leave_queue');
        inQueue = false;
        updateQueueUI(false);
        showToast('Left matchmaking queue');
        return;
    }

    inQueue = true;
    socket.emit('join_queue', {
        time_control: selectedTimeControl,
        game_type: 'rated'
    });
}

function startOnlineGame(data) {
    gameId = data.game_id;
    myColor = data.color;
    isOnlineGame = true;
    gameMode = 'online';
    boardState = data.board;
    isWhiteTurn = true;

    boardFlipped = (myColor === 'black');

    if (myColor === 'white') {
        whitePlayerName = currentUser.username;
        whiteRating = currentUser.rating;
        blackPlayerName = data.opponent.username;
        blackRating = data.opponent.rating;
    } else {
        blackPlayerName = currentUser.username;
        blackRating = currentUser.rating;
        whitePlayerName = data.opponent.username;
        whiteRating = data.opponent.rating;
    }

    isMyTurn = (myColor === 'white');

    // Parse time control
    const timeConfig = parseTimeControl(data.time_control || selectedTimeControl);
    whiteTime = timeConfig.initialTime;
    blackTime = timeConfig.initialTime;
    currentIncrement = timeConfig.increment;
    clocksEnabled = true;

    document.getElementById('game-setup').style.display = 'none';
    document.getElementById('game-area').style.display = 'flex';
    document.getElementById('hamburger-menu').style.display = 'block';
    document.body.classList.add('playing');

    // Show chat interface
    initializeChatUI();

    updatePlayerCards();
    updateGameModeDisplay();
    renderBoard();
    updateCoordinates();
    updateTurnIndicator();
    startClock();

    playSound('gameStart');
    showToast(`Game started! You are ${myColor}.`);
}

function sendOnlineMove(from, to, promotion = 'Q') {
    socket.emit('online_move', {
        game_id: gameId,
        move: { from, to, promotion }
    });
}

function handleOpponentMove(data) {
    // Apply increment to opponent who just moved (before turn flips)
    if (clocksEnabled && currentIncrement > 0) {
        if (isWhiteTurn) whiteTime += currentIncrement;
        else blackTime += currentIncrement;
        updateClockDisplay();
    }

    if (data.move) {
        lastMoveSquares = [data.move.from, data.move.to];
        animatePieceLocally(data.move.from, data.move.to).then(() => {
            boardState = data.board;
            isWhiteTurn = data.whiteToMove;
            isMyTurn = (myColor === 'white') === isWhiteTurn;
            totalMoves++;

            addMove(data.move, totalMoves - 1);

            // Play appropriate sound
            if (data.checkmate || data.stalemate) {
                playSound('gameEnd');
            } else if (data.inCheck) {
                playSound('check');
            } else if (data.move.notation && data.move.notation.includes('x')) {
                playSound('capture');
            } else {
                playSound('move');
            }

            renderBoard();
            updateTurnIndicator();
            updatePlayerCardHighlight();
        });
    } else {
        boardState = data.board;
        isWhiteTurn = data.whiteToMove;
        isMyTurn = (myColor === 'white') === isWhiteTurn;
        totalMoves++;
        renderBoard();
        updateTurnIndicator();
        updatePlayerCardHighlight();
    }

    if (data.checkmate || data.stalemate || data.isDraw) {
        isGameComplete = true;
        stopClock();
        if (data.isDraw && !data.stalemate) {
            data.result = 'draw';
            data.termination = data.drawReason;
        }
        showGameOver(data);
        showAnalyzeButton();
    }
}

function handleGameEnd(data) {
    isGameComplete = true;
    stopClock();
    playSound('gameEnd');
    showGameOver(data);
    showAnalyzeButton();
}

function resignGame() {
    if (isGameComplete) {
        showToast('Game already finished');
        return;
    }

    if (confirm('Are you sure you want to resign?')) {
        if (isOnlineGame) {
            socket.emit('resign', { game_id: gameId });
        } else {
            // Local game resignation
            const result = isWhiteTurn ? 'black_win' : 'white_win';
            handleGameEnd({
                success: true,
                result: result,
                termination: 'Resignation'
            });
        }
        playSound('gameEnd');
        closeMenu();
    }
}

function offerDraw() {
    if (!isOnlineGame) {
        showToast('Draw offers only available in online games');
        return;
    }

    if (isGameComplete) {
        showToast('Game already finished');
        return;
    }

    socket.emit('offer_draw', { game_id: gameId });
    showToast('Draw offer sent to opponent');
    closeMenu();
}

function respondToDraw(accepted) {
    const modal = document.getElementById('draw-modal');
    modal.style.display = 'none';

    socket.emit('respond_draw', {
        game_id: gameId,
        accepted: accepted
    });
}

// ============================================================================
// CHAT SYSTEM
// ============================================================================

function initializeChatUI() {
    const chatWidget = document.getElementById('chat-widget');
    if (chatWidget) {
        // Only show chat for PvP (Online or Local)
        if (gameMode === 'pvp' || gameMode === 'online') {
            chatWidget.style.display = 'block';
        } else {
            chatWidget.style.display = 'none';
        }
    }

    // Reset state
    chatMessages = [];
    unreadMessages = 0;
    isChatOpen = false;

    // Clear message list
    const list = document.getElementById('chat-messages-list');
    if (list) {
        list.innerHTML = '<div class="chat-system-msg">Game started. Say hello!</div>';
    }

    // Ensure window is closed
    const window = document.getElementById('chat-window');
    if (window) window.style.display = 'none';

    updateChatBadge();
}

function toggleChat() {
    isChatOpen = !isChatOpen;
    const chatWindow = document.getElementById('chat-window');

    if (chatWindow) {
        chatWindow.style.display = isChatOpen ? 'block' : 'none';
        if (isChatOpen) {
            unreadMessages = 0;
            updateChatBadge();
            // Focus input after animation
            setTimeout(() => {
                const input = document.getElementById('chat-text-input');
                if (input) input.focus();
            }, 50);

            // Scroll to bottom
            const list = document.getElementById('chat-messages-list');
            if (list) list.scrollTop = list.scrollHeight;
        }
    }
    playSound('btnClick');
}

function sendChatMessage() {
    const input = document.getElementById('chat-text-input');
    if (!input || !input.value.trim()) return;

    const message = input.value.trim();
    if (message.length > 200) {
        showToast('Message too long (max 200 characters)');
        return;
    }

    // In online mode, emit to server
    if (isOnlineGame && socket) {
        socket.emit('chat_message', {
            game_id: gameId,
            message: message
        });
    }

    // Add to local UI
    addChatMessage({
        sender: currentUser ? currentUser.username : 'You',
        message: message,
        timestamp: Date.now(),
        isSelf: true
    });

    input.value = '';
}

function sendQuickEmoji(emoji) {
    const input = document.getElementById('chat-text-input');
    if (input) {
        input.value = emoji;
        sendChatMessage();
    }
}

function receiveChatMessage(data) {
    // If we are the sender, we already added this message locally in sendChatMessage()
    if (currentUser && data.sender === currentUser.username) {
        return;
    }

    addChatMessage({
        sender: data.sender,
        message: data.message,
        timestamp: data.timestamp,
        isSelf: false
    });

    if (!isChatOpen) {
        unreadMessages++;
        updateChatBadge();
        // Play a subtle notification sound for incoming chat
        playSound('btnClick');
    }
}

function addChatMessage(data) {
    chatMessages.push(data);

    const list = document.getElementById('chat-messages-list');
    if (!list) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-bubble ${data.isSelf ? 'me' : 'them'}`;

    const timeStr = new Date(data.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    msgDiv.innerHTML = `
        <div class="chat-bubble-name">${data.sender}</div>
        <div class="chat-text">${escapeHtml(data.message)}</div>
        <div class="chat-bubble-time">${timeStr}</div>
    `;

    list.appendChild(msgDiv);
    list.scrollTop = list.scrollHeight;
}

function updateChatBadge() {
    const badge = document.getElementById('chat-unread-badge');
    if (badge) {
        if (unreadMessages > 0) {
            badge.textContent = unreadMessages;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// GAME ANALYSIS
// ============================================================================

async function analyzeGame() {
    if (!isGameComplete) {
        showToast('Finish the game before analyzing');
        return;
    }

    if (isAnalysisMode) {
        exitAnalysis();
        return;
    }

    showToast('Analyzing game with Stockfish...');

    try {
        const response = await fetch(`/api/game/${gameId}/analyze`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            gameAnalysis = data.analysis;
            enterAnalysisMode();
            applyMoveClassifications();
            showToast('Analysis complete!');
        } else {
            showToast('Analysis failed: ' + data.error);
        }
    } catch (error) {
        console.error('Analysis error:', error);
        showToast('Analysis failed');
    }
}

function enterAnalysisMode() {
    isAnalysisMode = true;
    currentMoveIndex = totalMoves;

    const controls = document.getElementById('analysis-controls');
    if (controls) {
        controls.style.display = 'flex';
        updateNavigationButtons();
    }

    const evalBar = document.getElementById('evaluation-bar');
    if (evalBar) evalBar.style.display = 'flex';

    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.textContent = 'Exit Analysis';
        analyzeBtn.onclick = exitAnalysis;
    }

    showToast('Use arrow keys or click moves to navigate');

    // Trigger first eval
    updateEvaluationBar(0);
}

function exitAnalysis() {
    isAnalysisMode = false;
    currentMoveIndex = totalMoves;

    const controls = document.getElementById('analysis-controls');
    if (controls) controls.style.display = 'none';

    const evalBar = document.getElementById('evaluation-bar');
    if (evalBar) evalBar.style.display = 'none';

    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.textContent = '📊 Analyze Game';
        analyzeBtn.onclick = analyzeGame;
    }

    goToLast();
}

function applyMoveClassifications() {
    if (!gameAnalysis) return;

    const moveItems = document.querySelectorAll('.move-item');
    gameAnalysis.forEach((analysis, index) => {
        if (moveItems[index]) {
            const classification = analysis.classification;
            moveItems[index].classList.add(classification);

            // Add icon
            const icon = getClassificationIcon(classification);
            if (icon) {
                moveItems[index].innerHTML += ` ${icon}`;
            }
        }
    });
}

function getClassificationIcon(classification) {
    const icons = {
        'brilliant': '‼',
        'best': '✓',
        'good': '',
        'inaccuracy': '?!',
        'mistake': '?',
        'blunder': '??'
    };
    return icons[classification] || '';
}

function showAnalyzeButton() {
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.style.display = 'block';
    }
}

async function goToPosition(index) {
    if (index < 0 || index > totalMoves) return;

    currentMoveIndex = index;

    try {
        const response = await fetch(`/api/game/${gameId}/position/${index}`);
        const data = await response.json();

        if (data.success) {
            boardState = data.board;
            isWhiteTurn = data.whiteToMove;
            renderBoard();
            updateTurnIndicator();
            updateNavigationButtons();
            highlightCurrentMove();

            // Show move analysis if available
            if (gameAnalysis && index > 0 && index <= gameAnalysis.length) {
                const stepAnalysis = gameAnalysis[index - 1];
                showMoveAnalysis(stepAnalysis);
                updateEvaluationBar(stepAnalysis.evaluation);
            } else {
                // Fetch real-time eval if not in analysis data
                fetchRealTimeEval();
            }
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function fetchRealTimeEval() {
    if (!isAnalysisMode) return;
    try {
        const response = await fetch(`/api/game/${gameId}/evaluate`);
        const data = await response.json();
        if (data.success) {
            updateEvaluationBar(data.evaluation);
        }
    } catch (e) { }
}

function updateEvaluationBar(evaluation) {
    const bar = document.getElementById('evaluation-bar');
    const fill = document.getElementById('evaluation-fill');
    const score = document.getElementById('evaluation-score');

    if (!bar || !fill || !score) return;

    let percent = 50; // White's percentage of the bar by default
    let dispScore = "0.0";

    if (evaluation !== undefined && evaluation !== null) {
        if (typeof evaluation === 'string' && evaluation.startsWith('M')) {
            const val = parseInt(evaluation.substring(1));
            // M1 -> 100%, M-1 -> 0%
            percent = (val > 0) ? 100 : 0;
            dispScore = Math.abs(val) >= 1000 ? "#" : evaluation;
        } else {
            const ev = parseFloat(evaluation);
            // ev > 0 is White advantage
            percent = 50 + (ev * 15);
            percent = Math.min(Math.max(percent, 2), 98);
            dispScore = Math.abs(ev).toFixed(1);
            if (ev === 0) dispScore = "0.0";
        }
    }

    // Handle board flip: UI bar should grow from bottom player's perspective
    if (boardFlipped) {
        // Black is at bottom. Bar percent represents White.
        // We want to show Black's advantage at the bottom.
        let blackPercent = 100 - percent;
        fill.style.height = `${blackPercent}%`;
        fill.style.background = 'linear-gradient(to bottom, #1a1a1a, #2a2a2a)'; // Dark fill
        bar.style.backgroundColor = '#f0f0f0'; // White background
        
        // Position score
        if (blackPercent > 50) {
            score.style.bottom = '10px';
            score.style.top = 'auto';
            score.style.color = '#ffffff';
        } else {
            score.style.top = '10px';
            score.style.bottom = 'auto';
            score.style.color = '#1a1a1a';
        }
    } else {
        // White is at bottom. 
        fill.style.height = `${percent}%`;
        fill.style.background = 'linear-gradient(to bottom, #f0f0f0, #d0d0d0)'; // White fill
        bar.style.backgroundColor = '#262421'; // Dark background
        
        // Position score
        if (percent > 50) {
            score.style.bottom = '10px';
            score.style.top = 'auto';
            score.style.color = '#1a1a1a';
        } else {
            score.style.top = '10px';
            score.style.bottom = 'auto';
            score.style.color = '#ffffff';
        }
    }

    score.textContent = dispScore;
}

function showMoveAnalysis(analysis) {
    const indicator = document.getElementById('turn-indicator');
    if (!indicator) return;

    let evalDisplay = '';
    if (analysis.evaluation !== undefined && analysis.evaluation !== null) {
        const ev = analysis.evaluation;
        if (typeof ev === 'string' && ev.startsWith('M')) {
            evalDisplay = `Eval: ${ev}`;
        } else {
            const numEv = parseFloat(ev);
            evalDisplay = `Eval: ${numEv > 0 ? '+' : ''}${numEv.toFixed(2)}`;
        }
    }

    const classText = analysis.classification.charAt(0).toUpperCase() +
        analysis.classification.slice(1);

    indicator.textContent = `Move ${currentMoveIndex}: ${classText} ${evalDisplay}`;

    if (analysis.best_move) {
        indicator.textContent += ` (Best: ${analysis.best_move})`;
    }
}

function goToFirst() {
    goToPosition(0);
}

function goToPrevious() {
    if (currentMoveIndex > 0) {
        goToPosition(currentMoveIndex - 1);
    }
}

function goToNext() {
    if (currentMoveIndex < totalMoves) {
        goToPosition(currentMoveIndex + 1);
    }
}

function goToLast() {
    goToPosition(totalMoves);
}

function updateNavigationButtons() {
    const firstBtn = document.getElementById('first-btn');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const lastBtn = document.getElementById('last-btn');

    if (firstBtn) firstBtn.disabled = (currentMoveIndex === 0);
    if (prevBtn) prevBtn.disabled = (currentMoveIndex === 0);
    if (nextBtn) nextBtn.disabled = (currentMoveIndex === totalMoves);
    if (lastBtn) lastBtn.disabled = (currentMoveIndex === totalMoves);
}

function highlightCurrentMove() {
    const moveItems = document.querySelectorAll('.move-item');
    moveItems.forEach((item, index) => {
        if (index + 1 === currentMoveIndex) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// ============================================================================
// LOCAL GAME MODES (PvP, PvC, CvP)
// ============================================================================

let playerRole = 'white';

function updateDifficultyDisplay() {
    const slider = document.getElementById('difficulty-slider');
    difficulty = parseInt(slider.value);

    const levels = {
        1: { name: 'Beginner', desc: 'Good for learning (~1300 ELO)' },
        10: { name: 'Intermediate', desc: 'Club player level (~1900 ELO)' },
        15: { name: 'Expert', desc: 'Strong tactical play (~2400 ELO)' },
        20: { name: 'Master', desc: 'Grandmaster level (~2800+ ELO)' }
    };

    let level = levels[1];
    if (difficulty >= 18) level = levels[20];
    else if (difficulty >= 13) level = levels[15];
    else if (difficulty >= 8) level = levels[10];

    document.getElementById('difficulty-value').textContent = level.name;
    document.getElementById('difficulty-desc').textContent = level.desc;
}

function showDifficulty(mode) {
    selectedMode = mode;

    if (mode === 'pvc') {
        playerRole = 'white';
        selectRole('white');
        document.getElementById('role-selection').style.display = 'flex';
    } else {
        document.getElementById('role-selection').style.display = 'none';
        selectedMode = (mode === 'cvp') ? 'cvc' : mode;
    }

    document.getElementById('difficulty-selector').style.display = 'flex';
}

function selectRole(role) {
    playerRole = role;
    const btnWhite = document.getElementById('btn-play-white');
    const btnBlack = document.getElementById('btn-play-black');

    if (role === 'white') {
        btnWhite.style.borderColor = '#ffffff';
        btnWhite.style.opacity = '1';
        btnBlack.style.borderColor = '#3f3f46';
        btnBlack.style.opacity = '0.5';
    } else {
        btnBlack.style.borderColor = '#ffffff';
        btnBlack.style.opacity = '1';
        btnWhite.style.borderColor = '#3f3f46';
        btnWhite.style.opacity = '0.5';
    }
}

function confirmDifficulty() {
    if (selectedMode) {
        let finalMode = selectedMode;
        if (selectedMode === 'pvc' && playerRole === 'black') {
            finalMode = 'cvp';
        }

        startGame(finalMode);
        document.getElementById('difficulty-selector').style.display = 'none';
    }
}

function toggleMenu() {
    const menu = document.getElementById('hamburger-menu');
    const dropdown = document.getElementById('menu-dropdown');
    menu.classList.toggle('active');
    dropdown.classList.toggle('active');
}

async function startGame(mode) {
    isOnlineGame = false;
    gameMode = mode;
    clocksEnabled = (mode === 'pvp');
    boardFlipped = (mode === 'cvp');
    isAnalysisMode = false;
    isGameComplete = false;
    currentMoveIndex = 0;
    totalMoves = 0;

    try {
        const response = await fetch('/api/new-game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, difficulty })
        });

        const data = await response.json();

        if (data.success) {
            gameId = data.game_id;
            boardState = data.board;
            isWhiteTurn = true;

            document.getElementById('game-setup').style.display = 'none';
            document.getElementById('game-area').style.display = 'flex';
            document.getElementById('hamburger-menu').style.display = 'block';
            document.body.classList.add('playing');

            if (mode === 'pvc') {
                whitePlayerName = 'You';
                blackPlayerName = 'Stockfish AI';
                whiteRating = 1500;
                blackRating = 2400;
            } else if (mode === 'cvp') {
                whitePlayerName = 'Stockfish AI';
                blackPlayerName = 'You';
                whiteRating = 2400;
                blackRating = 1500;
            } else if (mode === 'cvc') {
                whitePlayerName = 'Stockfish AI (White)';
                blackPlayerName = 'Stockfish AI (Black)';
                whiteRating = 2400;
                blackRating = 2400;
            } else {
                whitePlayerName = 'White';
                blackPlayerName = 'Black';
                whiteRating = 1500;
                blackRating = 1500;
            }

            if (clocksEnabled) {
                const tcConf = selectedTimeControl && selectedTimeControl !== 'unlimited'
                    ? parseTimeControl(selectedTimeControl)
                    : { initialTime: 0, increment: 0 };

                if (tcConf.initialTime === 0) {
                    // Unlimited / no clock
                    clocksEnabled = false;
                    document.getElementById('top-clock').style.display = 'none';
                    document.getElementById('bottom-clock').style.display = 'none';
                } else {
                    whiteTime = tcConf.initialTime;
                    blackTime = tcConf.initialTime;
                    currentIncrement = tcConf.increment;
                    document.getElementById('top-clock').style.display = '';
                    document.getElementById('bottom-clock').style.display = '';
                    startClock();
                }
            }

            updatePlayerCards();
            updateGameModeDisplay();
            renderBoard();
            updateCoordinates();

            playSound('gameStart');

            if (mode === 'cvp' || mode === 'cvc') {
                setTimeout(getAIMove, 300);
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to start game');
    }
}

function updatePlayerCards() {
    if (!boardFlipped) {
        document.getElementById('bottom-player-name').textContent = whitePlayerName;
        document.getElementById('bottom-player-rating').textContent = `Rating: ${whiteRating}`;
        document.getElementById('bottom-avatar').textContent = '♔';
        document.getElementById('bottom-clock').textContent = formatTime(whiteTime);

        document.getElementById('top-player-name').textContent = blackPlayerName;
        document.getElementById('top-player-rating').textContent = `Rating: ${blackRating}`;
        document.getElementById('top-avatar').textContent = '♚';
        document.getElementById('top-clock').textContent = formatTime(blackTime);
    } else {
        document.getElementById('bottom-player-name').textContent = blackPlayerName;
        document.getElementById('bottom-player-rating').textContent = `Rating: ${blackRating}`;
        document.getElementById('bottom-avatar').textContent = '♚';
        document.getElementById('bottom-clock').textContent = formatTime(blackTime);

        document.getElementById('top-player-name').textContent = whitePlayerName;
        document.getElementById('top-player-rating').textContent = `Rating: ${whiteRating}`;
        document.getElementById('top-avatar').textContent = '♔';
        document.getElementById('top-clock').textContent = formatTime(whiteTime);
    }

    updatePlayerCardHighlight();

    if (!clocksEnabled) {
        document.getElementById('top-clock').style.display = 'none';
        document.getElementById('bottom-clock').style.display = 'none';
    } else {
        document.getElementById('top-clock').style.display = 'flex';
        document.getElementById('bottom-clock').style.display = 'flex';
    }
}

function updatePlayerCardHighlight() {
    const topCard = document.getElementById('top-player-card');
    const bottomCard = document.getElementById('bottom-player-card');

    if (!boardFlipped) {
        if (isWhiteTurn) {
            bottomCard.classList.add('active');
            topCard.classList.remove('active');
        } else {
            topCard.classList.add('active');
            bottomCard.classList.remove('active');
        }
    } else {
        if (isWhiteTurn) {
            topCard.classList.add('active');
            bottomCard.classList.remove('active');
        } else {
            bottomCard.classList.add('active');
            topCard.classList.remove('active');
        }
    }
}

function updateGameModeDisplay() {
    const modeNames = {
        'pvp': 'Player vs Player',
        'pvc': 'Player vs Computer',
        'cvp': 'Computer vs Player',
        'online': 'Online Multiplayer'
    };
    document.getElementById('game-mode-display').textContent = modeNames[gameMode] || 'Chess Game';
}

function renderBoard() {
    const board = document.getElementById('chessboard');
    board.innerHTML = '';

    if (!boardState || boardState.length !== 8) {
        console.error('Invalid board state');
        return;
    }

    const rowOrder = boardFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
    const colOrder = boardFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];

    for (const row of rowOrder) {
        if (!boardState[row] || boardState[row].length !== 8) {
            console.error('Invalid row:', row);
            continue;
        }

        for (const col of colOrder) {
            const square = document.createElement('div');
            const isLight = (row + col) % 2 === 0;
            square.className = `square ${isLight ? 'light' : 'dark'}`;
            square.dataset.row = row;
            square.dataset.col = col;

            const piece = boardState[row][col];
            if (piece && piece !== '--') {
                const pieceEl = document.createElement('div');
                pieceEl.className = 'piece ' + (piece[0] === 'w' ? 'white-piece' : 'black-piece');
                pieceEl.textContent = PIECES[piece] || '';
                square.appendChild(pieceEl);
            }

            if (!isAnalysisMode && (!isOnlineGame || isMyTurn)) {
                square.addEventListener('click', () => handleSquareClick(row, col));

                // Set piece draggable
                const pEl = square.querySelector('.piece');
                if (pEl) {
                    pEl.draggable = true;
                    pEl.addEventListener('dragstart', (e) => handleDragStart(e, row, col));
                    pEl.addEventListener('dragend', handleDragEnd);

                    // Mobile Touch
                    pEl.addEventListener('touchstart', (e) => handleTouchStart(e, row, col), { passive: false });
                    pEl.addEventListener('touchmove', handleTouchMove, { passive: false });
                    pEl.addEventListener('touchend', handleTouchEnd, { passive: false });
                }

                // Allow drops
                square.addEventListener('dragover', handleDragOver);
                square.addEventListener('dragenter', handleDragEnter);
                square.addEventListener('dragleave', handleDragLeave);
                square.addEventListener('drop', (e) => handleDrop(e, row, col));
            }

            // Highlight last move
            if (lastMoveSquares.some(s => s.row === row && s.col === col)) {
                square.classList.add('last-move');
            }

            board.appendChild(square);
        }
    }
}

function updateCoordinates() {
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

    if (boardFlipped) {
        updateFileLabels([...files].reverse());
        updateRankLabels([...ranks].reverse());
    } else {
        updateFileLabels(files);
        updateRankLabels(ranks);
    }
}

function updateFileLabels(files) {
    const topFiles = document.getElementById('top-files');
    const bottomFiles = document.getElementById('bottom-files');

    topFiles.innerHTML = files.map(f => `<div class="file-label">${f}</div>`).join('');
    bottomFiles.innerHTML = files.map(f => `<div class="file-label">${f}</div>`).join('');
}

function updateRankLabels(ranks) {
    const leftRanks = document.getElementById('left-ranks');
    const rightRanks = document.getElementById('right-ranks');

    leftRanks.innerHTML = ranks.map(r => `<div class="rank-label">${r}</div>`).join('');
    rightRanks.innerHTML = ranks.map(r => `<div class="rank-label">${r}</div>`).join('');
}

async function handleSquareClick(row, col) {
    if (isAIThinking || isAnalysisMode) return;

    if (isOnlineGame && !isMyTurn) {
        showToast("It's not your turn!");
        return;
    }

    const piece = boardState[row][col];

    if (!selectedSquare) {
        if (piece === '--' || (piece[0] === 'w') !== isWhiteTurn) return;

        if (isOnlineGame) {
            const isPieceWhite = (piece[0] === 'w');
            if ((myColor === 'white' && !isPieceWhite) || (myColor === 'black' && isPieceWhite)) {
                return;
            }
        }

        selectedSquare = { row, col };
        highlightSquare(row, col);
        await getValidMoves(row, col);
    }
    else if (selectedSquare.row === row && selectedSquare.col === col) {
        clearHighlights();
        selectedSquare = null;
        validMoves = [];
    }
    else {
        const isValid = validMoves.some(m => m.row === row && m.col === col);

        if (isValid) {
            const piece = boardState[selectedSquare.row][selectedSquare.col];
            const isPawn = piece[1] === 'p';
            const isPromotion = isPawn && (row === 0 || row === 7);

            if (isPromotion) {
                pendingPromotion = { from: selectedSquare, to: { row, col } };
                document.getElementById('promotion-modal').style.display = 'flex';
                return;
            }

            if (isOnlineGame) {
                sendOnlineMove(selectedSquare, { row, col });
                clearHighlights();
                selectedSquare = null;
                validMoves = [];
            } else {
                await makeMove(selectedSquare, { row, col });
            }
        } else if (piece !== '--' && ((piece[0] === 'w') === isWhiteTurn)) {
            clearHighlights();
            selectedSquare = { row, col };
            highlightSquare(row, col);
            await getValidMoves(row, col);
        } else {
            clearHighlights();
            selectedSquare = null;
            validMoves = [];
        }
    }
}

async function getValidMoves(row, col) {
    try {
        const response = await fetch(`/api/game/${gameId}/valid-moves`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position: { row, col } })
        });

        const data = await response.json();
        if (data.success) {
            validMoves = data.moves;
            highlightValidMoves();
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function makeMove(from, to, promotion = 'Q') {
    try {
        clearHighlights();
        selectedSquare = null;
        validMoves = [];

        const animationPromise = animatePieceLocally(from, to);
        const responsePromise = fetch(`/api/game/${gameId}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from, to, promotion })
        });

        await animationPromise;
        const response = await responsePromise;
        const data = await response.json();

        if (data.success) {
            // Apply increment before switching turn
            if (clocksEnabled && currentIncrement > 0) {
                if (isWhiteTurn) whiteTime += currentIncrement;
                else blackTime += currentIncrement;
                updateClockDisplay();
            }

            lastMoveSquares = [from, to];
            boardState = data.board;
            isWhiteTurn = data.whiteToMove;
            totalMoves++;

            renderBoard();
            addMove(data.move, totalMoves - 1);
            updateTurnIndicator();
            updatePlayerCardHighlight();

            // Play sound
            if (data.checkmate || data.stalemate || data.isDraw) {
                playSound('gameEnd');
            } else if (data.inCheck) {
                playSound('check');
            } else if (data.move.notation && data.move.notation.includes('x')) {
                playSound('capture');
            } else {
                playSound('move');
            }

            if (data.checkmate || data.stalemate || data.isDraw) {
                stopClock();
                isGameComplete = true;
                if (data.isDraw && !data.stalemate) {
                    data.result = 'draw';
                    data.termination = data.drawReason;
                }
                showGameOver(data);
                showAnalyzeButton();
                return;
            }

            if ((gameMode === 'pvc' && !isWhiteTurn) || (gameMode === 'cvp' && isWhiteTurn)) {
                setTimeout(getAIMove, 30);
            } else if (gameMode === 'cvc') {
                setTimeout(getAIMove, 30);
            }
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function getAIMove() {
    if (isAIThinking) return;

    isAIThinking = true;
    document.getElementById('ai-overlay').style.display = 'block';

    try {
        const response = await fetch(`/api/game/${gameId}/ai-move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            if (data.move) {
                lastMoveSquares = [data.move.from, data.move.to];
                await animatePieceLocally(data.move.from, data.move.to);
            }

            boardState = data.board;
            isWhiteTurn = data.whiteToMove;
            totalMoves++;

            renderBoard();
            addMove(data.move, totalMoves - 1);
            updateTurnIndicator();
            updatePlayerCardHighlight();

            // Play sound
            if (data.checkmate || data.stalemate || data.isDraw) {
                playSound('gameEnd');
            } else if (data.inCheck) {
                playSound('check');
            } else if (data.move.notation && data.move.notation.includes('x')) {
                playSound('capture');
            } else {
                playSound('move');
            }

            if (data.checkmate || data.stalemate || data.isDraw) {
                stopClock();
                isGameComplete = true;
                if (data.isDraw && !data.stalemate) {
                    data.result = 'draw';
                    data.termination = data.drawReason;
                }
                showGameOver(data);
                showAnalyzeButton();
            } else {
                if (gameMode === 'cvc') {
                    setTimeout(getAIMove, 500);
                }
            }
        }
    } catch (error) {
        console.error('Error:', error);
    } finally {
        isAIThinking = false;
        document.getElementById('ai-overlay').style.display = 'none';
    }
}

function updateTurnIndicator() {
    const indicator = document.getElementById('turn-indicator');
    if (isAnalysisMode) {
        indicator.textContent = `Analysis: Move ${currentMoveIndex} of ${totalMoves}`;
    } else if (isOnlineGame) {
        if (isMyTurn) {
            indicator.textContent = 'Your turn';
        } else {
            indicator.textContent = "Opponent's turn";
        }
    } else {
        indicator.textContent = isWhiteTurn ? 'White to move' : 'Black to move';
    }
}

async function getHint() {
    try {
        const response = await fetch(`/api/game/${gameId}/hint`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('hint-message').textContent =
                `Try moving: ${data.hint.notation}`;
            document.getElementById('hint-modal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error:', error);
    }
    closeMenu();
}

function closeHint() {
    document.getElementById('hint-modal').style.display = 'none';
}

async function undoMove() {
    if (isAnalysisMode) {
        showToast('Exit analysis mode first to undo moves');
        return;
    }

    if (isOnlineGame) {
        showToast('Cannot undo in online games');
        return;
    }

    try {
        const response = await fetch(`/api/game/${gameId}/undo`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            boardState = data.board;
            isWhiteTurn = data.whiteToMove;
            totalMoves--;

            clearHighlights();
            renderBoard();
            updateTurnIndicator();
            updatePlayerCardHighlight();

            const history = document.getElementById('move-history');
            if (history.lastChild) {
                history.removeChild(history.lastChild);
            }
        }
    } catch (error) {
        console.error('Error:', error);
    }
    closeMenu();
}

function flipBoard() {
    boardFlipped = !boardFlipped;
    renderBoard();
    updateCoordinates();
    updatePlayerCards();
    closeMenu();
}

function closeMenu() {
    const menu = document.getElementById('hamburger-menu');
    const dropdown = document.getElementById('menu-dropdown');
    menu.classList.remove('active');
    dropdown.classList.remove('active');
}

function resetGame() {
    if (confirm('Start a new game?')) {
        stopClock();
        if (isOnlineGame && socket) {
            socket.emit('resign', { game_id: gameId });
        }
        location.reload();
    }
}

// Clock functions
function startClock() {
    if (!clocksEnabled) return;

    stopClock();
    lastUpdateTime = Date.now();

    clockInterval = setInterval(() => {
        const currentTime = Date.now();
        const elapsed = (currentTime - lastUpdateTime) / 1000;
        lastUpdateTime = currentTime;

        if (isWhiteTurn) {
            whiteTime = Math.max(0, whiteTime - elapsed);
            if (whiteTime === 0) {
                stopClock();
                playSound('gameEnd');
                showGameOver({ timeout: true, winner: 'black' });
            }
        } else {
            blackTime = Math.max(0, blackTime - elapsed);
            if (blackTime === 0) {
                stopClock();
                playSound('gameEnd');
                showGameOver({ timeout: true, winner: 'white' });
            }
        }

        updateClockDisplay();
    }, 100);
}

function stopClock() {
    if (clockInterval) {
        clearInterval(clockInterval);
        clockInterval = null;
    }
}

function updateClockDisplay() {
    if (!clocksEnabled) return;

    if (!boardFlipped) {
        document.getElementById('bottom-clock').textContent = formatTime(whiteTime);
        document.getElementById('top-clock').textContent = formatTime(blackTime);

        document.getElementById('bottom-clock').classList.toggle('low-time', whiteTime < 60);
        document.getElementById('top-clock').classList.toggle('low-time', blackTime < 60);
    } else {
        document.getElementById('top-clock').textContent = formatTime(whiteTime);
        document.getElementById('bottom-clock').textContent = formatTime(blackTime);

        document.getElementById('top-clock').classList.toggle('low-time', whiteTime < 60);
        document.getElementById('bottom-clock').classList.toggle('low-time', blackTime < 60);
    }
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function highlightSquare(row, col) {
    const square = document.querySelector(`.square[data-row="${row}"][data-col="${col}"]`);
    if (square) {
        square.classList.add('selected');
    }
}

function highlightValidMoves() {
    validMoves.forEach(move => {
        const square = document.querySelector(`.square[data-row="${move.row}"][data-col="${move.col}"]`);
        if (square) {
            square.classList.add(move.isCapture ? 'valid-capture' : 'valid-move');
        }
    });
}

function clearHighlights() {
    document.querySelectorAll('.square').forEach(sq => {
        sq.classList.remove('selected', 'valid-move', 'valid-capture');
    });
}

function addMove(move, index) {
    if (!move) return;
    const history = document.getElementById('move-history');
    const div = document.createElement('div');
    div.className = 'move-item';
    div.dataset.index = index;

    const moveNum = Math.floor(index / 2) + 1;
    const isWhiteMove = index % 2 === 0;

    div.textContent = isWhiteMove
        ? `${moveNum}. ${move.notation}`
        : `${moveNum}... ${move.notation}`;

    div.onclick = () => {
        if (isAnalysisMode) goToPosition(index + 1);
    };

    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

function showGameOver(data) {
    setTimeout(() => {
        const modal = document.getElementById('game-over-modal');
        const icon = document.getElementById('game-over-icon');
        const title = document.getElementById('game-over-title');
        const message = document.getElementById('game-over-message');

        let msg = '';
        if (data.timeout) {
            icon.textContent = '⏱️';
            title.textContent = 'Time Out!';
            msg = `${data.winner === 'white' ? 'White' : 'Black'} wins on time!`;
        } else if (data.checkmate) {
            icon.textContent = '🏆';
            title.textContent = 'Checkmate!';
            msg = isWhiteTurn ? 'Black won by Checkmate' : 'White won by Checkmate';
        } else if (data.stalemate) {
            icon.textContent = '🤝';
            title.textContent = 'Stalemate';
            msg = "It's a draw!";
        } else if (data.result) {
            icon.textContent = '🏆';
            if (data.result === 'white_win') {
                title.textContent = 'White Wins!';
                msg = myColor === 'white' ? 'You won!' : 'You lost.';
            } else if (data.result === 'black_win') {
                title.textContent = 'Black Wins!';
                msg = myColor === 'black' ? 'You won!' : 'You lost.';
            } else {
                title.textContent = 'Draw';
                msg = "It's a draw!";
            }

            if (data.termination) {
                msg += ` (${data.termination})`;
            }
        }
        message.textContent = msg;
        modal.style.display = 'flex';

        document.getElementById('turn-indicator').textContent = 'Game Over: ' + msg;
        document.getElementById('turn-indicator').style.color = 'var(--neon-pink)';
    }, 300);
}

function closeGameOverModal() {
    document.getElementById('game-over-modal').style.display = 'none';
}

function showToast(msg) {
    let toast = document.getElementById('toast-msg');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-msg';
        toast.style.cssText = [
            'position:fixed', 'bottom:80px', 'left:50%',
            'transform:translateX(-50%)',
            'background:rgba(5,15,40,0.95)',
            'color:var(--neon-cyan)',
            'border:1px solid var(--neon-cyan)',
            'padding:0.75rem 1.5rem',
            'border-radius:10px',
            'font-family:Orbitron,monospace',
            'font-size:0.85rem',
            'z-index:9999',
            'box-shadow:0 0 20px rgba(0,245,255,0.3)',
            'pointer-events:none',
            'transition:opacity 0.3s'
        ].join(';');
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { toast.style.opacity = '0'; }, 2500);
}

function handleDragStart(e, row, col) {
    if (isAIThinking || isAnalysisMode) return;
    const piece = boardState[row][col];
    if (piece === '--' || (piece[0] === 'w') !== isWhiteTurn) {
        e.preventDefault();
        return;
    }

    draggedPiece = e.target;
    dragFrom = { row, col };
    draggedPiece.classList.add('dragging');

    selectedSquare = { row, col };
    highlightSquare(row, col);
    getValidMoves(row, col);

    e.dataTransfer.setData('text/plain', JSON.stringify({ row, col }));
    e.dataTransfer.dropEffect = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function handleDragEnter(e) {
    e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleDragEnd(e) {
    if (draggedPiece) draggedPiece.classList.remove('dragging');
}

async function handleDrop(e, row, col) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    if (!dragFrom) return;

    const from = dragFrom;
    const to = { row, col };

    if (from.row === to.row && from.col === to.col) return;

    const isValid = validMoves.some(m => m.row === row && m.col === col);
    if (isValid) {
        const piece = boardState[from.row][from.col];
        const isPawn = piece[1] === 'p';
        const isPromotion = isPawn && (row === 0 || row === 7);

        if (isPromotion) {
            pendingPromotion = { from, to };
            document.getElementById('promotion-modal').style.display = 'flex';
        } else {
            if (isOnlineGame) sendOnlineMove(from, to);
            else await makeMove(from, to);
        }
    }

    clearHighlights();
    selectedSquare = null;
    validMoves = [];
    dragFrom = null;
    draggedPiece = null;
}

// Mobile Touch Handlers
let touchElement = null;

function handleTouchStart(e, row, col) {
    if (isAIThinking || isAnalysisMode) return;
    const piece = boardState[row][col];
    if (piece === '--' || (piece[0] === 'w') !== isWhiteTurn) return;

    e.preventDefault();
    touchElement = e.target;
    dragFrom = { row, col };

    selectedSquare = { row, col };
    highlightSquare(row, col);
    getValidMoves(row, col);

    touchElement.style.position = 'fixed';
    touchElement.style.zIndex = '1000';
    touchElement.style.pointerEvents = 'none';
    updateTouchPos(e.touches[0]);
}

function handleTouchMove(e) {
    if (!touchElement) return;
    e.preventDefault();
    const touch = e.touches[0];
    updateTouchPos(touch);

    // Highlight square under touch
    const elem = document.elementFromPoint(touch.clientX, touch.clientY);
    const square = elem ? elem.closest('.square') : null;

    document.querySelectorAll('.square').forEach(sq => sq.classList.remove('drag-over'));
    if (square) square.classList.add('drag-over');
}

async function handleTouchEnd(e) {
    if (!touchElement) return;
    e.preventDefault();

    const touch = e.changedTouches[0];
    const elem = document.elementFromPoint(touch.clientX, touch.clientY);
    const square = elem ? elem.closest('.square') : null;

    touchElement.style.position = '';
    touchElement.style.zIndex = '';
    touchElement.style.left = '';
    touchElement.style.top = '';
    touchElement.style.pointerEvents = '';

    if (square) {
        const row = parseInt(square.dataset.row);
        const col = parseInt(square.dataset.col);
        await handleDrop(e, row, col);
    } else {
        clearHighlights();
        selectedSquare = null;
        validMoves = [];
    }

    touchElement = null;
    dragFrom = null;
}

function updateTouchPos(touch) {
    if (!touchElement || !touch) return;
    const size = touchElement.offsetWidth;
    touchElement.style.left = (touch.clientX - size / 2) + 'px';
    touchElement.style.top = (touch.clientY - size / 2) + 'px';
}

function animatePieceLocally(from, to) {
    return new Promise(resolve => {
        const fromSquare = document.querySelector(`.square[data-row="${from.row}"][data-col="${from.col}"]`);
        const toSquare = document.querySelector(`.square[data-row="${to.row}"][data-col="${to.col}"]`);

        if (fromSquare && toSquare) {
            const piece = fromSquare.querySelector('.piece');
            if (piece) {
                const fromRect = fromSquare.getBoundingClientRect();
                const toRect = toSquare.getBoundingClientRect();
                const dx = toRect.left - fromRect.left;
                const dy = toRect.top - fromRect.top;

                if (dx !== 0 || dy !== 0) {
                    piece.style.transition = 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
                    piece.style.transform = `translate(${dx}px, ${dy}px)`;
                    piece.style.zIndex = '100';
                    setTimeout(resolve, 200);
                    return;
                }
            }
        }
        resolve();
    });
}

console.log('♟️ GrandMaster - COMPLETE VERSION Loaded!');
console.log('✅ Features: Chat, Sounds, Analysis, Theme Toggle, Email Verification');
console.log('🎮 Online counter, Queue position, Resign button');