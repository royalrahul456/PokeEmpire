// POKEEMPIRE V3 - Telegram WebApp Client Engine

let tg = window.Telegram ? window.Telegram.WebApp : null;

let userCoins = 12450;
let userGems = 320;
let userBP = 1245;

document.addEventListener('DOMContentLoaded', () => {
  if (tg) {
    tg.expand();
    tg.ready();
    tg.setHeaderColor('#0b0f1d');
    tg.setBackgroundColor('#02040a');

    // Extract Telegram User Info
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const u = tg.initDataUnsafe.user;
      const userNameEl = document.getElementById('userName');
      if (userNameEl) userNameEl.innerText = u.first_name || u.username || "Ace Trainer";
    }
  }

  initParticleCanvas();
});

// Particle Background Canvas
function initParticleCanvas() {
  const canvas = document.getElementById('particleCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  class Particle {
    constructor() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.size = Math.random() * 2.5 + 1;
      this.speedY = Math.random() * -0.6 - 0.2;
      this.color = Math.random() > 0.5 ? 'rgba(250, 204, 21, 0.5)' : 'rgba(192, 132, 252, 0.4)';
    }
    update() {
      this.y += this.speedY;
      if (this.y < 0) {
        this.y = canvas.height;
        this.x = Math.random() * canvas.width;
      }
    }
    draw() {
      ctx.fillStyle = this.color;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  for (let i = 0; i < 40; i++) particles.push(new Particle());

  function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(animateParticles);
  }
  animateParticles();
}

// Navigation Tab Router
window.switchTab = function(tabName) {
  document.querySelectorAll('[id^="screen-"]').forEach(s => s.classList.add('hidden'));
  const activeScreen = document.getElementById('screen-' + tabName);
  if (activeScreen) activeScreen.classList.remove('hidden');

  document.querySelectorAll('[id^="tab-"]').forEach(b => {
    b.className = "flex flex-col items-center text-slate-400";
  });
  const activeBtn = document.getElementById('tab-' + tabName);
  if (activeBtn) activeBtn.className = "flex flex-col items-center text-amber-400 font-bold";

  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.impactOccurred('light');
  }
};

// Currency Updates
window.updateCurrencyDisplay = function() {
  const globalCoins = document.getElementById('globalCoins');
  if (globalCoins) globalCoins.innerText = userCoins.toLocaleString();
  document.querySelectorAll('.displayCoins').forEach(el => el.innerText = userCoins.toLocaleString());
};

// Toast Alerts
window.triggerToast = function(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.remove('opacity-0', 'translate-y-[-10px]');
  toast.classList.add('opacity-100');
  setTimeout(() => {
    toast.classList.remove('opacity-100');
    toast.classList.add('opacity-0');
  }, 2200);

  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.notificationOccurred('success');
  }
};

// Quest Claiming
window.claimReward = function(btn, amount) {
  userCoins += amount;
  window.updateCurrencyDisplay();
  btn.innerText = 'CLAIMED!';
  btn.disabled = true;
  btn.className = "bg-emerald-500 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs";
  window.triggerToast(`Claimed Reward: +${amount} 🪙 Coins!`);
};

// Market Buying
window.buyMarketItem = function(name, price) {
  if (userCoins >= price) {
    userCoins -= price;
    window.updateCurrencyDisplay();
    window.triggerToast(`Purchased ${name} for 🪙 ${price.toLocaleString()} Coins!`);
  } else {
    window.triggerToast(`Insufficient Coins for ${name}!`);
  }
};

// Pokémon Modal Stats Viewer
window.openPokeDetail = function(name, pokeId, rarity, cp, lv, iv) {
  document.getElementById('modalName').innerText = name;
  document.getElementById('modalRarity').innerText = rarity.toUpperCase();
  document.getElementById('modalCP').innerText = cp;
  document.getElementById('modalLv').innerText = lv;
  document.getElementById('modalIV').innerText = iv + '%';
  document.getElementById('modalIVBar').style.width = iv + '%';
  document.getElementById('modalImg').src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${pokeId}.png`;
  document.getElementById('pokeModal').classList.remove('hidden');

  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.selectionChanged();
  }
};

window.closePokeDetail = function() {
  document.getElementById('pokeModal').classList.add('hidden');
};

window.triggerBattleSim = function(mode) {
  window.triggerToast(`Starting ${mode} Match... ⚔️`);
};
