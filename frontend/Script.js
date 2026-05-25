/* ===== Navbar Scroll Effect (Glassmorphism) ===== */
const header = document.getElementById("header");

if (header) {
  window.addEventListener("scroll", () => {
    if (window.scrollY > 50) {
      header.classList.add("scrolled");
    } else {
      header.classList.remove("scrolled");
    }
  });
}

/* ===== Hamburger Menu Logic ===== */
const hamburger = document.getElementById('hamburger');
const navMenu = document.getElementById('nav-menu');

if (hamburger && navMenu) {
  hamburger.addEventListener('click', () => {
    navMenu.classList.toggle('active');
  });

  // Close menu when clicking a link
  document.querySelectorAll('.nav-link').forEach(n => n.addEventListener('click', () => {
    navMenu.classList.remove('active');
  }));
}

/* ===== Universal Scroll Reveal Engine ===== */
const reveals = document.querySelectorAll(".reveal");
const staggers = document.querySelectorAll(".reveal-stagger");
const leftSlides = document.querySelectorAll(".reveal-left");
const rightSlides = document.querySelectorAll(".reveal-right");

function revealOnScroll() {
  const windowHeight = window.innerHeight;
  const elementVisible = 100;

  const checkReveal = (elements) => {
    elements.forEach(el => {
      const top = el.getBoundingClientRect().top;
      if (top < windowHeight - elementVisible) {
        el.classList.add("active");
      }
    });
  };

  checkReveal(reveals);
  checkReveal(leftSlides);
  checkReveal(rightSlides);

  staggers.forEach((el, index) => {
    const top = el.getBoundingClientRect().top;
    if (top < windowHeight - elementVisible) {
      setTimeout(() => {
        el.classList.add("active");
      }, (index % 3) * 150);
    }
  });
}

window.addEventListener("scroll", revealOnScroll);
revealOnScroll(); 

/* ===== Active Menu Highlight ===== */
const sections = document.querySelectorAll("section");
const navLinks = document.querySelectorAll(".nav-link");

window.addEventListener("scroll", () => {
  let current = "";
  sections.forEach(section => {
    if (scrollY >= section.offsetTop - 150) {
      current = section.id;
    }
  });

  navLinks.forEach(link => {
    link.classList.remove("active");
    if (link.getAttribute("href") === `#${current}`) {
      link.classList.add("active");
    }
  });
});

/* ===== Dynamic Year ===== */
const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

/* ===== WhatsApp Form Logic ===== */
const quoteForm = document.getElementById("quoteForm");
if (quoteForm) quoteForm.addEventListener("submit", function (e) {
  e.preventDefault();

  const btn = this.querySelector("button");
  const btnText = document.getElementById("btnText");
  
  const name = document.getElementById("name").value;
  const org = document.getElementById("org").value;
  const category = document.getElementById("category").value;
  const mobile = document.getElementById("mobile").value;
  const email = document.getElementById("email").value;

  const originalText = btnText.textContent;
  btnText.textContent = "Processing...";
  btn.style.opacity = "0.7";

  setTimeout(() => {
    const msg = `*New Quotation Request* %0a---------------------------%0a*Name:* ${name}%0a*Organization:* ${org}%0a*Requirement:* ${category}%0a*Mobile:* ${mobile}%0a*Email:* ${email}`;
    
    const phoneNumber = "+918957783558"; 
    
    window.open(`https://wa.me/${phoneNumber}?text=${msg}`, "_blank");

    btn.style.opacity = "1";
    btnText.textContent = originalText;
    this.reset();
  }, 1000);
});

/* ===== Typewriter Effect (single safe implementation) ===== */
class TypeWriter {
  constructor(txtElement, words, wait = 3000) {
    this.txtElement = txtElement;
    this.words = words;
    this.txt = '';
    this.wordIndex = 0;
    this.wait = parseInt(wait, 10) || 3000;
    this.isDeleting = false;
    this.type();
  }

  type() {
    const current = this.wordIndex % this.words.length;
    const fullTxt = this.words[current] || '';

    if (this.isDeleting) {
      this.txt = fullTxt.substring(0, this.txt.length - 1);
    } else {
      this.txt = fullTxt.substring(0, this.txt.length + 1);
    }

    this.txtElement.innerHTML = `<span class="txt">${this.txt}</span>`;

    let typeSpeed = 100;
    if (this.isDeleting) typeSpeed /= 2;

    if (!this.isDeleting && this.txt === fullTxt) {
      typeSpeed = this.wait;
      this.isDeleting = true;
    } else if (this.isDeleting && this.txt === '') {
      this.isDeleting = false;
      this.wordIndex++;
      typeSpeed = 500;
    }

    setTimeout(() => this.type(), typeSpeed);
  }
}

// Init On DOM Load (single safe init)
document.addEventListener('DOMContentLoaded', function init() {
  const txtElement = document.querySelector('.txt-type');
  if (!txtElement) return; // nothing to do

  let words = [];
  try {
    words = JSON.parse(txtElement.getAttribute('data-words'));
  } catch (err) {
    // Fallback: try to split by comma if attribute is plain text
    const raw = txtElement.getAttribute('data-words') || '[]';
    words = raw.replace(/^\s+|\s+$/g, '').replace(/^\[|\]$/g, '').split(/\s*,\s*/).map(w => w.replace(/^\"|\"$/g, '')).filter(Boolean);
  }

  const wait = txtElement.getAttribute('data-wait') || 3000;
  if (!Array.isArray(words) || words.length === 0) return;
  new TypeWriter(txtElement, words, wait);
});