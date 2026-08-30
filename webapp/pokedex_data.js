// POKEEMPIRE V3 - Official Pokédex Database from monsters.json & pokemon_seeds.json

const POKEDEX_DATA = [
  {
    id: 1,
    name: "Bulbasaur",
    tier: "Uncommon",
    types: ["Grass", "Poison"],
    hp: 45, atk: 49, def: 49, spd: 45, spAtk: 65, spDef: 65,
    evolution: ["Bulbasaur", "Ivysaur (Lv. 16)", "Venusaur (Lv. 32)"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/1.png"
  },
  {
    id: 2,
    name: "Ivysaur",
    tier: "Rare",
    types: ["Grass", "Poison"],
    hp: 60, atk: 62, def: 63, spd: 60, spAtk: 80, spDef: 80,
    evolution: ["Bulbasaur", "Ivysaur", "Venusaur"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/2.png"
  },
  {
    id: 3,
    name: "Venusaur",
    tier: "Epic",
    types: ["Grass", "Poison"],
    hp: 80, atk: 82, def: 83, spd: 80, spAtk: 100, spDef: 100,
    evolution: ["Bulbasaur", "Ivysaur", "Venusaur"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/3.png"
  },
  {
    id: 4,
    name: "Charmander",
    tier: "Uncommon",
    types: ["Fire"],
    hp: 39, atk: 52, def: 43, spd: 65, spAtk: 60, spDef: 50,
    evolution: ["Charmander", "Charmeleon (Lv. 16)", "Charizard (Lv. 36)"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/4.png"
  },
  {
    id: 5,
    name: "Charmeleon",
    tier: "Rare",
    types: ["Fire"],
    hp: 58, atk: 64, def: 58, spd: 80, spAtk: 80, spDef: 65,
    evolution: ["Charmander", "Charmeleon", "Charizard"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/5.png"
  },
  {
    id: 6,
    name: "Charizard",
    tier: "Epic",
    types: ["Fire", "Flying"],
    hp: 78, atk: 84, def: 78, spd: 100, spAtk: 109, spDef: 85,
    evolution: ["Charmander", "Charmeleon", "Charizard"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png"
  },
  {
    id: 7,
    name: "Squirtle",
    tier: "Uncommon",
    types: ["Water"],
    hp: 44, atk: 48, def: 65, spd: 43, spAtk: 50, spDef: 64,
    evolution: ["Squirtle", "Wartortle (Lv. 16)", "Blastoise (Lv. 36)"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/7.png"
  },
  {
    id: 8,
    name: "Wartortle",
    tier: "Rare",
    types: ["Water"],
    hp: 59, atk: 63, def: 80, spd: 58, spAtk: 65, spDef: 80,
    evolution: ["Squirtle", "Wartortle", "Blastoise"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/8.png"
  },
  {
    id: 9,
    name: "Blastoise",
    tier: "Epic",
    types: ["Water"],
    hp: 79, atk: 83, def: 100, spd: 78, spAtk: 85, spDef: 105,
    evolution: ["Squirtle", "Wartortle", "Blastoise"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/9.png"
  },
  {
    id: 25,
    name: "Pikachu",
    tier: "Legendary",
    types: ["Electric"],
    hp: 35, atk: 55, def: 40, spd: 90, spAtk: 50, spDef: 50,
    evolution: ["Pichu", "Pikachu", "Raichu (Thunder Stone)"],
    caught: true,
    isShiny: true,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
  },
  {
    id: 26,
    name: "Raichu",
    tier: "Epic",
    types: ["Electric"],
    hp: 60, atk: 90, def: 55, spd: 110, spAtk: 90, spDef: 80,
    evolution: ["Pichu", "Pikachu", "Raichu"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/26.png"
  },
  {
    id: 94,
    name: "Gengar",
    tier: "Epic",
    types: ["Ghost", "Poison"],
    hp: 60, atk: 65, def: 60, spd: 110, spAtk: 130, spDef: 75,
    evolution: ["Gastly", "Haunter", "Gengar"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/94.png"
  },
  {
    id: 130,
    name: "Gyarados",
    tier: "Rare",
    types: ["Water", "Flying"],
    hp: 95, atk: 125, def: 79, spd: 81, spAtk: 60, spDef: 100,
    evolution: ["Magikarp", "Gyarados (Lv. 20)"],
    caught: true,
    isShiny: true,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/130.png"
  },
  {
    id: 133,
    name: "Eevee",
    tier: "Rare",
    types: ["Normal"],
    hp: 55, atk: 55, def: 50, spd: 55, spAtk: 45, spDef: 65,
    evolution: ["Eevee", "Vaporeon", "Jolteon", "Flareon", "Sylveon"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png"
  },
  {
    id: 149,
    name: "Dragonite",
    tier: "Legendary",
    types: ["Dragon", "Flying"],
    hp: 91, atk: 134, def: 95, spd: 80, spAtk: 100, spDef: 100,
    evolution: ["Dratini", "Dragonair", "Dragonite"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/149.png"
  },
  {
    id: 150,
    name: "Mewtwo",
    tier: "Mythical",
    types: ["Psychic"],
    hp: 106, atk: 110, def: 90, spd: 130, spAtk: 154, spDef: 90,
    evolution: ["Mewtwo"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png"
  },
  {
    id: 151,
    name: "Mew",
    tier: "Mythical",
    types: ["Psychic"],
    hp: 100, atk: 100, def: 100, spd: 100, spAtk: 100, spDef: 100,
    evolution: ["Mew"],
    caught: false,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/151.png"
  },
  {
    id: 248,
    name: "Tyranitar",
    tier: "Epic",
    types: ["Rock", "Dark"],
    hp: 100, atk: 134, def: 110, spd: 61, spAtk: 95, spDef: 100,
    evolution: ["Larvitar", "Pupitar", "Tyranitar"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/248.png"
  },
  {
    id: 282,
    name: "Gardevoir",
    tier: "Rare",
    types: ["Psychic", "Fairy"],
    hp: 68, atk: 65, def: 65, spd: 80, spAtk: 125, spDef: 115,
    evolution: ["Ralts", "Kirlia", "Gardevoir"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/282.png"
  },
  {
    id: 384,
    name: "Rayquaza",
    tier: "Mythical",
    types: ["Dragon", "Flying"],
    hp: 105, atk: 150, def: 90, spd: 95, spAtk: 150, spDef: 90,
    evolution: ["Rayquaza"],
    caught: true,
    isShiny: true,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/384.png"
  },
  {
    id: 448,
    name: "Lucario",
    tier: "Epic",
    types: ["Fighting", "Steel"],
    hp: 70, atk: 110, def: 70, spd: 90, spAtk: 115, spDef: 70,
    evolution: ["Riolu", "Lucario"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png"
  },
  {
    id: 700,
    name: "Sylveon",
    tier: "Rare",
    types: ["Fairy"],
    hp: 95, atk: 65, def: 65, spd: 60, spAtk: 110, spDef: 130,
    evolution: ["Eevee", "Sylveon"],
    caught: true,
    isShiny: false,
    img: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/700.png"
  }
];
