import { useEffect, useState } from "react";

export async function fetchAllData() {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/api/data_stream`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let accumulated = "";
    const allData = [];

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        accumulated += decoder.decode(value, { stream: true });
        const lines = accumulated.split("\n");
        accumulated = lines.pop(); // 마지막 줄은 아직 불완전할 수 있음

        lines.forEach((line) => {
          if (line) {
            try {
              const parsed = JSON.parse(line);
              allData.push(parsed);
            } catch (err) {
              console.error("JSON parse error:", err);
            }
          }
        });
      }
    }

    return allData; // 모든 데이터가 수집된 후 반환
  } catch (err) {
    console.error("Fetch error:", err);
    return [];
  }
}
