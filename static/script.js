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
        visionDesc: "To become the vibrant central hub for every campus organization, gathering, and student interaction across university facilities.",
        workspaceMode: '<i class="fa-solid fa-sliders"></i> Workspace View:',
        viewStudent: '<i class="fa-solid fa-user-graduate"></i> Student View',
        viewOrganizer: '<i class="fa-solid fa-user-gear"></i> Organizer Panel',
        studentTitle: "Campus Catalog",
        studentSubtitle: "Explore live, upcoming educational sessions and campus workshops.",
        statusAvail: "Available",
        statusFull: "Full (Waitlist Open)",
        spotsLeft: "Spots filled",
        waitlistCount: "Waitlist Size",
        btnRegister: "Register for Event",
        btnWaitlist: "Join Waitlist (FIFO)",
        orgTitleCreate: "Create New Event",
        lblTitle: "Event Title",
        lblCapacity: "Max Capacity",
        lblInitialState: "Initial State",
        lblDatetime: "Schedule Date & Time",
        lblLocation: "Location / Plain URL text",
        lblDescription: "Description",
        btnSaveDraft: "Save and Initialize Draft",
        orgTitleManage: "Active Operations Dashboard",
        badgePub: "Published",
        badgeDr: "Draft",
        btnCancelEv: '<i class="fa-solid fa-ban"></i> Cancel',
        btnPublishEv: '<i class="fa-solid fa-paper-plane"></i> Publish',
        lblConfirmedList: "Confirmed Registrations (18)",
        lblFifoWaitlist: "FIFO Queued Waitlist (4)"
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
        visionDesc: "Да се превърнем в централния и динамичен център за всяка студентска организация, събиране и взаимодействие в рамките на университета.",
        workspaceMode: '<i class="fa-solid fa-sliders"></i> Режим на изглед:',
        viewStudent: '<i class="fa-solid fa-user-graduate"></i> Студентски изглед',
        viewOrganizer: '<i class="fa-solid fa-user-gear"></i> Организаторски панел',
        studentTitle: "Каталог на кампуса",
        studentSubtitle: "Разгледайте активни събития, лекции и университетски семинари.",
        statusAvail: "Свободни места",
        statusFull: "Запълнено (Списък на чакащи)",
        spotsLeft: "Заети места",
        waitlistCount: "Размер на чакащите",
        btnRegister: "Регистрирай се за събитие",
        btnWaitlist: "Запиши се в списъка (FIFO)",
        orgTitleCreate: "Създай ново събитие",
        lblTitle: "Наименование на събитието",
        lblCapacity: "Максимален капацитет",
        lblInitialState: "Първоначално състояние",
        lblDatetime: "Планирана дата и час",
        lblLocation: "Локация / Текст линк",
        lblDescription: "Описание",
        btnSaveDraft: "Запази и инициирай чернова",
        orgTitleManage: "Табло за активни операции",
        badgePub: "Публикувано",
        badgeDr: "Чернова",
        btnCancelEv: '<i class="fa-solid fa-ban"></i> Отмени',
        btnPublishEv: '<i class="fa-solid fa-paper-plane"></i> Публикувай',
        lblConfirmedList: "Потвърдени регистрации (18)",
        lblFifoWaitlist: "FIFO Списък на чакащие (4)"
    }
};

function switchLanguage(lang) {
    // 1. Save language choice globally 
    localStorage.setItem('preferred_lang', lang);

    // 2. Clear out double-selection styling glitches completely
    const enBtn = document.getElementById('lang-en');
    const bgBtn = document.getElementById('lang-bg');
    
    if (enBtn && bgBtn) {
        if(lang === 'en') {
            enBtn.className = 'lang-btn px-3 py-1 rounded-full transition-all bg-indigo-600 text-white shadow-sm';
            bgBtn.className = 'lang-btn px-3 py-1 rounded-full transition-all text-slate-400 hover:text-white';
        } else {
            bgBtn.className = 'lang-btn px-3 py-1 rounded-full transition-all bg-indigo-600 text-white shadow-sm';
            enBtn.className = 'lang-btn px-3 py-1 rounded-full transition-all text-slate-400 hover:text-white';
        }
    }

    // 3. Fallback inline dynamic markup text substitution translations (.lang-text class elements)
    document.querySelectorAll('.lang-text').forEach(el => {
        if (el.classList.contains('event-title') || el.classList.contains('event-desc')) return;
        const text = el.getAttribute(`data-${lang}`);
        if (text) el.innerText = text;
    });

    // 4. Translate dynamic event items from backend databases if on events template page
    if (typeof eventTranslations !== 'undefined') {
        document.querySelectorAll('.event-card').forEach(card => {
            const titleEl = card.querySelector('.event-title');
            const descEl = card.querySelector('.event-desc');
            
            if (titleEl) {
                const englishTitle = titleEl.getAttribute('data-en');
                const translation = eventTranslations[englishTitle];
                
                if (lang === 'bg' && translation) {
                    titleEl.innerText = translation.bgTitle;
                    if (descEl) descEl.innerText = translation.bgDesc;
                } else {
                    titleEl.innerText = englishTitle;
                    if (descEl) descEl.innerText = descEl.getAttribute('data-en') || '';
                }
            }
        });
    }

    // 5. Update global structured element mappings securely via translations array keys
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

    if(document.getElementById('txt-workspace-mode')) document.getElementById('txt-workspace-mode').innerHTML = translations[lang].workspaceMode;
    if(document.getElementById('btn-view-student')) document.getElementById('btn-view-student').innerHTML = translations[lang].viewStudent;
    if(document.getElementById('btn-view-organizer')) document.getElementById('btn-view-organizer').innerHTML = translations[lang].viewOrganizer;
    if(document.getElementById('student-title')) document.getElementById('student-title').textContent = translations[lang].studentTitle;
    if(document.getElementById('student-subtitle')) document.getElementById('student-subtitle').textContent = translations[lang].studentSubtitle;
    if(document.getElementById('lbl-status-avail')) document.getElementById('lbl-status-avail').textContent = translations[lang].statusAvail;
    if(document.getElementById('lbl-status-full')) document.getElementById('lbl-status-full').textContent = translations[lang].statusFull;
    if(document.getElementById('lbl-spots-left')) document.getElementById('lbl-spots-left').textContent = translations[lang].spotsLeft;
    if(document.getElementById('lbl-waitlist-count')) document.getElementById('lbl-waitlist-count').textContent = translations[lang].waitlistCount;
    if(document.getElementById('btn-register-event')) document.getElementById('btn-register-event').textContent = translations[lang].btnRegister;
    if(document.getElementById('btn-join-waitlist')) document.getElementById('btn-join-waitlist').textContent = translations[lang].btnWaitlist;
    
    if(document.getElementById('org-title-create')) document.getElementById('org-title-create').textContent = translations[lang].orgTitleCreate;
    if(document.getElementById('lbl-title')) document.getElementById('lbl-title').textContent = translations[lang].lblTitle;
    if(document.getElementById('lbl-capacity')) document.getElementById('lbl-capacity').textContent = translations[lang].lblCapacity;
    if(document.getElementById('lbl-initial-state')) document.getElementById('lbl-initial-state').textContent = translations[lang].lblInitialState;
    if(document.getElementById('lbl-datetime')) document.getElementById('lbl-datetime').textContent = translations[lang].lblDatetime;
    if(document.getElementById('lbl-location')) document.getElementById('lbl-location').textContent = translations[lang].lblLocation;
    if(document.getElementById('lbl-description')) document.getElementById('lbl-description').textContent = translations[lang].lblDescription;
    if(document.getElementById('btn-save-draft')) document.getElementById('btn-save-draft').textContent = translations[lang].btnSaveDraft;
    
    if(document.getElementById('org-title-manage')) document.getElementById('org-title-manage').textContent = translations[lang].orgTitleManage;
    if(document.getElementById('badge-pub')) document.getElementById('badge-pub').textContent = translations[lang].badgePub;
    if(document.getElementById('badge-dr')) document.getElementById('badge-dr').textContent = translations[lang].badgeDr;
    if(document.getElementById('btn-cancel-ev')) document.getElementById('btn-cancel-ev').innerHTML = translations[lang].btnCancelEv;
    if(document.getElementById('btn-publish-ev')) document.getElementById('btn-publish-ev').innerHTML = translations[lang].btnPublishEv;
    if(document.getElementById('lbl-confirmed-list')) document.getElementById('lbl-confirmed-list').textContent = translations[lang].lblConfirmedList;
    if(document.getElementById('lbl-fifo-waitlist')) document.getElementById('lbl-fifo-waitlist').textContent = translations[lang].lblFifoWaitlist;
}

// --- Background Bubble Animation Engine ---
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

// --- Layout Configurations Initialization Hook ---
document.addEventListener('DOMContentLoaded', () => {
    // Force English fallback if no prior interaction history exists in local storage
    const savedLang = localStorage.getItem('preferred_lang') || 'en';
    switchLanguage(savedLang);

    // Process Dark/Light System Theme configuration
    const themeCheckbox = document.getElementById('theme-checkbox');
    const savedTheme = localStorage.getItem('theme');
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        document.documentElement.classList.add('dark');
        if (themeCheckbox) themeCheckbox.checked = true;
    }

    if (themeCheckbox) {
        themeCheckbox.addEventListener('change', () => {
            if (themeCheckbox.checked) {
                document.body.classList.add('dark-mode');
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
            }
        });
    }

    // Process Accessibility Font Size constraints
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