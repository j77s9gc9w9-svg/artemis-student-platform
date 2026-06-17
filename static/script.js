// --- Language Switcher Dictionary (EN / BG) ---
const translations = {
    en: {
        brand: "static",
        subtitle: "Your Campus, Your Events",
        home: "Home",
        events: "Events",
        clubs: "Clubs",
        about: "About Us",
        login: "Log In",
        signup: "Sign Up",
        tagline: "Discover. Participate.",
        title: "Make <br><span>Memories.</span>",
        desc: "static is your go-to platform for discovering exciting campus events, connecting with people and creating unforgettable experiences.",
        explore: 'Explore Events <i class="fa-solid fa-arrow-right"></i>',
        club: '<i class="fa-solid fa-users"></i> Join a Club'
    },
    bg: {
        brand: "Евентър",
        subtitle: "Твоят кампус, Твоите събития",
        home: "Начало",
        events: "Събития",
        clubs: "Клубове",
        about: "За нас",
        login: "Вход",
        signup: "Регистрация",
        tagline: "Откривай. Участвай.",
        title: "Създавай <br><span>Спомени.</span>",
        desc: "static е твоята платформа за откриване на вълнуващи събития в университета, създаване на контакти и незабравими преживявания.",
        explore: 'Виж Събитията <i class="fa-solid fa-arrow-right"></i>',
        club: '<i class="fa-solid fa-users"></i> Влез в клуб'
    }
};

function switchLanguage(lang) {
    // Update active button state style classes 
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
        if(btn.textContent.toLowerCase() === lang) {
            btn.classList.add('active');
        }
    });

    // Populate DOM nodes text mapping strings
    document.getElementById('nav-brand').textContent = translations[lang].brand;
    document.getElementById('nav-subtitle').textContent = translations[lang].subtitle;
    document.getElementById('nav-home').textContent = translations[lang].home;
    document.getElementById('nav-events').textContent = translations[lang].events;
    document.getElementById('nav-clubs').textContent = translations[lang].clubs;
    document.getElementById('nav-about').textContent = translations[lang].about;
    document.getElementById('btn-login').textContent = translations[lang].login;
    document.getElementById('btn-signup').textContent = translations[lang].signup;
    document.getElementById('hero-tagline').textContent = translations[lang].tagline;
    document.getElementById('hero-title').innerHTML = translations[lang].title;
    document.getElementById('hero-desc').textContent = translations[lang].desc;
    document.getElementById('btn-explore').innerHTML = translations[lang].explore;
    document.getElementById('btn-club').innerHTML = translations[lang].club;
}

// --- HTML5 Canvas Physics Engine for Bubbly Effect ---
const canvas = document.getElementById('bubble-canvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('visual-box');

let bubblesArray = [];

function setCanvasSize() {
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;
}
window.addEventListener('resize', setCanvasSize);
setCanvasSize();

class Bubble {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = canvas.height + Math.random() * 100;
        this.radius = Math.random() * 12 + 4;
        this.speedY = Math.random() * 1.2 + 0.4;
        this.speedX = Math.sin(this.radius) * 0.4;
        
        const colors = ['rgba(99, 102, 241, ', 'rgba(168, 85, 247, ', 'rgba(129, 140, 248, '];
        this.colorBase = colors[Math.floor(Math.random() * colors.length)];
        this.opacity = Math.random() * 0.4 + 0.2;
    }

    update() {
        this.y -= this.speedY;
        this.x += this.speedX;
        this.speedX += Math.sin(this.y / 30) * 0.02;

        if (this.y + this.radius < 0) {
            this.y = canvas.height + this.radius + Math.random() * 20;
            this.x = Math.random() * canvas.width;
            this.speedY = Math.random() * 1.2 + 0.4;
        }
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = this.colorBase + this.opacity + ')';
        ctx.fill();
    }
}

function initBubbles() {
    bubblesArray = [];
    const numberOfBubbles = 35; 
    for (let i = 0; i < numberOfBubbles; i++) {
        bubblesArray.push(new Bubble());
    }
}

function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < bubblesArray.length; i++) {
        bubblesArray[i].update();
        bubblesArray[i].draw();
    }
    requestAnimationFrame(animate);
}

initBubbles();
animate();

container.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;
    
    for(let i=0; i<8; i++) {
        let burstBubble = new Bubble();
        burstBubble.x = clickX;
        burstBubble.y = clickY;
        burstBubble.speedY = Math.random() * 3 + 1;
        burstBubble.speedX = (Math.random() - 0.5) * 4;
        bubblesArray.push(burstBubble);
        if(bubblesArray.length > 60) bubblesArray.shift();
    }
});

async function register(email, password) {
    const response = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
    });

    return response.json();
}

