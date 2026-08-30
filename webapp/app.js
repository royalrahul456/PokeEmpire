// POKEEMPIRE V3 - Telegram WebApp Client Engine with Full Pokédex Database Integration

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

    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const u = tg.initDataUnsafe.user;
      const userNameEl = document.getElementById('userName');
      if (userNameEl) userNameEl.innerText = u.first_name || u.username || "Ace Trainer";
    }
  }

  initParticleCanvas();
  renderPokedex('all');
  renderBag();
});

// Render Dynamic Pokédex Catalog
function renderPokedex(tierFilter, searchQuery = '') {
  const container = document.getElementById('pokedexGrid');
  if (!container) return;
  container.innerHTML = '';

  const query = searchQuery.toLowerCase();

  POKEDEX_DATA.forEach(poke => {
    if (tierFilter !== 'all' && poke.tier.toLowerCase() !== tierFilter.toLowerCase()) return;
    if (query && !poke.name.toLowerCase().includes(query) && !poke.types.some(t => t.toLowerCase().includes(query))) return;

    const glowClass = getGlowClass(poke.tier);
    const cardHtml = `
      <div onclick="openPokeDetailByName('${poke.name}')" class="glass-card p-1.5 ${glowClass} text-center cursor-pointer hover:scale-105 transition relative">
        ${poke.isShiny ? '<span class="absolute top-1 right-1 text-[9px]">✨</span>' : ''}
        <span class="text-[8px] text-amber-300 font-bold block text-left">#${String(poke.id).padStart(3, '0')}</span>
        <div class="w-12 h-12 mx-auto my-0.5">
          <img src="${poke.img}" class="w-full h-full object-contain poke-img-bounce">
        </div>
        <div class="font-bold text-[9px] text-white truncate">${poke.name}</div>
        <div class="text-[7px] text-slate-400 font-semibold uppercase">${poke.tier}</div>
      </div>
    `;
    container.innerHTML += cardHtml;
  });
}

function getGlowClass(tier) {
  switch (tier.toLowerCase()) {
    case 'mythical': return 'card-rose-glow';
    case 'legendary': return 'card-gold-glow';
    case 'epic': return 'card-purple-glow';
    case 'rare': return 'card-sky-glow';
    case 'uncommon': return 'card-emerald-glow';
    default: return 'border-white/10';
  }
}

// Render My Pokémon Bag
function renderBag() {
  const container = document.getElementById('bagGrid');
  if (!container) return;
  container.innerHTML = '';

  const bagMonsters = POKEDEX_DATA.filter(p => p.caught);
  bagMonsters.forEach(poke => {
    const glowClass = getGlowClass(poke.tier);
    const cardHtml = `
      <div onclick="openPokeDetailByName('${poke.name}')" class="glass-card p-1.5 ${glowClass} text-center cursor-pointer hover:scale-105 transition relative">
        ${poke.isShiny ? '<span class="absolute top-1 right-1 text-[9px]">✨</span>' : ''}
        <span class="text-[8px] text-amber-300 font-bold block text-left">CP ${poke.hp * 30 + poke.atk * 20}</span>
        <div class="w-12 h-12 mx-auto my-0.5">
          <img src="${poke.img}" class="w-full h-full object-contain poke-img-bounce">
        </div>
        <div class="font-bold text-[9px] text-white truncate">${poke.name}</div>
        <div class="text-[7px] text-slate-400">Lv. ${Math.floor(poke.spAtk / 2.5)}</div>
      </div>
    `;
    container.innerHTML += cardHtml;
  });
}

// Search Pokedex
window.filterPokedex = function() {
  const query = document.getElementById('pokedexSearch').value;
  renderPokedex(currentTier, query);
};

let currentTier = 'all';
window.filterDexTier = function(tier) {
  currentTier = tier;
  document.querySelectorAll('[id^="dexTier-"]').forEach(btn => {
    btn.className = "px-2.5 py-1 rounded-lg bg-slate-800 text-slate-400 shrink-0";
  });
  const activeBtn = document.getElementById('dexTier-' + tier);
  if (activeBtn) activeBtn.className = "px-2.5 py-1 rounded-lg bg-amber-400 text-slate-950 font-bold shrink-0";

  renderPokedex(tier);
};

// Open Pokédex Detail Modal
window.openPokeDetailByName = function(name) {
  const poke = POKEDEX_DATA.find(p => p.name.toLowerCase() === name.toLowerCase());
  if (!poke) return;

  document.getElementById('modalName').innerText = poke.name;
  document.getElementById('modalRarity').innerText = poke.tier.toUpperCase();
  document.getElementById('modalHP').innerText = poke.hp;
  document.getElementById('modalAtk').innerText = poke.atk;
  document.getElementById('modalDef').innerText = poke.def;
  document.getElementById('modalSpd').innerText = poke.spd;

  document.getElementById('barHP').style.width = Math.min(100, (poke.hp / 120) * 100) + '%';
  document.getElementById('barAtk').style.width = Math.min(100, (poke.atk / 150) * 100) + '%';
  document.getElementById('barDef').style.width = Math.min(100, (poke.def / 120) * 100) + '%';
  document.getElementById('barSpd').style.width = Math.min(100, (poke.spd / 150) * 100) + '%';

  const typesContainer = document.getElementById('modalTypes');
  typesContainer.innerHTML = poke.types.map(t => `<span class="bg-slate-800 text-amber-300 border border-amber-400/30 text-[9px] px-1.5 py-0.2 rounded font-bold">${t}</span>`).join('');

  document.getElementById('modalEvo').innerText = poke.evolution.join(' ➔ ');
  document.getElementById('modalImg').src = poke.img;
  document.getElementById('pokeModal').classList.remove('hidden');

  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.selectionChanged();
  }
};

window.closePokeDetail = function() {
  document.getElementById('pokeModal').classList.add('hidden');
};

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
};

window.claimReward = function(btn, amount) {
  userCoins += amount;
  window.updateCurrencyDisplay();
  btn.innerText = 'CLAIMED!';
  btn.disabled = true;
  btn.className = "bg-emerald-500 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs";
  window.triggerToast(`Claimed Reward: +${amount} 🪙 Coins!`);
};

window.buyMarketItem = function(name, price) {
  if (userCoins >= price) {
    userCoins -= price;
    window.updateCurrencyDisplay();
    window.triggerToast(`Purchased ${name} for 🪙 ${price.toLocaleString()} Coins!`);
  } else {
    window.triggerToast(`Insufficient Coins for ${name}!`);
  }
};

window.triggerBattleSim = function(mode) {
  window.triggerToast(`Starting ${mode} Arena Match... ⚔️`);
};

window.updateCurrencyDisplay = function() {
  const globalCoins = document.getElementById('globalCoins');
  if (globalCoins) globalCoins.innerText = userCoins.toLocaleString();
  document.querySelectorAll('.displayCoins').forEach(el => el.innerText = userCoins.toLocaleString());
};
