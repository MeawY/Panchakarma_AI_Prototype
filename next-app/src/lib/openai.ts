import OpenAI from "openai";

function getOpenAI(): OpenAI {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not set");
  const baseURL = process.env.OPENAI_BASE_URL?.trim() || undefined;
  return new OpenAI({ apiKey, baseURL });
}

const EMB_MODEL = "text-embedding-3-small";
const CHAT_MODEL = "gpt-4o-mini";

export async function embedQuery(query: string): Promise<number[]> {
  const openai = getOpenAI();
  const res = await openai.embeddings.create({
    model: EMB_MODEL,
    input: [query],
  });
  const vec = res.data[0]?.embedding;
  if (!vec) throw new Error("No embedding returned");
  return vec;
}

export async function chat(
  system: string,
  user: string,
  temperature = 0.2
): Promise<string> {
  const openai = getOpenAI();
  const msg = await openai.chat.completions.create({
    model: CHAT_MODEL,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    temperature,
  });
  return msg.choices[0]?.message?.content ?? "";
}

export { getOpenAI, EMB_MODEL, CHAT_MODEL };
