const playerACanvas = document.getElementById('mocz-canvas');
const playerBCanvas = document.getElementById('mocz-canvas2');
const stopaAImg = document.getElementById('stopA');
const stopaBImg = document.getElementById('stopB');

const playAreaWidth = 3000;
const playAreaHeight = 3000;
var feetRisenDown = false;

var canvasWidth = window.innerWidth / 2;
var canvasHeight = window.innerHeight;

playerACanvas.width = canvasWidth;
playerACanvas.height = canvasHeight;
playerBCanvas.width = canvasWidth;
playerBCanvas.height = canvasHeight;

var pepper_pattern = null;
var papaj_pattern = null;

var playerAState = {
    ctx: null,
    x: 0,
    y: 0,
    moveDirection: 0,
    feetDiff: -1,
    lastUpdate: Date.now(),
    trail: [],
    angle: 0,
    cameraX: 0,
    cameraY: 0,
    tailGradient: null,
    bgGradient: null,
    win: false,
};
var playerBState = {
    ctx: null,
    x: 0,
    y: 0,
    moveDirection: 0,
    feetDiff: -1,
    lastUpdate: Date.now(),
    trail: [],
    angle: 0,
    cameraX: 0,
    cameraY: 0,
    tailGradient: null,
    bgGradient: null,
    win: false,
};

function resetPlayerStates() {
    playerAState.x = playAreaWidth / 2 - 500;
    playerAState.y = playAreaHeight / 2;
    playerAState.ctx = playerACanvas.getContext('2d');
    playerAState.cameraX = 0;
    playerAState.cameraY = 0;
    playerAState.trail = [];

    playerAState.tailGradient = playerAState.ctx.createLinearGradient(0, 0, playerACanvas.width * 0.9, playerACanvas.height * 0.8);
    playerAState.tailGradient.addColorStop(0, "pink");
    playerAState.tailGradient.addColorStop(0.1, "orange");
    playerAState.tailGradient.addColorStop(0.2, "magenta");
    playerAState.tailGradient.addColorStop(0.6, "violet");
    playerAState.tailGradient.addColorStop(1, "blue");

    playerAState.bgGradient = '#e2e2e2';
    playerBState.x = playAreaWidth / 2 + 500;
    playerBState.y = playAreaHeight / 2;
    playerBState.ctx = playerBCanvas.getContext('2d');

    playerBState.tailGradient = playerBState.ctx.createLinearGradient(0, 0, playerACanvas.width * 0.9, playerACanvas.height * 0.6);
    playerBState.tailGradient.addColorStop(0, "green");
    playerBState.tailGradient.addColorStop(0.2, "blue");
    playerBState.tailGradient.addColorStop(0.6, "teal");
    playerBState.tailGradient.addColorStop(1, "red");

    playerBState.bgGradient = '#d2d2d2';

    playerBState.cameraX = 0;
    playerBState.cameraY = 0;
    playerBState.trail = [];
}

const playerSize = 10;
const moveDistance = 5; // Adjust this value to control the speed of movement
const moveTimeout = 10; // ms

// Game states
const STATE_START = 'start';
const STATE_ACTIVE = 'active';
const STATE_GAMEOVER = 'gameover';
const STATE_DEMO = 'demo';

var currentGameState = STATE_START;

// Camera properties
const CAMERA_SPEED = 3;

// Function to draw the player line
function drawPlayer(activePlayer, drawPlayer) {
    var { x, y, angle } = drawPlayer;
    var { ctx, cameraX, cameraY } = activePlayer;
    ctx.beginPath();
    ctx.moveTo(x - cameraX, y - cameraY);
    const endX = x + Math.cos(angle) * playerSize;
    const endY = y + Math.sin(angle) * playerSize;
    ctx.lineTo(endX - cameraX, endY - cameraY);
    ctx.stroke();
}

// Function to update the trail

function updateTrail(activePlayer) {
    var { x, y } = activePlayer;
    activePlayer.trail.push({ x, y });
}

// Function to draw the trail
function drawTrail(activePlayer, tailPlayer) {
    var { trail } = tailPlayer;
    var { ctx, cameraX, cameraY } = activePlayer;

    // Fill with gradient
    ctx.strokeStyle = tailPlayer.tailGradient;
    ctx.lineWidth = playerSize;
    ctx.lineCap = 'round';

    ctx.beginPath();
    ctx.moveTo(trail[0].x - cameraX, trail[0].y - cameraY);
    for (var i = 1; i < trail.length; i++) {
        ctx.lineTo(trail[i].x - cameraX, trail[i].y - cameraY);
    }
    ctx.stroke();
}

// Function to update the camera position

function updateCamera(activePlayer) {
    const targetX = activePlayer.x - canvasWidth / 2;
    const targetY = activePlayer.y - canvasHeight / 2;

    activePlayer.cameraX += (targetX - activePlayer.cameraX) / CAMERA_SPEED;
    activePlayer.cameraY += (targetY - activePlayer.cameraY) / CAMERA_SPEED;

    // Ensure the camera stays within the play area bounds
    activePlayer.cameraX = Math.max(0, Math.min(playAreaWidth - canvasWidth, activePlayer.cameraX));
    activePlayer.cameraY = Math.max(0, Math.min(playAreaHeight - canvasHeight, activePlayer.cameraY));
}

function ensureGameStart() {
    if (currentGameState == STATE_START) {
        currentGameState = STATE_ACTIVE;
    }

    if (currentGameState == STATE_GAMEOVER && feetRisenDown) {
        resetPlayerStates();
        currentGameState = STATE_ACTIVE;
    }
}

// Function to handle arrow key events
function handleArrowKeys(event) {
    if (currentGameState == STATE_START) {
        currentGameState = STATE_ACTIVE;
    }
    const arrowKey = event.key;

    switch (event.key) {
        case 'ArrowLeft':
            playerBState.moveDirection = -1;
            break;
        case 'ArrowRight':
            playerBState.moveDirection = 1;
            break;
        case 'a':
            playerAState.moveDirection = -1;
            break;
        case 'd':
            playerAState.moveDirection = 1;
            break;
    }
}

function handleKeyUp(event) {
    switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowRight':
            playerBState.moveDirection = 0;
            break;
        case 'a':
        case 'b':
            playerAState.moveDirection = 0;
            break;
    }
}

// Attach arrow key event listener to the window
window.addEventListener('keydown', handleArrowKeys);
window.addEventListener('keyup', handleKeyUp);


function updateMove(activePlayer) {
    if (activePlayer.feetDiff == -1) {
        // binary input
        if (activePlayer.moveDirection < 0) {
            activePlayer.angle -= Math.PI / 180 * 5
        }

        else if (activePlayer.moveDirection > 0) {
            activePlayer.angle += Math.PI / 180 * 5
        }

    } else {
        if (activePlayer.feetDiff < 0) {
            activePlayer.angle -= Math.PI / 180 * (Math.abs(activePlayer.feetDiff) * 10)
        }

        if (activePlayer.feetDiff > 0) {
            activePlayer.angle += Math.PI / 180 * (Math.abs(activePlayer.feetDiff) * 10)
        }
    }

    // Move the player forward in the direction it's facing
    activePlayer.x += Math.cos(activePlayer.angle) * moveDistance;
    activePlayer.y += Math.sin(activePlayer.angle) * moveDistance;
}


// Main game loop
function gameLoop(activePlayer) {
    var timeDelta = Date.now() - activePlayer.lastUpdate;

    if (timeDelta > moveTimeout) {
        activePlayer.lastUpdate = Date.now();
        updateMove(activePlayer);
        updateTrail(activePlayer);
    }

    updateCamera(activePlayer);
    activePlayer.ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    activePlayer.ctx.fillStyle = activePlayer.bgGradient;
    activePlayer.ctx.fillRect(0, 0, canvasWidth, canvasHeight);
    if (papaj_pattern) {
        activePlayer.ctx.drawImage(papaj_pattern, -activePlayer.cameraX, - activePlayer.cameraY, playAreaWidth, 30); // Or at whatever offset you like
        activePlayer.ctx.drawImage(papaj_pattern, - activePlayer.cameraX, - activePlayer.cameraY, 30, playAreaHeight); // Or at whatever offset you like
        activePlayer.ctx.drawImage(papaj_pattern, playAreaWidth - activePlayer.cameraX - 30, - activePlayer.cameraY, 30, playAreaHeight); // Or at whatever offset you like
        activePlayer.ctx.drawImage(papaj_pattern, -activePlayer.cameraX, playAreaHeight - 30 - activePlayer.cameraY, playAreaWidth, 30); // Or at whatever offset you like
    }

    if (playerAState.trail.length) {
        drawTrail(activePlayer, playerAState);
        drawPlayer(activePlayer, playerAState);
    }

    if (playerBState.trail.length) {
        drawTrail(activePlayer, playerBState);
        drawPlayer(activePlayer, playerBState);
    }

    activePlayer.ctx.strokeStyle = 'black';
    activePlayer.ctx.lineWidth = 4;
    activePlayer.ctx.lineCap = 'square';

    if (activePlayer == playerAState) {
        activePlayer.ctx.beginPath();
        activePlayer.ctx.moveTo(canvasWidth - 2, 0);
        activePlayer.ctx.lineTo(canvasWidth - 2, canvasHeight);
        activePlayer.ctx.stroke();
    }
}

function detectOutOfBoundsCollision(activePlayer) {
    var { x, y } = activePlayer;
    // detect the bounds
    if (x > (playAreaWidth - 30) || y > (playAreaHeight - 30)) {
        return true
    }

    if (x < 30 || y < 30) {
        return true
    }

    return false;
}

function detectTrailCollisions(activePlayer, combinedTrail) {
    // return false;
    const { x, y } = activePlayer;
    const closePoints = combinedTrail.filter((point) => Math.abs(point.x - x) < 15 && Math.abs(point.y - y) < 15);

    if (closePoints.length > 10) {
        for (i = 0; i < closePoints.length - 1; i++) {
            const pointA = closePoints[i];
            const pointB = closePoints[i + 1];

            const distanceToA = Math.sqrt(Math.pow(pointA.x - x, 2) + Math.pow(pointA.y - y, 2))
            const distanceToB = Math.sqrt(Math.pow(pointB.x - x, 2) + Math.pow(pointB.y - y, 2))
            const distanceBetweenPoints = Math.sqrt(Math.pow(pointA.x - pointB.x, 2) + Math.pow(pointA.y - pointB.y, 2))

            if (Math.abs((distanceToA + distanceToB) - distanceBetweenPoints) < playerSize) {
                return true
            }
        }
    }

    return false;
}

// @brief collision detect
// @returns bool collision detect
function detectCollisions() {
    const combinedTrail = [...playerBState.trail, ...playerAState.trail];

    if (detectTrailCollisions(playerAState, combinedTrail) || detectOutOfBoundsCollision(playerAState)) {
        playerAState.win = false;
        playerBState.win = true;
        return true;
    }

    if (detectTrailCollisions(playerBState, combinedTrail) || detectOutOfBoundsCollision(playerBState)) {
        playerBState.win = false;
        playerAState.win = true;
        return true;
    }

    return false
}

function renderStart(activeCtx, offset = 0) {
    activeCtx.clearRect(0, 0, playerACanvas.width, playerACanvas.height);
    const grd = activeCtx.createLinearGradient(0, 0, playerACanvas.width * 0.9, playerACanvas.height * 0.8);
    grd.addColorStop(0, "yellow");
    grd.addColorStop(0.5, "brown");
    grd.addColorStop(1, "yellow");

    // Fill with gradient
    activeCtx.fillStyle = grd;
    activeCtx.fillRect(0, 0, playerACanvas.width, playerACanvas.height);

    activeCtx.fillStyle = 'white';
    activeCtx.font = '150px Comic Sans MS'
    activeCtx.fillText("achtung die stoopke", 150 - offset, 150);
    activeCtx.font = '90px Comic Sans MS'
    activeCtx.textBaseline = "hanging";
    activeCtx.fillText("podnieś stupke aby zacząć", 150 - offset, 400);
    activeCtx.fillStyle = 'white'

    if (pepper_pattern) {
        activeCtx.drawImage(pepper_pattern, (playerACanvas.width / 2) - offset, (playerACanvas.height / 2) + 50); // Or at whatever offset you like
    }
}

function renderGameOver(activeCtx, offset = 0) {
    activeCtx.clearRect(0, 0, playerACanvas.width, playerACanvas.height);
    activeCtx.clearRect(0, 0, playerBCanvas.width, playerBCanvas.height);

    if (playerAState.win) {
        activeCtx.fillText("stupka A <3", 50, 50);
    }

    if (playerBState.win) {
        activeCtx.fillText("stupka B <3", 50, 50);
    }
}

function renderLoop() {
    switch (currentGameState) {
        case STATE_ACTIVE:
            gameLoop(playerAState);
            gameLoop(playerBState);
            break;
        case STATE_START:
            renderStart(playerAState.ctx, 0);
            renderStart(playerBState.ctx, canvasWidth)
            break;
        case STATE_GAMEOVER:
            renderGameOver(playerAState.ctx, 0);
            renderGameOver(playerBState.ctx, canvasWidth)
            break;
        default:
    }

    if (detectCollisions()) {
        currentGameState = STATE_GAMEOVER;
    }

    requestAnimationFrame(renderLoop);
}

// Start the game loop
window.addEventListener('resize', () => {
    playerACanvas.width = window.innerWidth / 2;
    playerACanvas.height = window.innerHeight;
    playerBCanvas.width = window.innerWidth / 2;
    playerBCanvas.height = window.innerHeight;
})

resetPlayerStates();
renderLoop();

var img = new Image;
img.src = "peppe.png"
img.onload = function () {
    pepper_pattern = img;
};


var papaj = new Image;
papaj.src = "oczy.png"
papaj.onload = function () {
    papaj_pattern = papaj;
};

// Stoopkarz api connection
const stoopkarzURL = "ws://localhost:8888/websocket";

let stoopkarzWS;

function reconnect() {
    stoopkarzWS = new WebSocket(stoopkarzURL);

    stoopkarzWS.onopen = ((ev) => {
        console.log("Connected");
        console.log(ev);
    })

    stoopkarzWS.onmessage = ((msg) => {
        const jsonMSG = JSON.parse(msg.data)

        switch (jsonMSG.type) {
            case 'players':
                if (jsonMSG['secondary']) {
                    if (jsonMSG?.secondary?.foot_image_data) {
                        stopaAImg.src = jsonMSG?.secondary?.foot_image_data;
                    }
                    if (jsonMSG.secondary.foot_diff > 0.15) {
                        ensureGameStart()
                        feetRisenDown = false;
                    } else if (jsonMSG.secondary.foot_diff < -0.15) {
                        ensureGameStart();
                        feetRisenDown = false;
                    } else {
                        feetRisenDown = true;
                    }
                    playerAState.feetDiff = jsonMSG.secondary.foot_diff;
                }

                if (jsonMSG['primary']) {
                    if (jsonMSG?.primary?.foot_image_data) {
                        stopaBImg.src = jsonMSG?.primary?.foot_image_data;
                    }
                    if (jsonMSG.primary.foot_diff > 0.15) {
                        feetRisenDown = false;
                        ensureGameStart()
                    } else if (jsonMSG.primary.foot_diff < -0.15) {
                        feetRisenDown = false;
                        ensureGameStart();
                    } else {
                        feetRisenDown = true;
                    }
                    playerBState.feetDiff = jsonMSG.primary.foot_diff;
                }
                break;
        }
    })

    stoopkarzWS.onclose = (msg) => {
        setTimeout(reconnect, 1000)
    }
}

reconnect();
