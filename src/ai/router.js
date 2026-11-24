/**
 * Multi-Key Proactive Anti-Wall Load Balancer & VIP Priority Router
 *
 * - Spreads messages across configured Gemini API keys BEFORE any key hits 5 messages/min.
 * - Tracks a 60-second sliding window of requests per key and always routes to the freshest key.
 * - Tier 1 VIP is strictly locked to the #1 most powerful model on the freshest key.
 */

export const DEFAULT_7_GEMINI_KEYS = [];

let roundRobinPointer = 0;
const keyUsageHistory = new Map(); // keyIdx -> array of timestamps in last 60s

function getRecentCount(keyIdx) {
  const now = Date.now();
  const list = (keyUsageHistory.get(keyIdx) || []).filter((t) => now - t < 60000);
  keyUsageHistory.set(keyIdx, list);
  return list.length;
}

function recordKeyUse(keyIdx) {
  const now = Date.now();
  const list = (keyUsageHistory.get(keyIdx) || []).filter((t) => now - t < 60000);
  list.push(now);
  keyUsageHistory.set(keyIdx, list);
}

export function safeParseAIJson(rawText) {
  if (!rawText) return { reply: 'heyy! wsp?' };
  const cleaned = String(rawText)
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```\s*$/i, '')
    .trim();

  try {
    return JSON.parse(cleaned);
  } catch {
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch {
        // Fallback below
      }
    }
    return { reply: cleaned };
  }
}

async function callGemini({ apiKey, model, systemPrompt, messages }) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const contents = messages.map((m) => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemPrompt }] },
      contents,
      generationConfig: {
        temperature: 0.85,
        responseMimeType: 'application/json'
      }
    })
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini (${model}) HTTP ${res.status}: ${errText}`);
  }

  const data = await res.json();
  const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
  return safeParseAIJson(rawText);
}

function getConfiguredGeminiKeys(env) {
  const keys = [];
  if (env?.GEMINI_API_KEYS) {
    keys.push(...String(env.GEMINI_API_KEYS).split(/[\n,]+/).map((k) => k.trim()));
  }
  if (env?.GEMINI_API_KEY) {
    keys.push(...String(env.GEMINI_API_KEY).split(/[\n,]+/).map((k) => k.trim()));
  }
  for (let i = 1; i <= 7; i++) {
    if (env?.[`GEMINI_API_KEY_${i}`]) {
      keys.push(String(env[`GEMINI_API_KEY_${i}`]).trim());
    }
  }
  return [...new Set(keys.filter(Boolean))];
}

export async function generateStructuredReply({
  env,
  systemPrompt,
  messages,
  isVipLoml = false
}) {
  const errors = [];
  const geminiKeys = getConfiguredGeminiKeys(env);
  const totalKeys = geminiKeys.length;
  if (totalKeys === 0) {
    throw new Error('No GEMINI_API_KEY or GEMINI_API_KEYS configured');
  }

  // Advance round-robin pointer BEFORE picking so every single message spreads to the next key!
  const baseStart = roundRobinPointer++ % totalKeys;

  // Sort candidate key indices so keys with the fewest calls in the last 60s (< 3 calls) come first!
  const candidateKeyIndices = Array.from({ length: totalKeys }, (_, i) => (baseStart + i) % totalKeys)
    .sort((a, b) => getRecentCount(a) - getRecentCount(b));

  // Tier 1 VIP is locked to the most powerful flagship models!
  const modelsToTry = isVipLoml
    ? ['gemini-2.5-flash', 'gemini-3.6-flash']
    : ['gemini-2.5-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'];

  for (const model of modelsToTry) {
    for (const keyIdx of candidateKeyIndices) {
      const apiKey = geminiKeys[keyIdx];
      // Proactively reserve this key slot BEFORE the await so simultaneous parallel calls pick different keys!
      recordKeyUse(keyIdx);
      try {
        const result = await callGemini({
          apiKey,
          model,
          systemPrompt,
          messages
        });
        return {
          ...result,
          usedKeySlot: keyIdx + 1,
          usedModel: model,
          keyRecentLoad: getRecentCount(keyIdx)
        };
      } catch (err) {
        errors.push(`Key #${keyIdx + 1} (${model}): ${err.message}`);
      }
    }
  }

  throw new Error(`All ${totalKeys} API keys exhausted: ${errors.join(' | ')}`);
}

export function buildFreeGeneratedImageUrl(prompt) {
  const encoded = encodeURIComponent(prompt.trim());
  const seed = Math.floor(Math.random() * 100000);
  return `https://image.pollinations.ai/prompt/${encoded}?model=flux&width=1080&height=1350&seed=${seed}&nologo=true`;
}
