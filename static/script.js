const translations = {
    en: {
        brand: "Eventer",
        subtitle: "Your Campus, Your Events",
        home: "Home",
        events: "Events",
        clubs: "Clubs",
        about: "About Us",
        login: "Log In",
        signup: "Sign Up",
        tagline: "Discover. Participate.",
        title: "Make <br><span>Memories.</span>",
        desc: "Eventer is your go-to platform for discovering exciting campus events, connecting with people and creating unforgettable experiences.",
        explore: 'Explore Events <i class="fa-solid fa-arrow-right"></i>',
        club: '<i class="fa-solid fa-users"></i> Join a Club',
        aboutTitle: "Connecting <br><span>Our Campus.</span>",
        aboutLead: "We believe that university life is more than just lectures and exams. It is about the connections you build, the passions you discover, and the memories you make.",
        missionTitle: "Our Mission",
        missionDesc: "To simplify event management on campus and boost student engagement by providing a seamless, unified space for student life activities.",
        visionTitle: "Our Vision",
        visionDesc: "To become the vibrant central hub for every campus organization, gathering, and student interaction across university facilities."
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
        desc: "Eventer е твоята платформа за откриване на вълнуващи събития в университета, създаване на контакти и незабравими преживявания.",
        explore: 'Виж Събитията <i class="fa-solid fa-arrow-right"></i>',
        club: '<i class="fa-solid fa-users"></i> Влез в клуб',
        aboutTitle: "Свързваме <br><span>Нашия Кампус.</span>",
        aboutLead: "Вярваме, че университетският живот е нещо повече от лекции и изпити. Той е за връзките, които изграждате, страстите, които откривате, и спомените, които създавате.",
        missionTitle: "Нашата Мисия",
        missionDesc: "Да опростим управлението на събития в кампуса и да увеличим ангажираността на студентите, като предоставим единно пространство за студентски активности.",
        visionTitle: "Нашата Визия",
        visionDesc: "Да се превърнем в централния и динамичен център за всяка студентска организация, събиране и взаимодействие в рамките на университета."
    }
};

function switchLanguage(lang) {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        if(btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(lang)) {
            btn.classList.add('active');
        } else if (btn.getAttribute('onclick')) {
            btn.classList.remove('active');
        }
    });

    if(document.getElementById('nav-brand')) document.getElementById('nav-brand').textContent = translations[lang].brand;
    if(document.getElementById('nav-subtitle')) document.getElementById('nav-subtitle').textContent = translations[lang].subtitle;
    if(document.getElementById('nav-home')) document.getElementById('nav-home').textContent = translations[lang].home;
    if(document.getElementById('nav-events')) document.getElementById('nav-events').textContent = translations[lang].events;
    if(document.getElementById('nav-clubs')) document.getElementById('nav-clubs').textContent = translations[lang].clubs;
    if(document.getElementById('nav-about')) document.getElementById('nav-about').textContent = translations[lang].about;
    if(document.getElementById('btn-login')) document.getElementById('btn-login').textContent = translations[lang].login;
    if(document.getElementById('btn-signup')) document.getElementById('btn-signup').textContent = translations[lang].signup;
    
    if(document.getElementById('hero-tagline')) document.getElementById('hero-tagline').textContent = translations[lang].tagline;
    if(document.getElementById('hero-title')) document.getElementById('hero-title').innerHTML = translations[lang].title;
    if(document.getElementById('hero-desc')) document.getElementById('hero-desc').textContent = translations[lang].desc;
    if(document.getElementById('btn-explore')) document.getElementById('btn-explore').innerHTML = translations[lang].explore;
    if(document.getElementById('btn-club')) document.getElementById('btn-club').innerHTML = translations[lang].club;

    if(document.getElementById('about-title')) document.getElementById('about-title').innerHTML = translations[lang].aboutTitle;
    if(document.getElementById('about-lead-text')) document.getElementById('about-lead-text').textContent = translations[lang].aboutLead;
    if(document.getElementById('card-mission-title')) document.getElementById('card-mission-title').textContent = translations[lang].missionTitle;
    if(document.getElementById('card-mission-desc')) document.getElementById('card-mission-desc').textContent = translations[lang].missionDesc;
    if(document.getElementById('card-vision-title')) document.getElementById('card-vision-title').textContent = translations[lang].visionTitle;
    if(document.getElementById('card-vision-desc')) document.getElementById('card-vision-desc').textContent = translations[lang].visionDesc;
}

const canvas = document.getElementById('bubble-canvas');
const container = document.getElementById('visual-box');

if (canvas && container) {
    const ctx = canvas.getContext('2d');
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
}

async function register(email, password) {
    const response = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
    });
    return response.json();
}

document.addEventListener('DOMContentLoaded', () => {
    const themeCheckbox = document.getElementById('theme-checkbox');
    const savedTheme = localStorage.getItem('theme');
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (themeCheckbox) themeCheckbox.checked = true;
    }

    if (themeCheckbox) {
        themeCheckbox.addEventListener('change', () => {
            if (themeCheckbox.checked) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('theme', 'light');
            }
        });
    }

    const decreaseBtn = document.getElementById('font-decrease');
    const increaseBtn = document.getElementById('font-increase');
    const htmlElement = document.documentElement;
    
    let currentSize = parseInt(localStorage.getItem('fontSize')) || 16;
    htmlElement.style.fontSize = currentSize + 'px';

    if (decreaseBtn) {
        decreaseBtn.addEventListener('click', () => {
            if (currentSize > 12) {
                currentSize -= 2;
                htmlElement.style.fontSize = currentSize + 'px';
                localStorage.setItem('fontSize', currentSize);
            }
        });
    }

    if (increaseBtn) {
        increaseBtn.addEventListener('click', () => {
            if (currentSize < 24) {
                currentSize += 2;
                htmlElement.style.fontSize = currentSize + 'px';
                localStorage.setItem('fontSize', currentSize);
            }
        });
    }
});