// POKEEMPIRE V3 - Dynamic Client Engine matching Bot Data Models

let tg = window.Telegram ? window.Telegram.WebApp : null;

let userCoins = 500;
let userGems = 10;
let userLevel = 1;
let userXP = 0;

document.addEventListener('DOMContentLoaded', () => {
  if (tg) {
    tg.expand();
    tg.ready();
    tg.setHeaderColor('#0b0f1d');
    tg.setBackgroundColor('#02040a');

    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const u = tg.initDataUnsafe.user;
      const userNameEl = document.getElementById('userName');
      if (userNameEl) userNameEl.innerText = u.first_name || u.username || "Trainer";
    }
  }

  initParticleCanvas();
  renderPokedex('all');
  renderShop();
  renderQuests();
  renderBag();
});

// Render Pokédex from monsters.json
function renderPokedex(tierFilter, searchQuery = '') {
  const container = document.getElementById('pokedexGrid');
  if (!container) return;
  container.innerHTML = '';

  const keys = Object.keys(MONSTERS_DB);
  const query = searchQuery.toLowerCase();

  keys.forEach(key => {
    const poke = MONSTERS_DB[key];
    if (tierFilter !== 'all' && poke.tier.toLowerCase() !== tierFilter.toLowerCase()) return;
    if (query && !poke.name.toLowerCase().includes(query) && !poke.types.some(t => t.toLowerCase().includes(query))) return;

    const imgUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${poke.id}.png`;
    const glowClass = getGlowClass(poke.tier);

    const cardHtml = `
      <div onclick="openPokeDetailKey('${key}')" class="glass-card p-1.5 ${glowClass} text-center cursor-pointer hover:scale-105 transition relative">
        <span class="text-[8px] text-amber-300 font-bold block text-left">#${String(poke.id).padStart(3, '0')}</span>
        <div class="w-12 h-12 mx-auto my-0.5">
          <img src="${imgUrl}" class="w-full h-full object-contain poke-img-bounce">
        </div>
        <div class="font-bold text-[9px] text-white truncate">${poke.name}</div>
        <div class="text-[7px] text-slate-400 uppercase">${poke.tier}</div>
      </div>
    `;
    container.innerHTML += cardHtml;
  });
}

// Render Shop from items.json
function renderShop() {
  const container = document.getElementById('shopList');
  if (!container) return;
  container.innerHTML = '';

  ITEMS_DB.forEach(item => {
    const cardHtml = `
      <div class="glass-card p-2 flex items-center justify-between border-white/10 hover:border-amber-400/40 transition">
        <div class="flex items-center space-x-2">
          <span class="text-xl">${item.icon}</span>
          <div>
            <div class="font-bold text-xs text-white">${item.name}</div>
            <div class="text-[9px] text-slate-400">${item.desc}</div>
          </div>
        </div>
        <button onclick="buyItem('${item.name}', ${item.price})" class="btn-gold px-2.5 py-1 rounded-lg text-[10px]">🪙 ${item.price}</button>
      </div>
    `;
    container.innerHTML += cardHtml;
  });
}

// Render Quests from quests.json
function renderQuests() {
  const container = document.getElementById('questsList');
  if (!container) return;
  container.innerHTML = '';

  QUESTS_DB.forEach(q => {
    const cardHtml = `
      <div class="glass-card p-2.5 space-y-1.5 border-white/10">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-[8px] bg-amber-400/20 text-amber-300 border border-amber-400/30 px-1.5 py-0.2 rounded font-bold uppercase">${q.type}</span>
            <div class="font-bold text-xs text-white mt-1">${q.name}</div>
            <div class="text-[9px] text-slate-400">${q.desc}</div>
          </div>
          <button onclick="claimQuestReward(this, ${q.rewardCoins}, ${q.rewardGems})" class="btn-gold px-2.5 py-1 rounded-lg text-[10px]">CLAIM +${q.rewardCoins}🪙</button>
        </div>
        <div class="text-[8px] text-emerald-400 font-semibold">REWARD: +${q.rewardCoins} 🪙 | +${q.rewardGems} 💎 | ${q.item}</div>
      </div>
    `;
    container.innerHTML += cardHtml;
  });
}

// Render Bag
function renderBag() {
  const container = document.getElementById('bagGrid');
  if (!container) return;
  container.innerHTML = '';

  const userCaught = ['pikachu', 'charizard', 'gyarados', 'gengar', 'lucario'];
  userCaught.forEach(key => {
    const poke = MONSTERS_DB[key];
    if (!poke) return;
    const imgUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${poke.id}.png`;
    const glowClass = getGlowClass(poke.tier);

    const cardHtml = `
      <div onclick="openPokeDetailKey('${key}')" class="glass-card p-1.5 ${glowClass} text-center cursor-pointer hover:scale-105 transition">
        <span class="text-[8px] text-amber-300 font-bold block text-left">CP ${poke.hp * 30 + poke.atk * 20}</span>
        <div class="w-12 h-12 mx-auto my-0.5">
          <img src="${imgUrl}" class="w-full h-full object-contain poke-img-bounce">
        </div>
        <div class="font-bold text-[9px] text-white truncate">${poke.name}</div>
        <div class="text-[7px] text-slate-400">Lv. 30</div>
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

// Search Pokedex
window.filterPokedex = function() {
  const query = document.getElementById('pokedexSearch').value;
  renderPokedex(currentTier, query);
};

let currentTier = 'all';
window.filterDexTier = function(tier) {
  currentTier = tier;
  document.querySelectorAll('[id^="dexTier-"]').forEach(btn => {
    btn.className = "px-2 py-0.5 rounded bg-slate-800 text-slate-400 shrink-0";
  });
  const activeBtn = document.getElementById('dexTier-' + tier);
  if (activeBtn) activeBtn.className = "px-2 py-0.5 rounded bg-amber-400 text-slate-950 font-bold shrink-0";

  renderPokedex(tier);
};

// Open Pokédex Detail Modal
window.openPokeDetailKey = function(key) {
  const poke = MONSTERS_DB[key];
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

  document.getElementById('modalEvo').innerText = poke.evo;
  document.getElementById('modalImg').src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${poke.id}.png`;
  document.getElementById('pokeModal').classList.remove('hidden');

  if (tg && tg.HapticFeedback) {
    tg.HapticFeedback.selectionChanged();
  }
};

window.closePokeDetail = function() {
  document.getElementById('pokeModal').classList.add('hidden');
};

// Canvas
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
      this.size = Math.random() * 2 + 1;
      this.speedY = Math.random() * -0.5 - 0.2;
      this.color = Math.random() > 0.5 ? 'rgba(250, 204, 21, 0.4)' : 'rgba(192, 132, 252, 0.3)';
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

  for (let i = 0; i < 30; i++) particles.push(new Particle());

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
  toast.classList.remove('opacity-0');
  toast.classList.add('opacity-100');
  setTimeout(() => {
    toast.classList.remove('opacity-100');
    toast.classList.add('opacity-0');
  }, 2000);
};

window.claimQuestReward = function(btn, coins, gems) {
  userCoins += coins;
  userGems += gems;
  window.updateCurrencyDisplay();
  btn.innerText = 'CLAIMED!';
  btn.disabled = true;
  btn.className = "bg-emerald-500 text-slate-950 font-bold px-2.5 py-1 rounded-lg text-[10px]";
  window.triggerToast(`Claimed +${coins} 🪙 and +${gems} 💎!`);
};

window.buyItem = function(name, price) {
  if (userCoins >= price) {
    userCoins -= price;
    window.updateCurrencyDisplay();
    window.triggerToast(`Bought ${name} for 🪙 ${price}!`);
  } else {
    window.triggerToast(`Need 🪙 ${price} Coins for ${name}!`);
  }
};

window.updateCurrencyDisplay = function() {
  const globalCoins = document.getElementById('globalCoins');
  if (globalCoins) globalCoins.innerText = userCoins.toLocaleString();
  const globalGems = document.getElementById('globalGems');
  if (globalGems) globalGems.innerText = userGems.toLocaleString();
};
