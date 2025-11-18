import { useEffect, useState, useMemo } from "react";
import useWebSocket from "react-use-websocket";



export function useSocketData({lastTime}) {
  const WS_URL = useMemo(() => {
    if (!lastTime) return null;
    return `${import.meta.env.VITE_SOCKET_URL}/ws/chartdata?lastTime=${encodeURIComponent(lastTime)}`;
  }, [lastTime]);

  const [datalist, setDatalist] = useState([]);
  const { lastMessage } = useWebSocket(WS_URL, {
    shouldReconnect: () => true,
  });

  useEffect(() => {
    if (lastMessage?.data) {
      try {
        const parsed = JSON.parse(lastMessage.data);

        let payload;
        if (Array.isArray(parsed)) {
          payload = parsed;
        } else if (parsed?.type === "wallet" && Array.isArray(parsed.data)) {
          payload = parsed.data;
        } else {
          // 다른 타입의 메시지(예: ping/pong, 연결 알림)는 무시
          return;
        }

        const flatParsed = Array.isArray(payload[0]) ? payload.flat() : payload;
        const mapped = flatParsed.map((item = {}) => ({
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
      
      setDatalist(mapped);
    } catch (err) {
      console.error("⚠️ WebSocket Parse Error:", err);
    }
  }
}, [lastMessage]);

  return datalist;
}
