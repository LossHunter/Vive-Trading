export async function fetchAllData() {
  try {
    const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/data_stream`);
    if (!res.ok || !res.body) {
      throw new Error(`Unexpected response: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let accumulated = "";

    // wallet 데이터만 추려서 time 기준으로 묶기
    const walletEntries = [];
    const groupedByTime = new Map();

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;

      if (!value) {
        continue;
      }

      accumulated += decoder.decode(value, { stream: true });
      const lines = accumulated.split("\n");
      accumulated = lines.pop() ?? "";

      for (const line of lines) {
        if (!line) continue;
        try {
          const parsed = JSON.parse(line);

          let payload;
          if (Array.isArray(parsed)) {
            payload = parsed;
          } else if (parsed?.type === "wallet" && Array.isArray(parsed.data)) {
            payload = parsed.data;
          } else {
            continue;
          }

          if (!payload.length) {
            continue;
          }

          walletEntries.push(...payload);

          const timeKey = payload[0]?.time ?? "__unknown__";
          if (!groupedByTime.has(timeKey)) {
            groupedByTime.set(timeKey, []);
          }

          const normalizedGroup = payload
            .map(item => ({ ...item }))
            .sort((a, b) => (a.userId ?? 0) - (b.userId ?? 0));

          groupedByTime.set(timeKey, normalizedGroup);
        } catch (err) {
          console.error("JSON parse error:", err);
        }
      }
    }

    const groupedWallets = Array.from(groupedByTime.values()).filter(group => group.length > 0);
    const lastTime =
      walletEntries.length > 0 ? walletEntries[walletEntries.length - 1].time ?? null : null;

    return { allData: groupedWallets, lastTime };
  } catch (err) {
    console.error("Fetch error:", err);
    return { allData: [], lastTime: null };
  }
}
