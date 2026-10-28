import { useState, useRef } from "react";

const PALETTE = {
  bg: "#FFF8EC",
  ink: "#2B2118",
  sun: "#F5A623",
  sunDark: "#8A5A0B",
  sky: "#4FA9D8",
  skyDark: "#1B5A78",
  leaf: "#6FAE4C",
  leafDark: "#2F5A1B",
  berry: "#D65A6C",
  berryDark: "#7A2530",
  card: "#FFFFFF",
};

const SHAPES = ["circle", "star", "leaf"];

function Shape({ type, color, size = 34 }) {
  if (type === "star") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24">
        <path
          d="M12 2l2.9 6.3 6.9.7-5.2 4.6 1.6 6.8L12 16.9 5.8 20.4l1.6-6.8L2.2 9l6.9-.7z"
          fill={color}
        />
      </svg>
    );
  }
  if (type === "leaf") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24">
        <path
          d="M20 4C10 4 4 10 4 20c10 0 16-6 16-16z"
          fill={color}
        />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill={color} />
    </svg>
  );
}

// ---- level definitions -------------------------------------------------
const LEVELS = [
  { id: 1, label: "1-5 à¤®à¥‹à¤œà¤¾", labelEn: "Count 1-5", max: 5, mode: "count" },
  { id: 2, label: "3-8 à¤®à¥‹à¤œà¤¾", labelEn: "Count 3-8", max: 8, mode: "count" },
  { id: 3, label: "à¤®à¥‹à¤ à¥‡ à¤•à¥‹à¤£?", labelEn: "Which is more?", max: 10, mode: "compare" },
  { id: 4, label: "5-12 à¤®à¥‹à¤œà¤¾", labelEn: "Count 5-12", max: 12, mode: "count" },
  { id: 5, label: "à¤¬à¥‡à¤°à¥€à¤œ", labelEn: "Simple addition", max: 6, mode: "add" },
];

function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function makeQuestion(level) {
  const color = [PALETTE.sky, PALETTE.leaf, PALETTE.berry][rand(0, 2)];
  const shape = SHAPES[rand(0, 2)];

  if (level.mode === "count") {
    const n = rand(Math.max(1, level.max - 4), level.max);
    const options = new Set([n]);
    while (options.size < 3) {
      options.add(rand(Math.max(1, n - 3), n + 3));
    }
    return {
      mode: "count",
      n,
      shape,
      color,
      options: shuffle([...options]),
      answer: n,
    };
  }

  if (level.mode === "compare") {
    let a = rand(1, level.max);
    let b = rand(1, level.max);
    while (a === b) b = rand(1, level.max);
    return {
      mode: "compare",
      a,
      b,
      shapeA: shape,
      shapeB: SHAPES[rand(0, 2)],
      colorA: PALETTE.sky,
      colorB: PALETTE.berry,
      answer: a > b ? "a" : "b",
    };
  }

  // addition
  const a = rand(1, level.max - 1);
  const b = rand(1, level.max - a);
  const sum = a + b;
  const options = new Set([sum]);
  while (options.size < 3) {
    options.add(rand(Math.max(1, sum - 3), sum + 3));
  }
  return {
    mode: "add",
    a,
    b,
    shape,
    color,
    options: shuffle([...options]),
    answer: sum,
  };
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = rand(0, i);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---- audio (speech synthesis stand-in for recorded Marathi clips) ------
function speak(text) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "mr-IN";
    u.rate = 0.85;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch (e) {
    // speech synthesis unavailable â€” silent fallback
  }
}

export default function App() {
  const [screen, setScreen] = useState("home"); // home | game | parent
  const [levelIdx, setLevelIdx] = useState(0);
  const [question, setQuestion] = useState(() => makeQuestion(LEVELS[0]));
  const [feedback, setFeedback] = useState(null); // 'correct' | 'wrong' | null
  const [streakRight, setStreakRight] = useState(0);
  const [streakWrong, setStreakWrong] = useState(0);
  const [log, setLog] = useState([]); // {levelId, correct}
  const lockRef = useRef(false);

  const level = LEVELS[levelIdx];

  function newQuestion(li = levelIdx) {
    setQuestion(makeQuestion(LEVELS[li]));
    setFeedback(null);
    lockRef.current = false;
  }

  function adaptDifficulty(correct) {
    let nextIdx = levelIdx;
    if (correct) {
      const s = streakRight + 1;
      setStreakRight(s);
      setStreakWrong(0);
      if (s >= 3 && levelIdx < LEVELS.length - 1) {
        nextIdx = levelIdx + 1;
        setStreakRight(0);
      }
    } else {
      const s = streakWrong + 1;
      setStreakWrong(s);
      setStreakRight(0);
      if (s >= 3 && levelIdx > 0) {
        nextIdx = levelIdx - 1;
        setStreakWrong(0);
      }
    }
    if (nextIdx !== levelIdx) setLevelIdx(nextIdx);
    return nextIdx;
  }

  function answer(isCorrect, spokenWord) {
    if (lockRef.current) return;
    lockRef.current = true;
    setFeedback(isCorrect ? "correct" : "wrong");
    speak(isCorrect ? "à¤¬à¤°à¥‹à¤¬à¤°!" : spokenWord || "à¤ªà¥à¤¨à¥à¤¹à¤¾ à¤ªà¥à¤°à¤¯à¤¤à¥à¤¨ à¤•à¤°à¤¾");
    setLog((l) => [...l, { levelId: level.id, correct: isCorrect }].slice(-100));
    const nextIdx = adaptDifficulty(isCorrect);
    setTimeout(() => newQuestion(nextIdx), 900);
  }

  // ---- derived stats for parent view ----
  const totalAttempts = log.length;
  const totalCorrect = log.filter((l) => l.correct).length;
  const accuracy = totalAttempts ? Math.round((totalCorrect / totalAttempts) * 100) : 0;
  const perLevel = LEVELS.map((lv) => {
    const attempts = log.filter((l) => l.levelId === lv.id);
    const correct = attempts.filter((a) => a.correct).length;
    return { ...lv, attempts: attempts.length, correct };
  });

  return (
    <div
      style={{
        minHeight: "100vh",
        background: PALETTE.bg,
        color: PALETTE.ink,
        fontFamily:
          "'Noto Sans Devanagari', 'Baloo 2', 'Segoe UI', sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "24px 16px 48px",
      }}
    >
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700&family=Noto+Sans+Devanagari:wght@500;700&display=swap"
      />

      <TopBar screen={screen} setScreen={setScreen} />

      {screen === "home" && <Home setScreen={setScreen} />}

      {screen === "game" && (
        <GameScreen
          level={level}
          question={question}
          feedback={feedback}
          onAnswer={answer}
          streakRight={streakRight}
        />
      )}

      {screen === "parent" && (
        <ParentView
          accuracy={accuracy}
          totalAttempts={totalAttempts}
          perLevel={perLevel}
          currentLevel={level}
        />
      )}
    </div>
  );
}

function TopBar({ screen, setScreen }) {
  return (
    <div
      style={{
        width: "100%",
        maxWidth: 420,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 20,
      }}
    >
      <div
        onClick={() => setScreen("home")}
        style={{ cursor: "pointer", display: "flex", flexDirection: "column" }}
      >
        <span style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Noto Sans Devanagari', sans-serif" }}>
          à¤…à¤‚à¤•à¤—à¤£à¤¿à¤¤
        </span>
        <span style={{ fontSize: 11, color: PALETTE.sunDark, letterSpacing: 0.3 }}>
          ANKGANIT Â· early numeracy
        </span>
      </div>
      <button
        onClick={() => setScreen(screen === "parent" ? "home" : "parent")}
        style={{
          border: `2px solid ${PALETTE.skyDark}`,
          background: screen === "parent" ? PALETTE.sky : "transparent",
          color: screen === "parent" ? "#fff" : PALETTE.skyDark,
          borderRadius: 999,
          padding: "6px 14px",
          fontSize: 13,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        {screen === "parent" ? "à¤–à¥‡à¤³à¤¾à¤•à¤¡à¥‡ à¤ªà¤°à¤¤" : "à¤ªà¤¾à¤²à¤• à¤¦à¥ƒà¤¶à¥à¤¯"}
      </button>
    </div>
  );
}

function Home({ setScreen }) {
  return (
    <div style={{ width: "100%", maxWidth: 420, textAlign: "center" }}>
      <div
        style={{
          background: PALETTE.card,
          borderRadius: 20,
          padding: "28px 20px",
          boxShadow: "0 6px 0 " + PALETTE.sunDark + "22",
          border: `2px solid ${PALETTE.sun}55`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "center", gap: 10, marginBottom: 12 }}>
          <Shape type="circle" color={PALETTE.sky} size={40} />
          <Shape type="star" color={PALETTE.sun} size={40} />
          <Shape type="leaf" color={PALETTE.leaf} size={40} />
        </div>
        <h1 style={{ fontSize: 20, margin: "0 0 8px", fontFamily: "'Noto Sans Devanagari', sans-serif" }}>
          à¤®à¤°à¤¾à¤ à¥€à¤¤ à¤®à¥‹à¤œà¤¾à¤¯à¤²à¤¾ à¤¶à¤¿à¤•à¥‚à¤¯à¤¾
        </h1>
        <p style={{ fontSize: 13, color: "#6b5f52", margin: "0 0 20px", lineHeight: 1.5 }}>
          Learn number sense in Marathi â€” counting, comparing, and simple addition,
          with the difficulty adjusting to how the child is doing.
        </p>
        <button
          onClick={() => setScreen("game")}
          style={{
            background: PALETTE.sun,
            border: "none",
            color: "#fff",
            fontWeight: 700,
            fontSize: 16,
            padding: "12px 32px",
            borderRadius: 999,
            cursor: "pointer",
            boxShadow: `0 4px 0 ${PALETTE.sunDark}`,
          }}
        >
          à¤–à¥‡à¤³ à¤¸à¥à¤°à¥‚ à¤•à¤°à¤¾
        </button>
      </div>
      <p style={{ fontSize: 11, color: "#9c8f7f", marginTop: 16 }}>
        Prototype demo â€” runs fully offline once packaged; voice here uses the
        browser's speech engine as a stand-in for recorded Marathi audio.
      </p>
    </div>
  );
}

function GameScreen({ level, question, feedback, onAnswer, streakRight }) {
  return (
    <div style={{ width: "100%", maxWidth: 420 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
          fontSize: 13,
          color: PALETTE.skyDark,
          fontWeight: 700,
        }}
      >
        <span>{level.label}</span>
        <span style={{ display: "flex", gap: 4 }}>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: i < streakRight ? PALETTE.leaf : "#e4dcc9",
              }}
            />
          ))}
        </span>
      </div>

      <div
        style={{
          background: PALETTE.card,
          borderRadius: 20,
          padding: "24px 18px",
          border: `2px solid ${
            feedback === "correct"
              ? PALETTE.leaf
              : feedback === "wrong"
              ? PALETTE.berry
              : "#eee3cf"
          }`,
          transition: "border-color 0.2s",
          minHeight: 260,
        }}
      >
        {question.mode === "count" && (
          <CountQuestion question={question} onAnswer={onAnswer} />
        )}
        {question.mode === "add" && (
          <AddQuestion question={question} onAnswer={onAnswer} />
        )}
        {question.mode === "compare" && (
          <CompareQuestion question={question} onAnswer={onAnswer} />
        )}
      </div>

      {feedback && (
        <p
          style={{
            textAlign: "center",
            marginTop: 12,
            fontWeight: 700,
            color: feedback === "correct" ? PALETTE.leafDark : PALETTE.berryDark,
          }}
        >
          {feedback === "correct" ? "à¤¬à¤°à¥‹à¤¬à¤°! Correct" : "à¤ªà¥à¤¨à¥à¤¹à¤¾ à¤ªà¥à¤°à¤¯à¤¤à¥à¤¨ à¤•à¤°à¤¾"}
        </p>
      )}
    </div>
  );
}

function ObjectRow({ n, shape, color }) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        justifyContent: "center",
        margin: "12px 0 18px",
        minHeight: 40,
      }}
    >
      {Array.from({ length: n }).map((_, i) => (
        <Shape key={i} type={shape} color={color} />
      ))}
    </div>
  );
}

function OptionButtons({ options, onPick, correctValue }) {
  return (
    <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onPick(opt === correctValue, String(opt))}
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            border: `2px solid ${PALETTE.skyDark}`,
            background: PALETTE.bg,
            fontSize: 20,
            fontWeight: 700,
            color: PALETTE.ink,
            cursor: "pointer",
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function CountQuestion({ question, onAnswer }) {
  return (
    <div style={{ textAlign: "center" }}>
      <p style={{ fontSize: 14, color: "#6b5f52", margin: "0 0 4px" }}>
        à¤•à¤¿à¤¤à¥€ à¤†à¤¹à¥‡à¤¤? Â· How many are there?
      </p>
      <ObjectRow n={question.n} shape={question.shape} color={question.color} />
      <OptionButtons
        options={question.options}
        correctValue={question.answer}
        onPick={onAnswer}
      />
    </div>
  );
}

function AddQuestion({ question, onAnswer }) {
  return (
    <div style={{ textAlign: "center" }}>
      <p style={{ fontSize: 14, color: "#6b5f52", margin: "0 0 4px" }}>
        à¤à¤•à¥‚à¤£ à¤•à¤¿à¤¤à¥€? Â· What's the total?
      </p>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, margin: "10px 0 18px" }}>
        <ObjectRow n={question.a} shape={question.shape} color={question.color} />
        <span style={{ fontSize: 24, fontWeight: 700, color: PALETTE.sunDark }}>+</span>
        <ObjectRow n={question.b} shape={question.shape} color={question.color} />
      </div>
      <OptionButtons
        options={question.options}
        correctValue={question.answer}
        onPick={onAnswer}
      />
    </div>
  );
}

function CompareQuestion({ question, onAnswer }) {
  return (
    <div style={{ textAlign: "center" }}>
      <p style={{ fontSize: 14, color: "#6b5f52", margin: "0 0 12px" }}>
        à¤•à¥‹à¤£à¤¤à¥à¤¯à¤¾ à¤¬à¤¾à¤œà¥‚à¤²à¤¾ à¤œà¤¾à¤¸à¥à¤¤ à¤†à¤¹à¥‡à¤¤? Â· Which side has more?
      </p>
      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={() => onAnswer(question.answer === "a", "à¤ªà¥à¤¨à¥à¤¹à¤¾")}
          style={{
            flex: 1,
            border: `2px solid ${PALETTE.skyDark}`,
            borderRadius: 14,
            background: "#fff",
            padding: "12px 6px",
            cursor: "pointer",
            minHeight: 96,
          }}
        >
          <ObjectRow n={question.a} shape={question.shapeA} color={question.colorA} />
        </button>
        <button
          onClick={() => onAnswer(question.answer === "b", "à¤ªà¥à¤¨à¥à¤¹à¤¾")}
          style={{
            flex: 1,
            border: `2px solid ${PALETTE.berryDark}`,
            borderRadius: 14,
            background: "#fff",
            padding: "12px 6px",
            cursor: "pointer",
            minHeight: 96,
          }}
        >
          <ObjectRow n={question.b} shape={question.shapeB} color={question.colorB} />
        </button>
      </div>
    </div>
  );
}

function ParentView({ accuracy, totalAttempts, perLevel, currentLevel }) {
  return (
    <div style={{ width: "100%", maxWidth: 420 }}>
      <h2 style={{ fontSize: 17, margin: "0 0 4px" }}>à¤ªà¥à¤°à¤—à¤¤à¥€ Â· Progress</h2>
      <p style={{ fontSize: 12, color: "#8a7c6a", margin: "0 0 16px" }}>
        Session summary â€” in the full app this syncs quietly when wifi is available.
      </p>

      <div style={{ display: "flex", gap: 12, marginBottom: 18 }}>
        <StatCard label="à¤ªà¥à¤°à¤¶à¥à¤¨ Â· Attempts" value={totalAttempts} />
        <StatCard label="à¤…à¤šà¥‚à¤•à¤¤à¤¾ Â· Accuracy" value={totalAttempts ? accuracy + "%" : "â€”"} />
      </div>

      <div
        style={{
          background: PALETTE.card,
          border: "2px solid #eee3cf",
          borderRadius: 16,
          padding: 16,
        }}
      >
        <p style={{ fontSize: 12, fontWeight: 700, color: "#6b5f52", margin: "0 0 10px" }}>
          à¤•à¥Œà¤¶à¤²à¥à¤¯à¤¾à¤¨à¥à¤¸à¤¾à¤° Â· By skill
        </p>
        {perLevel.map((lv) => (
          <div
            key={lv.id}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 0",
              borderBottom: lv.id !== perLevel.length ? "1px solid #f1e9d8" : "none",
            }}
          >
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{lv.label}</div>
              <div style={{ fontSize: 11, color: "#9c8f7f" }}>{lv.labelEn}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              {lv.id === currentLevel.id && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: PALETTE.sunDark,
                    background: PALETTE.sun + "22",
                    borderRadius: 999,
                    padding: "2px 8px",
                    marginRight: 6,
                  }}
                >
                  à¤¸à¤§à¥à¤¯à¤¾
                </span>
              )}
              <span style={{ fontSize: 13, color: "#6b5f52" }}>
                {lv.attempts ? `${lv.correct}/${lv.attempts}` : "â€”"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div
      style={{
        flex: 1,
        background: PALETTE.card,
        border: "2px solid #eee3cf",
        borderRadius: 14,
        padding: "12px 14px",
      }}
    >
      <div style={{ fontSize: 11, color: "#9c8f7f", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}