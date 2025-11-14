import { useState, useEffect } from 'react';

const DATA_PROCESS_INTERVAL = 1000;

/**
 * Upbit 웹소켓에서 주요 코인 실시간 가격을 구독하는 커스텀 훅
 * @returns {object} { btcPrice, ethPrice, dogePrice, solPrice, xrpPrice }
 */
export function useUpbitTicker() {
    const [btcPrice, setBtcPrice] = useState("Loading...");
    const [ethPrice, setEthPrice] = useState("Loading...");
    const [dogePrice, setDogePrice] = useState("Loading...");
    const [solPrice, setSolPrice] = useState("Loading...");
    const [xrpPrice, setXrpPrice] = useState("Loading...");

    useEffect(() => {
        const ws = new WebSocket("wss://api.upbit.com/websocket/v1");
        let lastProcessedTime = 0;

        ws.onopen = () => {
            console.log("✅ Connected to Upbit WebSocket");
            ws.send(JSON.stringify([
                { ticket: "ticker-test" },
                {
                    type: "ticker",
                    codes: ["KRW-BTC", "KRW-ETH", "KRW-DOGE", "KRW-SOL", "KRW-XRP"]
                }
            ]));
        };

        ws.onmessage = async (event) => {
            try {
                const text = await event.data.text();
                const data = JSON.parse(text);

                if (data.type === "ticker") {
                    const now = Date.now();
                    if (now - lastProcessedTime < DATA_PROCESS_INTERVAL) return;
                    lastProcessedTime = now;

                    switch (data.code) {
                        case "KRW-BTC":
                            setBtcPrice(data.trade_price.toLocaleString());
                            break;
                        case "KRW-ETH":
                            setEthPrice(data.trade_price.toLocaleString());
                            break;
                        case "KRW-DOGE":
                            setDogePrice(data.trade_price.toLocaleString());
                            break;
                        case "KRW-SOL":
                            setSolPrice(data.trade_price.toLocaleString());
                            break;
                        case "KRW-XRP":
                            setXrpPrice(data.trade_price.toLocaleString());
                            break;
                        default:
                            break;
                    }
                }
            } catch (e) {
                console.error("❌ Error processing message:", e);
            }
        };

        ws.onerror = (error) => {
            console.error("⚠️ WebSocket Error:", error);
        };

        ws.onclose = () => {
            console.log("🔌 WebSocket Disconnected. Attempting to reconnect...");
        };

        return () => {
            console.log("🛑 Closing WebSocket connection.");
            ws.close();
        };
    }, []);

    return { btcPrice, ethPrice, dogePrice, solPrice, xrpPrice };
}
