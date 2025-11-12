import { time } from "framer-motion";
import React, { useEffect, useState } from "react";
import { data } from "react-router-dom";
import useWebSocket from "react-use-websocket";

const protocol = window.location.protocol === "https:" ? "wss" : "ws";
const host = window.location.host; 
const WS_URL = `${protocol}://${host}/ws/chartdata`;

export function useSocketData() {
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
