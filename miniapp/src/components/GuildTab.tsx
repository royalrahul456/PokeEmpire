"use client";

import React, { useState, useEffect } from "react";
import { PlayerProfile, GuildData } from "@/types";
import {
  Shield,
  Users,
  PlusCircle,
  Search,
  Award,
  Coins,
  Crown,
  ChevronRight,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Flag,
  X,
  Edit2
} from "lucide-react";
import { triggerTelegramHaptic } from "@/lib/telegram";
import { TelegramAnimatedEmoji } from "@/components/TelegramAnimatedEmoji";

interface GuildTabProps {
  player: PlayerProfile | null;
  onRefreshPlayer: () => Promise<void>;
}

const GUILD_FLAG_PRESETS = [
  { id: "dragon", name: "Imperial Dragon", desc: "Legendary Dragonfire Aura" },
  { id: "strawhat", name: "Straw Hat Pirates", desc: "King of the Seas" },
  { id: "phoenix", name: "Blazing Phoenix", desc: "Immortal Flame Rebirth" },
  { id: "crown", name: "Royal Sovereign", desc: "Imperial Pokémon Royalty" },
  { id: "lightning", name: "Thunder Strike", desc: "Surge & Electric Current" },
  { id: "samurai", name: "Cyber Samurai", desc: "Neon Blade Discipline" },
  { id: "jedi_blue", name: "Galactic Order", desc: "Cyan Hyper Crystal" },
  { id: "wolf", name: "Iron Wolf", desc: "Pack Alpha Resilience" },
  { id: "shield", name: "Golden Aegis", desc: "Impervious Guild Defense" },
  { id: "skull", name: "Shadow Skull", desc: "Dark Void Syndicate" },
  { id: "star", name: "Celestial Star", desc: "Astral Championship Glow" },
  { id: "jedi_grey", name: "Grey Guardian", desc: "Silver Swords Mastery" },
];

export const GuildTab: React.FC<GuildTabProps> = ({ player, onRefreshPlayer }) => {
  const [myGuild, setMyGuild] = useState<GuildData | null>(null);
  const [allGuilds, setAllGuilds] = useState<GuildData[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showFlagModal, setShowFlagModal] = useState(false);
  const [customEmojiInput, setCustomEmojiInput] = useState("");
  const [newGuildName, setNewGuildName] = useState("");
  const [newGuildTag, setNewGuildTag] = useState("");
  const [newGuildFlag, setNewGuildFlag] = useState("shield");
  const [actionMsg, setActionMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchGuildData();
  }, [player?.id]);

  const fetchGuildData = async () => {
    setLoading(true);
    try {
      if (player?.id) {
        const myRes = await fetch(`/api/guild/my?user_id=${player.id}`);
        const myData = await myRes.json();
        if (myData.in_guild && myData.guild) {
          setMyGuild(myData.guild);
        } else {
          setMyGuild(null);
        }
      }

      const listRes = await fetch(`/api/guild/list`);
      const listData = await listRes.json();
      if (listData.guilds) {
        setAllGuilds(listData.guilds);
      }
    } catch (e) {
      console.warn("Error fetching guild data:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGuild = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!player) return;
    setSubmitting(true);
    setErrorMsg("");
    setActionMsg("");
    triggerTelegramHaptic("medium");

    try {
      const res = await fetch("/api/guild/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: player.id,
          name: newGuildName,
          tag: newGuildTag,
          flag: newGuildFlag,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Failed to create guild");
        triggerTelegramHaptic("error");
        return;
      }

      setActionMsg(data.message || "Guild created successfully!");
      triggerTelegramHaptic("success");
      setShowCreateModal(false);
      setNewGuildName("");
      setNewGuildTag("");
      await fetchGuildData();
      await onRefreshPlayer();
    } catch (err: any) {
      setErrorMsg(err.message || "Network error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleJoinGuild = async (guildId: number) => {
    if (!player) return;
    setErrorMsg("");
    setActionMsg("");
    triggerTelegramHaptic("medium");

    try {
      const res = await fetch("/api/guild/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: player.id,
          guild_id: guildId,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.error || "Failed to join guild");
        triggerTelegramHaptic("error");
        return;
      }

      setActionMsg("Successfully joined the guild!");
      triggerTelegramHaptic("success");
      await fetchGuildData();
      await onRefreshPlayer();
    } catch (err: any) {
      setErrorMsg(err.message || "Network error joining guild");
    }
  };

  // Change Animated Guild Flag
  const handleUpdateFlag = async (flagId: string) => {
    if (!player || !myGuild) return;
    triggerTelegramHaptic("medium");
    setSubmitting(true);

    try {
      const res = await fetch("/api/guild/set-flag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: player.id,
          guildId: myGuild.id,
          flag: flagId,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        setErrorMsg(data.error || "Failed to update flag");
        triggerTelegramHaptic("error");
      } else {
        triggerTelegramHaptic("success");
        setActionMsg("🎉 Official Telegram Animated Guild Flag updated!");
        setMyGuild({ ...myGuild, flag: flagId });
        setShowFlagModal(false);
        await fetchGuildData();
      }
    } catch {
      setErrorMsg("Network error updating flag.");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredGuilds = allGuilds.filter(
    (g) =>
      g.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      g.tag.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isGuildLeader = Boolean(myGuild && player && (myGuild.owner_id === player.id));

  return (
    <div className="space-y-4 pb-32 animate-fade-in relative">
      {/* Notifications */}
      {actionMsg && (
        <div className="p-3 rounded-2xl liquid-glass-accent border-emerald-500/40 text-emerald-600 dark:text-emerald-400 text-xs font-bold flex items-center space-x-2 animate-fade-in shadow-lg">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
          <span>{actionMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-3 rounded-2xl liquid-glass border-red-500/40 text-red-500 text-xs font-bold flex items-center space-x-2 animate-fade-in shadow-lg">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ============================================================== */}
      {/* 🚩 TELEGRAM ANIMATED GUILD FLAG MODAL                          */}
      {/* ============================================================== */}
      {showFlagModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="liquid-glass-accent w-full max-w-sm rounded-[32px] p-5 space-y-4 border border-violet-500/50 shadow-2xl relative max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-2 border-b border-white/10">
              <div className="flex items-center space-x-2">
                <Flag className="w-4 h-4 text-violet-400" />
                <h3 className="font-black text-sm text-slate-900 dark:text-white">
                  Telegram Animated Guild Flags
                </h3>
              </div>
              <button
                onClick={() => setShowFlagModal(false)}
                className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Equip an official animated banner for your guild! It displays with optical glass aura across rankings and player tags.
            </p>

            {/* Custom Telegram Animated Emoji ID Input */}
            <div className="space-y-1.5 pt-1">
              <label className="text-[11px] font-bold text-slate-400">
                Custom Telegram Emoji ID or Tag
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={customEmojiInput}
                  onChange={(e) => setCustomEmojiInput(e.target.value)}
                  placeholder="e.g. 5269563867305879894"
                  className="flex-1 liquid-glass px-3.5 py-2 rounded-xl text-xs text-slate-900 dark:text-white outline-none placeholder:text-slate-500 font-mono"
                />
                <button
                  onClick={() => handleUpdateFlag(customEmojiInput)}
                  disabled={!customEmojiInput.trim() || submitting}
                  className="btn-violet px-3 py-2 rounded-xl text-xs font-black disabled:opacity-50"
                >
                  Apply
                </button>
              </div>
            </div>

            {/* Official Animated Presets Grid */}
            <div className="space-y-2 pt-2">
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 block">
                Official Animated Crests ({GUILD_FLAG_PRESETS.length})
              </span>
              <div className="grid grid-cols-2 gap-2.5">
                {GUILD_FLAG_PRESETS.map((flag) => {
                  const isCurrent = (myGuild?.flag || "shield").toLowerCase() === flag.id;
                  return (
                    <div
                      key={flag.id}
                      onClick={() => handleUpdateFlag(flag.id)}
                      data-glass="true"
                      className={`liquid-glass p-3 rounded-2xl flex flex-col items-center text-center space-y-1.5 cursor-pointer transition-all active:scale-95 group hover:-translate-y-1 ${
                        isCurrent
                          ? "border-amber-400/80 shadow-lg shadow-amber-400/20 bg-amber-500/10"
                          : "hover:border-violet-500/50"
                      }`}
                    >
                      <TelegramAnimatedEmoji emoji={flag.id} size="md" />
                      <div>
                        <span className="font-bold text-[11px] text-slate-900 dark:text-white block truncate max-w-[120px]">
                          {flag.name}
                        </span>
                        <span className="text-[9px] text-slate-400 block truncate max-w-[120px]">
                          {flag.desc}
                        </span>
                      </div>
                      {isCurrent && (
                        <span className="text-[8px] font-black uppercase px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 shadow">
                          Equipped
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* VIEW A: PLAYER IS IN A GUILD                                   */}
      {/* ============================================================== */}
      {myGuild ? (
        <div className="space-y-4">
          {/* Main Guild Banner Card with Animated Crest */}
          <div
            data-glass="true"
            data-config='{"blurAmount":0.35,"refraction":0.55,"cornerRadius":28,"edgeHighlight":0.18}'
            className="liquid-glass-accent glass-sheen rounded-[28px] p-5 relative overflow-hidden animate-slide-up"
          >
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center space-x-3.5">
                {/* Large Scale Telegram Animated Flag */}
                <div className="relative group cursor-pointer" onClick={() => isGuildLeader && setShowFlagModal(true)}>
                  <TelegramAnimatedEmoji
                    emoji={myGuild.flag || "shield"}
                    size="lg"
                    className="hover:scale-105 transition-transform duration-300"
                  />
                  {isGuildLeader && (
                    <span className="absolute -bottom-1 -right-1 bg-violet-600 text-white p-1 rounded-full shadow border border-white/50 group-hover:scale-110 transition-transform">
                      <Edit2 className="w-2.5 h-2.5" />
                    </span>
                  )}
                </div>

                <div>
                  <div className="flex items-center space-x-2">
                    <span className="bg-violet-500/20 text-violet-600 dark:text-violet-300 text-[10px] font-black px-2 py-0.5 rounded-md border-t border-white/40">
                      [{myGuild.tag}]
                    </span>
                    <h3 className="font-black text-lg text-slate-900 dark:text-white">{myGuild.name}</h3>
                  </div>
                  <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">
                    <span>Guild Lv.{myGuild.level}</span>
                    <span>•</span>
                    <span>Leader: {myGuild.owner_name}</span>
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-xs font-bold text-amber-500 flex items-center justify-end space-x-1">
                  <span>🪙</span>
                  <span className="font-mono">{myGuild.treasury.toLocaleString()}</span>
                </div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Treasury</span>
              </div>
            </div>

            {/* Leader Action: Change Animated Flag Button */}
            {isGuildLeader && (
              <div className="mt-3 pt-2.5 border-t border-white/10 flex justify-end">
                <button
                  onClick={() => setShowFlagModal(true)}
                  className="liquid-glass-pill px-3 py-1 rounded-xl text-[10px] font-bold text-violet-600 dark:text-violet-300 flex items-center space-x-1.5 hover:scale-105 active:scale-95 transition-all"
                >
                  <Sparkles className="w-3 h-3 text-amber-400" />
                  <span>Customize Animated Flag</span>
                </button>
              </div>
            )}

            {/* Announcement Box */}
            {myGuild.announcement && (
              <div className="mt-3.5 p-3 rounded-2xl bg-violet-500/10 border-t border-white/20 text-xs text-violet-900 dark:text-violet-200 relative z-10">
                <div className="flex items-center space-x-1.5 font-bold mb-0.5 text-violet-600 dark:text-violet-400">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Guild Notice</span>
                </div>
                <p>{myGuild.announcement}</p>
              </div>
            )}

            {/* Passive Guild Perks */}
            <div className="mt-4 pt-3 border-t border-violet-500/15 grid grid-cols-2 gap-2 text-xs relative z-10">
              <div className="flex items-center space-x-2 text-slate-700 dark:text-slate-300">
                <span className="text-amber-500 font-bold">✨ +5%</span>
                <span>Shiny Catch Rate</span>
              </div>
              <div className="flex items-center space-x-2 text-slate-700 dark:text-slate-300">
                <span className="text-emerald-500 font-bold">🪙 +10%</span>
                <span>Coin Boost</span>
              </div>
            </div>
          </div>

          {/* Members List */}
          <div className="space-y-2 animate-slide-up delay-150">
            <div className="flex justify-between items-center px-1">
              <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Guild Members ({myGuild.members?.length || 0}/{myGuild.max_members})
              </span>
            </div>

            <div className="space-y-2">
              {myGuild.members?.map((member, mIdx) => (
                <div
                  key={`${member.user_id}-${mIdx}`}
                  data-glass="true"
                  className="liquid-glass rounded-2xl p-3 flex items-center justify-between hover:scale-[1.01] transition-all"
                >
                  <div className="flex items-center space-x-2.5 relative z-10">
                    <div className="w-8 h-8 rounded-xl bg-violet-500/10 flex items-center justify-center font-bold text-xs text-violet-600 dark:text-violet-300">
                      {member.nickname.charAt(0)}
                    </div>
                    <div>
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-xs text-slate-900 dark:text-white">
                          {member.nickname}
                        </span>
                        {member.role === "leader" ? (
                          <span className="text-[9px] bg-gradient-to-r from-amber-400 to-yellow-500 text-slate-950 font-black px-1.5 py-0.2 rounded shadow-sm flex items-center space-x-0.5">
                            <Crown className="w-2.5 h-2.5 inline" />
                            <span>LEADER</span>
                          </span>
                        ) : member.role === "co_leader" ? (
                          <span className="text-[9px] bg-violet-500 text-white font-black px-1.5 py-0.2 rounded shadow-sm">
                            CO-LEADER
                          </span>
                        ) : null}
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        Lv.{member.level} • @{member.username}
                      </span>
                    </div>
                  </div>

                  <span className="text-[10px] text-slate-400 font-mono relative z-10">
                    {new Date(member.joined_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* ============================================================== */
        /* VIEW B: PLAYER HAS NO GUILD - DIRECTORY & CREATION             */
        /* ============================================================== */
        <div className="space-y-4">
          {/* Join or Create CTA Card */}
          <div
            data-glass="true"
            className="liquid-glass-accent glass-sheen rounded-[28px] p-5 text-center space-y-3 relative overflow-hidden animate-slide-up"
          >
            <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center shadow-xl shadow-violet-500/30 border-t border-white/50">
              <TelegramAnimatedEmoji emoji="dragon" size="md" />
            </div>

            <div>
              <h3 className="font-black text-base text-slate-900 dark:text-white">
                Join a Guild or Found an Empire
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs mx-auto leading-relaxed">
                Unlock official animated guild flags, boost your team shiny rate by +5%, and earn bonus coins with your comrades!
              </p>
            </div>

            <button
              onClick={() => {
                triggerTelegramHaptic("medium");
                setShowCreateModal(true);
              }}
              className="btn-gold px-6 py-2.5 rounded-2xl text-xs font-black uppercase tracking-wider inline-flex items-center space-x-2 shadow-lg shadow-amber-500/20 active:scale-95"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Found a New Guild (500k 🪙)</span>
            </button>
          </div>

          {/* Search Directory */}
          <div className="liquid-glass px-3.5 py-2.5 rounded-2xl flex items-center space-x-2">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search guilds by name or [TAG]..."
              className="bg-transparent text-xs text-slate-900 dark:text-white outline-none w-full placeholder:text-slate-400 font-medium"
            />
          </div>

          {/* All Guilds List with Animated Flags */}
          <div className="space-y-2.5 animate-slide-up delay-150">
            <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">
              Active Guilds ({filteredGuilds.length})
            </span>

            {filteredGuilds.map((guild, gIdx) => (
              <div
                key={`${guild.id}-${gIdx}`}
                data-glass="true"
                className="liquid-glass glass-sheen rounded-[22px] p-3.5 flex items-center justify-between hover:scale-[1.01] hover:-translate-y-0.5 transition-all duration-200"
              >
                <div className="flex items-center space-x-3 relative z-10">
                  {/* Telegram Animated Emoji Guild Flag */}
                  <TelegramAnimatedEmoji
                    emoji={guild.flag || (guild.id === 1 ? "dragon" : guild.id === 2 ? "skull" : "strawhat")}
                    size="sm"
                  />

                  <div>
                    <div className="flex items-center space-x-1.5">
                      <span className="font-black text-xs text-slate-900 dark:text-white">{guild.name}</span>
                      <span className="text-[10px] font-mono font-bold text-violet-500">[{guild.tag}]</span>
                    </div>
                    <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-0.5 font-medium">
                      <span>Lv.{guild.level}</span>
                      <span>•</span>
                      <span>{guild.members_count}/{guild.max_members} Members</span>
                      <span>•</span>
                      <span className="text-amber-500 font-mono font-bold">{guild.treasury.toLocaleString()} 🪙</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleJoinGuild(guild.id)}
                  disabled={guild.members_count >= guild.max_members}
                  className="btn-violet px-3.5 py-1.5 rounded-xl text-xs font-bold disabled:opacity-40 relative z-10 active:scale-95 transition"
                >
                  Join
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CREATE GUILD MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="liquid-glass-accent w-full max-w-sm rounded-[32px] p-6 space-y-4 border border-violet-500/50 relative shadow-2xl">
            <button
              onClick={() => setShowCreateModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white text-sm p-1"
            >
              ✕
            </button>

            <div className="text-center">
              <TelegramAnimatedEmoji emoji={newGuildFlag} size="md" className="mx-auto my-1" />
              <h3 className="font-black text-base text-slate-900 dark:text-white mt-2">
                Found a Pokémon Guild
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Fee: 500,000 Coins • Select an official animated flag
              </p>
            </div>

            <form onSubmit={handleCreateGuild} className="space-y-3 relative z-10">
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 block mb-1">
                  Guild Name (3–20 characters)
                </label>
                <input
                  type="text"
                  required
                  maxLength={20}
                  value={newGuildName}
                  onChange={(e) => setNewGuildName(e.target.value)}
                  placeholder="e.g. Apex Predators"
                  className="w-full liquid-glass px-3.5 py-2 rounded-xl text-xs text-slate-900 dark:text-white outline-none placeholder:text-slate-400 font-semibold"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 block mb-1">
                  Guild Tag (2–5 uppercase letters)
                </label>
                <input
                  type="text"
                  required
                  maxLength={5}
                  value={newGuildTag}
                  onChange={(e) => setNewGuildTag(e.target.value.toUpperCase())}
                  placeholder="e.g. APEX"
                  className="w-full liquid-glass px-3.5 py-2 rounded-xl text-xs text-slate-900 dark:text-white outline-none placeholder:text-slate-400 font-mono font-bold uppercase"
                />
              </div>

              {/* Flag Selection */}
              <div>
                <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 block mb-1">
                  Animated Guild Crest
                </label>
                <div className="flex space-x-2 overflow-x-auto pb-1 scrollbar-none">
                  {GUILD_FLAG_PRESETS.slice(0, 6).map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setNewGuildFlag(f.id)}
                      className={`p-1.5 rounded-xl border transition-all ${
                        newGuildFlag === f.id
                          ? "border-amber-400 bg-amber-400/20 scale-105"
                          : "border-white/20 hover:border-white/40"
                      }`}
                    >
                      <TelegramAnimatedEmoji emoji={f.id} size="sm" />
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting || (player?.coins || 0) < 500000}
                className="btn-gold w-full py-3 rounded-2xl text-xs font-black uppercase tracking-wider disabled:opacity-40 shadow-lg mt-2"
              >
                {submitting ? "Founding Guild..." : "Found Guild (500,000 🪙)"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
