import { useMemo, useEffect, useState } from "react";
import useWebSocket from "react-use-websocket";

export function useSocketData({ lastTime, enabled }) {
  const WS_URL = useMemo(() => {
    if (!enabled || !lastTime) return null; // 초기 로딩 전엔 null
    return `${import.meta.env.VITE_SOCKET_URL}/ws/chartdata?lastTime=${encodeURIComponent(lastTime)}`;
  }, [lastTime, enabled]);

  const { lastMessage } = useWebSocket(WS_URL, {
    shouldReconnect: () => true,
  });

  const [socket_data, setSocket_data] = useState([]);
  const [socketlasttime, setSocketlasttime] = useState("");

  useEffect(() => {
    if (!lastMessage?.data) return;

    try {
      const parsed = JSON.parse(lastMessage.data);
      const flatParsed = Array.isArray(parsed[0]) ? parsed.flat() : parsed;

      const mapped = flatParsed.map(item => ({
        userId: item.userId,
        username: item.username,
        colors: item.colors,
        logo: item.logo,
        time: item.time,
        why: item.why,
        position: item.position,
        non: item.non,
        bit: item.btc || item.bit,
        eth: item.eth,
        dog: item.dog,
        sol: item.sol,
        xrp: item.xrp,
        total: item.total
      }));

      setSocketlasttime(mapped.length > 0 ? mapped[mapped.length - 1].time : null);
      setSocket_data(mapped);
    } catch (err) {
      console.error("⚠️ WebSocket Parse Error:", err);
    }
  }, [lastMessage]);

  return { socket_data, socketlasttime };
}
