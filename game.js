// Canvas setup
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
canvas.width = 800;
canvas.height = 600;

// Game constants
const paddleWidth = 10;
const paddleHeight = 100;
const ballSize = 10;
const powerUpSize = 20;
const powerUpDuration = 5000; // 5 seconds

// Game objects
let player1 = {
    x: 0,
    y: canvas.height / 2 - paddleHeight / 2,
    width: paddleWidth,
    height: paddleHeight,
    color: '#fff',
    score: 0,
    originalHeight: paddleHeight
};

let player2 = {
    x: canvas.width - paddleWidth,
    y: canvas.height / 2 - paddleHeight / 2,
    width: paddleWidth,
    height: paddleHeight,
    color: '#fff',
    score: 0,
    originalHeight: paddleHeight
};

let ball = {
    x: canvas.width / 2,
    y: canvas.height / 2,
    size: ballSize,
    speedX: 5,
    speedY: 5,
    originalSpeedX: 5,
    originalSpeedY: 5,
    color: '#fff'
};

// Game state
let powerUps = [];
let activePowerUps = [];
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
    }
});

document.addEventListener('keyup', (e) => {
    if (keys.hasOwnProperty(e.key)) {
        keys[e.key] = false;
    }
});

// Handle paddle movement based on key states
function handleInput() {
    const paddleSpeed = 8;
    
    if (keys.w && player1.y > 0) {
        player1.y -= paddleSpeed;
    }
    if (keys.s && player1.y + player1.height < canvas.height) {
        player1.y += paddleSpeed;
    }
    
    if (!singlePlayer) {
        if (keys.ArrowUp && player2.y > 0) {
            player2.y -= paddleSpeed;
        }
        if (keys.ArrowDown && player2.y + player2.height < canvas.height) {
            player2.y += paddleSpeed;
        }
    }
}

// AI for player 2 in single-player mode
function aiMove() {
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
    
    // Add some randomness to make AI less perfect
    const reactionDelay = difficulty === 'hard' ? 0.1 : (difficulty === 'medium' ? 0.2 : 0.3);
    
    if (Math.random() > reactionDelay && ball.speedX > 0) {
        const paddleCenter = player2.y + player2.height / 2;
        const targetY = ball.y;
        
        if (paddleCenter < targetY - 10 && player2.y + player2.height < canvas.height) {
            player2.y += speed;
        } else if (paddleCenter > targetY + 10 && player2.y > 0) {
            player2.y -= speed;
        }
    }
}

// Update ball position and handle collisions
function updateBall() {
    // Move ball
    ball.x += ball.speedX;
    ball.y += ball.speedY;
    
    // Ball collision with top and bottom walls
    if (ball.y <= 0 || ball.y + ball.size >= canvas.height) {
        ball.speedY *= -1;
        // Audio commented out as requested
        // hitSound.play();
    }
    
    // Ball collision with paddles
    // Player 1 paddle
    if (
        ball.x <= player1.x + player1.width &&
        ball.y + ball.size >= player1.y &&
        ball.y <= player1.y + player1.height &&
        ball.speedX < 0
    ) {
        // Calculate angle based on where ball hits paddle
        const hitPosition = (ball.y - player1.y) / player1.height;
        const angle = (hitPosition - 0.5) * Math.PI / 2; // -45 to 45 degrees
        
        ball.speedX = Math.abs(ball.speedX);
        ball.speedY = ball.originalSpeedY * Math.sin(angle) * 1.5;
        
        // Audio commented out as requested
        // hitSound.play();
    }
    
    // Player 2 paddle
    if (
        ball.x + ball.size >= player2.x &&
        ball.y + ball.size >= player2.y &&
        ball.y <= player2.y + player2.height &&
        ball.speedX > 0
    ) {
        // Calculate angle based on where ball hits paddle
        const hitPosition = (ball.y - player2.y) / player2.height;
        const angle = (hitPosition - 0.5) * Math.PI / 2; // -45 to 45 degrees
        
        ball.speedX = -Math.abs(ball.speedX);
        ball.speedY = ball.originalSpeedY * Math.sin(angle) * 1.5;
        
        // Audio commented out as requested
        // hitSound.play();
    }
    
    // Ball out of bounds (scoring)
    if (ball.x + ball.size < 0) {
        player2.score++;
        // Audio commented out as requested
        // scoreSound.play();
        resetBall();
    } else if (ball.x > canvas.width) {
        player1.score++;
        // Audio commented out as requested
        // scoreSound.play();
        resetBall();
    }
}

// Reset ball to center after scoring
function resetBall() {
    ball.x = canvas.width / 2;
    ball.y = canvas.height / 2;
    
    // Randomize direction
    ball.speedX = ball.originalSpeedX * (Math.random() > 0.5 ? 1 : -1);
    ball.speedY = ball.originalSpeedY * (Math.random() > 0.5 ? 1 : -1);
}

// Power-up functions
function spawnPowerUp() {
    if (Math.random() < 0.005) { // 0.5% chance per frame
        const types = ['increasePaddle', 'decreasePaddle', 'increaseSpeed', 'decreaseSpeed'];
        const type = types[Math.floor(Math.random() * types.length)];
        
        // Ensure power-up spawns in playable area
        const x = Math.random() * (canvas.width - 100) + 50;
        const y = Math.random() * (canvas.height - 100) + 50;
        
        powerUps.push({
            x,
            y,
            size: powerUpSize,
            type
        });
    }
}

function checkPowerUpCollision() {
    powerUps.forEach((powerUp, index) => {
        if (
            ball.x < powerUp.x + powerUp.size &&
            ball.x + ball.size > powerUp.x &&
            ball.y < powerUp.y + powerUp.size &&
            ball.y + ball.size > powerUp.y
        ) {
            applyPowerUp(powerUp.type);
            powerUps.splice(index, 1);
            
            // Audio commented out as requested
            // powerUpSound.play();
        }
    });
}

function applyPowerUp(type) {
    const now = Date.now();
    
    switch (type) {
        case 'increasePaddle':
            player1.height = player1.originalHeight * 1.5;
            player2.height = player2.originalHeight * 1.5;
            activePowerUps.push({
                type,
                endTime: now + powerUpDuration,
                revert: () => {
                    player1.height = player1.originalHeight;
                    player2.height = player2.originalHeight;
                }
            });
            break;
        case 'decreasePaddle':
            player1.height = player1.originalHeight * 0.5;
            player2.height = player2.originalHeight * 0.5;
            activePowerUps.push({
                type,
                endTime: now + powerUpDuration,
                revert: () => {
                    player1.height = player1.originalHeight;
                    player2.height = player2.originalHeight;
                }
            });
            break;
        case 'increaseSpeed':
            ball.speedX *= 1.5;
            ball.speedY *= 1.5;
            activePowerUps.push({
                type,
                endTime: now + powerUpDuration,
                revert: () => {
                    ball.speedX = ball.originalSpeedX * Math.sign(ball.speedX);
                    ball.speedY = ball.originalSpeedY * Math.sign(ball.speedY);
                }
            });
            break;
        case 'decreaseSpeed':
            ball.speedX *= 0.5;
            ball.speedY *= 0.5;
            activePowerUps.push({
                type,
                endTime: now + powerUpDuration,
                revert: () => {
                    ball.speedX = ball.originalSpeedX * Math.sign(ball.speedX);
                    ball.speedY = ball.originalSpeedY * Math.sign(ball.speedY);
                }
            });
            break;
    }
}

function updatePowerUps() {
    const now = Date.now();
    
    // Check for expired power-ups
    for (let i = activePowerUps.length - 1; i >= 0; i--) {
        if (now >= activePowerUps[i].endTime) {
            activePowerUps[i].revert();
            activePowerUps.splice(i, 1);
        }
    }
}

// Draw functions
function drawPaddles() {
    // Player 1 paddle
    ctx.fillStyle = player1.color;
    ctx.fillRect(player1.x, player1.y, player1.width, player1.height);
    
    // Player 2 paddle
    ctx.fillStyle = player2.color;
    ctx.fillRect(player2.x, player2.y, player2.width, player2.height);
}

function drawBall() {
    ctx.fillStyle = ball.color;
    ctx.fillRect(ball.x, ball.y, ball.size, ball.size);
}

function drawScores() {
    ctx.font = '30px Arial';
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    
    // Player 1 score
    ctx.fillText(player1.score, canvas.width / 4, 50);
    
    // Player 2 score
    ctx.fillText(player2.score, 3 * canvas.width / 4, 50);
}

function drawPowerUps() {
    powerUps.forEach(powerUp => {
        switch (powerUp.type) {
            case 'increasePaddle':
                ctx.fillStyle = '#0f0'; // Green
                break;
            case 'decreasePaddle':
                ctx.fillStyle = '#f00'; // Red
                break;
            case 'increaseSpeed':
                ctx.fillStyle = '#00f'; // Blue
                break;
            case 'decreaseSpeed':
                ctx.fillStyle = '#ff0'; // Yellow
                break;
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
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw center line
    drawCenterLine();
    
    // Draw game objects
    drawPaddles();
    drawBall();
    drawScores();
    drawPowerUps();
    drawActivePowerUps();
    
    // Draw pause message if game is paused
    if (paused) {
        ctx.font = '40px Arial';
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
    }
}

// Main update function
function update() {
    if (paused) return;
    
    handleInput();
    
    if (singlePlayer) {
        aiMove();
    }
    
    updateBall();
    spawnPowerUp();
    checkPowerUpCollision();
    updatePowerUps();
}

// Game loop
function gameLoop() {
    update();
    draw();
    requestAnimationFrame(gameLoop);
}

// Event listeners for settings
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
    // Set initial colors from inputs
    player1.color = document.getElementById('player1Color').value;
    player2.color = document.getElementById('player2Color').value;
    
    // Start game loop
    gameLoop();
}; 