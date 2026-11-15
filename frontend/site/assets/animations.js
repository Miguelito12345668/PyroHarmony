/**
 * PyroHarmony — Animations du site vitrine
 * 1. Barre de progression de scroll
 * 2. Compteurs animés (stats)
 * 3. Reveal au scroll
 * 4. Smooth scroll pour les liens internes
 */

// --- 1. Barre de progression de scroll ---
function initScrollProgress() {
  const bar = document.createElement('div');
  bar.className = 'scroll-progress';
  document.body.appendChild(bar);

  window.addEventListener('scroll', () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    bar.style.width = progress + '%';
  }, { passive: true });
}

// --- 2. Compteurs animés ---
function animateCounter(el, target, duration = 1500, suffix = '') {
  const start = 0;
  const startTime = performance.now();
  const isNumeric = !isNaN(parseFloat(target));
  
  if (!isNumeric) return;
  
  const numericTarget = parseFloat(target.toString().replace(/[^\d.]/g, ''));
  const originalText = target.toString();
  const nonNumeric = originalText.replace(/[\d.]/g, '');
  
  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 4);
    const value = start + (numericTarget - start) * eased;
    
    if (Number.isInteger(numericTarget)) {
      el.textContent = Math.round(value).toLocaleString('fr-FR') + nonNumeric;
    } else {
      el.textContent = value.toFixed(1).toLocaleString('fr-FR') + nonNumeric;
    }
    
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function initCounters() {
  const counters = document.querySelectorAll('.stat-value, [data-counter]');
  if (!counters.length) return;
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !entry.target.dataset.animated) {
        entry.target.dataset.animated = 'true';
        animateCounter(entry.target, entry.target.textContent);
      }
    });
  }, { threshold: 0.5 });
  
  counters.forEach(c => observer.observe(c));
}

// --- 3. Reveal au scroll ---
function initReveal() {
  const elements = document.querySelectorAll('.reveal');
  if (!elements.length) return;
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
  
  elements.forEach(el => observer.observe(el));
}

// --- 4. Smooth scroll ---
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const target = document.querySelector(link.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

// --- 5. Typing effect pour le titre hero ---
function initTyping() {
  const titles = document.querySelectorAll('.hero h1');
  if (!titles.length) return;
  
  titles.forEach(title => {
    const text = title.textContent;
    const html = title.innerHTML;
    // Ne pas faire le typing si le titre contient du HTML structuré (highlight)
    if (html.includes('<')) return;
    
    title.textContent = '';
    let i = 0;
    function type() {
      if (i < text.length) {
        title.textContent += text.charAt(i);
        i++;
        setTimeout(type, 40);
      }
    }
    setTimeout(type, 500);
  });
}

// --- Init au chargement ---
document.addEventListener('DOMContentLoaded', () => {
  initScrollProgress();
  initReveal();
  initCounters();
  initSmoothScroll();
});