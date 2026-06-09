// Canvas setup
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
canvas.width = 800;
canvas.height = 600;

// Game constants
const paddleWidth = 10;
const paddleHeight = 100;
const ballRadius = 7;
const powerUpSize = 20;
const powerUpDuration = 5000; // 5 seconds

// Physics tuning (all speeds are expressed in px per 60fps-frame and scaled by dt)
const PADDLE_SPEED = 8;                 // paddle travel per frame
const BASE_BALL_SPEED = 6;              // ball speed at serve
const MAX_BALL_SPEED = 15;              // cap so rallies stay playable
const BALL_SPEED_GAIN = 1.05;           // multiplier applied on every paddle hit
const MAX_BOUNCE_ANGLE = Math.PI / 3;   // 60deg cap -> guarantees horizontal progress
const SERVE_ANGLE = Math.PI / 6;        // 30deg serve cone
const SPIN_FACTOR = 0.004;              // radians of curve per px of paddle motion
const DT_CAP = 3;                       // never advance more than 3 frames in one tick
const SUBSTEP = 0.5;                    // ball integration step (frames) to avoid tunneling

// Game objects
let player1 = {
    x: 0,
    y: canvas.height / 2 - paddleHeight / 2,
    prevY: canvas.height / 2 - paddleHeight / 2,
    width: paddleWidth,
    height: paddleHeight,
    color: '#fff',
    score: 0,
    originalHeight: paddleHeight
};

let player2 = {
    x: canvas.width - paddleWidth,
    y: canvas.height / 2 - paddleHeight / 2,
    prevY: canvas.height / 2 - paddleHeight / 2,
    width: paddleWidth,
    height: paddleHeight,
    color: '#fff',
    score: 0,
    originalHeight: paddleHeight
};

let ball = {
    x: canvas.width / 2,
    y: canvas.height / 2,
    radius: ballRadius,
    dirX: 1,        // unit direction (cos)
    dirY: 0,        // unit direction (sin)
    speed: BASE_BALL_SPEED,
    color: '#fff'
};

// Game state
let powerUps = [];          // pickups currently on the field
let activePowerUps = [];    // {type, category, factor, endTime}
let paused = false;
let singlePlayer = true;
let difficulty = 'medium';

// Audio elements commented out as requested
/*
const hitSound = document.getElementById('hitSound');
const scoreSound = document.getElementById('scoreSound');
const powerUpSound = document.getElementById('powerUpSound');
*/

// Input handling
const keys = {
    w: false,
    s: false,
    ArrowUp: false,
    ArrowDown: false
};

document.addEventListener('keydown', (e) => {
    if (keys.hasOwnProperty(e.key)) {
        keys[e.key] = true;
        e.preventDefault();
    }
});

document.addEventListener('keyup', (e) => {
    if (keys.hasOwnProperty(e.key)) {
        keys[e.key] = false;
        e.preventDefault();
    }
});

// Clamp a paddle so it stays fully on screen
function clampPaddle(p) {
    p.y = Math.max(0, Math.min(canvas.height - p.height, p.y));
}

// Handle paddle movement based on key states
function handleInput(dt) {
    const step = PADDLE_SPEED * dt;

    if (keys.w) player1.y -= step;
    if (keys.s) player1.y += step;
    clampPaddle(player1);

    if (!singlePlayer) {
        if (keys.ArrowUp) player2.y -= step;
        if (keys.ArrowDown) player2.y += step;
        clampPaddle(player2);
    }
}

// AI for player 2 in single-player mode
function aiMove(dt) {
    let speed;
    switch (difficulty) {
        case 'easy':
            speed = 3;
            break;
        case 'medium':
            speed = 5;
            break;
        case 'hard':
            speed = 7;
            break;
        default:
            speed = 5;
    }

    // skipChance: probability the AI does nothing this frame (higher = weaker)
    const skipChance = difficulty === 'hard' ? 0.1 : (difficulty === 'medium' ? 0.2 : 0.3);

    // Only react while the ball is heading toward the AI paddle
    if (ball.dirX > 0 && Math.random() > skipChance) {
        // Hard AI predicts the intercept; easier tiers just track the ball
        const targetY = difficulty === 'hard' ? predictBallY() : ball.y;
        const paddleCenter = player2.y + player2.height / 2;
        const step = speed * dt;

        if (paddleCenter < targetY - 10) {
            player2.y += step;
        } else if (paddleCenter > targetY + 10) {
            player2.y -= step;
        }
        clampPaddle(player2);
    }
}

// Predict the ball's y when it reaches the right paddle, accounting for wall bounces
function predictBallY() {
    if (ball.dirX <= 0) return ball.y;
    const mult = ballSpeedMultiplier();
    const vx = ball.dirX * ball.speed * mult;
    const vy = ball.dirY * ball.speed * mult;
    const time = (player2.x - ball.x) / vx;
    let y = ball.y + vy * time;

    // Reflect the predicted y back into [radius, height - radius] like a wall bounce
    const span = canvas.height - 2 * ball.radius;
    if (span <= 0) return ball.y;
    let m = (y - ball.radius) % (2 * span);
    if (m < 0) m += 2 * span;
    if (m > span) m = 2 * span - m;
    return ball.radius + m;
}

// Effect stacks ---------------------------------------------------------------
function paddleSizeMultiplier() {
    let m = 1;
    for (const e of activePowerUps) if (e.category === 'paddle') m *= e.factor;
    return m;
}

function ballSpeedMultiplier() {
    let m = 1;
    for (const e of activePowerUps) if (e.category === 'ball') m *= e.factor;
    return m;
}

// Recompute paddle heights from the base size and active effects (stacking-safe)
function applyPaddleSizes() {
    const m = paddleSizeMultiplier();
    for (const p of [player1, player2]) {
        const center = p.y + p.height / 2;
        p.height = p.originalHeight * m;
        p.y = center - p.height / 2;
        clampPaddle(p);
    }
}

// Ball physics ----------------------------------------------------------------
function bouncePaddle(paddle, dir) {
    // Where on the paddle the ball landed: -1 (top) .. +1 (bottom)
    const rel = (ball.y - (paddle.y + paddle.height / 2)) / (paddle.height / 2);
    let angle = Math.max(-1, Math.min(1, rel)) * MAX_BOUNCE_ANGLE;

    // Spin: a moving paddle curves the ball in its direction of travel
    const paddleVel = paddle.y - paddle.prevY;
    angle += paddleVel * SPIN_FACTOR;
    angle = Math.max(-MAX_BOUNCE_ANGLE, Math.min(MAX_BOUNCE_ANGLE, angle));

    // Speed up the rally, capped
    ball.speed = Math.min(ball.speed * BALL_SPEED_GAIN, MAX_BALL_SPEED);

    ball.dirX = dir * Math.cos(angle);
    ball.dirY = Math.sin(angle);
}

function moveBallStep(step, mult) {
    ball.x += ball.dirX * ball.speed * mult * step;
    ball.y += ball.dirY * ball.speed * mult * step;

    // Top / bottom walls: reflect and snap out of the wall (no sticking)
    if (ball.y - ball.radius <= 0) {
        ball.y = ball.radius;
        ball.dirY = Math.abs(ball.dirY);
    } else if (ball.y + ball.radius >= canvas.height) {
        ball.y = canvas.height - ball.radius;
        ball.dirY = -Math.abs(ball.dirY);
    }

    // Player 1 paddle (left)
    if (
        ball.dirX < 0 &&
        ball.x - ball.radius <= player1.x + player1.width &&
        ball.y + ball.radius >= player1.y &&
        ball.y - ball.radius <= player1.y + player1.height
    ) {
        bouncePaddle(player1, 1);
        ball.x = player1.x + player1.width + ball.radius; // clamp to face
    }

    // Player 2 paddle (right)
    if (
        ball.dirX > 0 &&
        ball.x + ball.radius >= player2.x &&
        ball.y + ball.radius >= player2.y &&
        ball.y - ball.radius <= player2.y + player2.height
    ) {
        bouncePaddle(player2, -1);
        ball.x = player2.x - ball.radius; // clamp to face
    }

    // Scoring
    if (ball.x + ball.radius < 0) {
        player2.score++;
        resetBall(-1);
    } else if (ball.x - ball.radius > canvas.width) {
        player1.score++;
        resetBall(1);
    }
}

// Integrate the ball in small sub-steps so fast balls can't tunnel
function updateBall(dt) {
    const mult = ballSpeedMultiplier();
    let remaining = dt;
    while (remaining > 0) {
        const step = Math.min(SUBSTEP, remaining);
        remaining -= step;
        moveBallStep(step, mult);
    }
}

// Reset ball to center after scoring / serve
function resetBall(direction) {
    ball.x = canvas.width / 2;
    ball.y = canvas.height / 2;
    ball.speed = BASE_BALL_SPEED;

    const dir = direction || (Math.random() > 0.5 ? 1 : -1);
    const angle = (Math.random() * 2 - 1) * SERVE_ANGLE; // controlled cone
    ball.dirX = dir * Math.cos(angle);
    ball.dirY = Math.sin(angle);
}

// Power-up functions ----------------------------------------------------------
function spawnPowerUp(dt) {
    if (Math.random() < 0.005 * dt) { // ~0.5% per 60fps-frame, frame-rate independent
        const types = ['increasePaddle', 'decreasePaddle', 'increaseSpeed', 'decreaseSpeed'];
        const type = types[Math.floor(Math.random() * types.length)];

        const x = Math.random() * (canvas.width - 100) + 50;
        const y = Math.random() * (canvas.height - 100) + 50;

        powerUps.push({ x, y, size: powerUpSize, type });
    }
}

function checkPowerUpCollision() {
    for (let i = powerUps.length - 1; i >= 0; i--) {
        const p = powerUps[i];
        // Closest point on the power-up square to the ball center
        const cx = Math.max(p.x, Math.min(ball.x, p.x + p.size));
        const cy = Math.max(p.y, Math.min(ball.y, p.y + p.size));
        const dx = ball.x - cx;
        const dy = ball.y - cy;
        if (dx * dx + dy * dy <= ball.radius * ball.radius) {
            applyPowerUp(p.type);
            powerUps.splice(i, 1);
        }
    }
}

function applyPowerUp(type) {
    const endTime = Date.now() + powerUpDuration;

    switch (type) {
        case 'increasePaddle':
            activePowerUps.push({ type, category: 'paddle', factor: 1.5, endTime });
            applyPaddleSizes();
            break;
        case 'decreasePaddle':
            activePowerUps.push({ type, category: 'paddle', factor: 0.5, endTime });
            applyPaddleSizes();
            break;
        case 'increaseSpeed':
            activePowerUps.push({ type, category: 'ball', factor: 1.5, endTime });
            break;
        case 'decreaseSpeed':
            activePowerUps.push({ type, category: 'ball', factor: 0.6, endTime });
            break;
    }
}

function updatePowerUps() {
    const now = Date.now();
    let paddleChanged = false;

    for (let i = activePowerUps.length - 1; i >= 0; i--) {
        if (now >= activePowerUps[i].endTime) {
            if (activePowerUps[i].category === 'paddle') paddleChanged = true;
            activePowerUps.splice(i, 1);
        }
    }

    if (paddleChanged) applyPaddleSizes();
}

// Draw functions --------------------------------------------------------------
function drawPaddles() {
    ctx.fillStyle = player1.color;
    ctx.fillRect(player1.x, player1.y, player1.width, player1.height);

    ctx.fillStyle = player2.color;
    ctx.fillRect(player2.x, player2.y, player2.width, player2.height);
}

function drawBall() {
    ctx.fillStyle = ball.color;
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
    ctx.fill();
}

function drawScores() {
    ctx.font = '30px Arial';
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.fillText(player1.score, canvas.width / 4, 50);
    ctx.fillText(player2.score, 3 * canvas.width / 4, 50);
}

function drawPowerUps() {
    powerUps.forEach(powerUp => {
        switch (powerUp.type) {
            case 'increasePaddle': ctx.fillStyle = '#0f0'; break; // Green
            case 'decreasePaddle': ctx.fillStyle = '#f00'; break; // Red
            case 'increaseSpeed':  ctx.fillStyle = '#00f'; break; // Blue
            case 'decreaseSpeed':  ctx.fillStyle = '#ff0'; break; // Yellow
        }
        ctx.fillRect(powerUp.x, powerUp.y, powerUp.size, powerUp.size);
    });
}

function drawActivePowerUps() {
    if (activePowerUps.length > 0) {
        ctx.font = '14px Arial';
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'left';

        ctx.fillText('Active Power-ups:', 10, canvas.height - 60);

        activePowerUps.forEach((powerUp, index) => {
            const timeLeft = Math.ceil((powerUp.endTime - Date.now()) / 1000);
            ctx.fillText(`${powerUp.type} (${timeLeft}s)`, 10, canvas.height - 40 + (index * 20));
        });
    }
}

function drawCenterLine() {
    ctx.strokeStyle = '#fff';
    ctx.setLineDash([10, 10]);
    ctx.beginPath();
    ctx.moveTo(canvas.width / 2, 0);
    ctx.lineTo(canvas.width / 2, canvas.height);
    ctx.stroke();
    ctx.setLineDash([]);
}

// Main draw function
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    drawCenterLine();
    drawPaddles();
    drawBall();
    drawScores();
    drawPowerUps();
    drawActivePowerUps();

    if (paused) {
        ctx.font = '40px Arial';
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
    }
}

// Main update function
function update(dt) {
    if (paused) return;

    // Remember where the paddles were so we can derive their velocity (spin)
    player1.prevY = player1.y;
    player2.prevY = player2.y;

    handleInput(dt);

    if (singlePlayer) {
        aiMove(dt);
    }

    updateBall(dt);
    spawnPowerUp(dt);
    checkPowerUpCollision();
    updatePowerUps();
}

// Game loop -------------------------------------------------------------------
let lastTime = 0;

function gameLoop(now) {
    // dt is expressed in 60fps-frame units and capped to avoid huge post-stall jumps
    const dt = Math.min((now - lastTime) / (1000 / 60), DT_CAP);
    lastTime = now;

    if (dt > 0) update(dt);
    draw();
    requestAnimationFrame(gameLoop);
}

// Event listeners for settings ------------------------------------------------
document.getElementById('player1Color').addEventListener('change', (e) => {
    player1.color = e.target.value;
});

document.getElementById('player2Color').addEventListener('change', (e) => {
    player2.color = e.target.value;
});

document.getElementById('pauseButton').addEventListener('click', () => {
    paused = !paused;
    document.getElementById('pauseButton').textContent = paused ? 'Resume' : 'Pause';
});

// Game mode selection
document.querySelectorAll('input[name="mode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        singlePlayer = e.target.value === 'single';
        resetBall();
    });
});

// Difficulty selection
document.getElementById('difficultySelect').addEventListener('change', (e) => {
    difficulty = e.target.value;
});

// Initialize game
window.onload = () => {
    player1.color = document.getElementById('player1Color').value;
    player2.color = document.getElementById('player2Color').value;

    resetBall();
    lastTime = performance.now();
    requestAnimationFrame(gameLoop);
};
