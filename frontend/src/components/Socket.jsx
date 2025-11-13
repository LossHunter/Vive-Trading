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
      
      setDatalist(mapped);
    } catch (err) {
      console.error("⚠️ WebSocket Parse Error:", err);
    }
  }
}, [lastMessage]);

  return datalist;
}
