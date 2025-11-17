import { useState, useEffect, useRef } from 'react';

const DATA_PROCESS_INTERVAL = 1000;

export function useUpbitTicker() {
    const [btcPrice, setBtcPrice] = useState("Loading...");
    const [ethPrice, setEthPrice] = useState("Loading...");
    const [dogePrice, setDogePrice] = useState("Loading...");
    const [solPrice, setSolPrice] = useState("Loading...");
    const [xrpPrice, setXrpPrice] = useState("Loading...");

    // 연결 안전하게 ref 사용하여 연결
    const wsRef = useRef(null);

    useEffect(() => {
        // 리트라이 추가
        let retryCount = 0;
        const maxRetries = 10;
        let lastProcessedTime = 0;

        const connect = () => {
            if(wsRef.current)
            {
                wsRef.current.close();
            }
            wsRef.current = new WebSocket("wss://api.upbit.com/websocket/v1");
            const ws= wsRef.current;

            ws.onopen = () => {
                console.log("Connected to Upbit WebSocket");
                retryCount = 0;
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
                    const text = await new Response(event.data).text();
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
                    console.error("Error processing message:", e);
                }
            };

            ws.onerror = (error) => {
                console.error("WebSocket Error:", error);
                if (retryCount < maxRetries) {
                    retryCount++;
                    console.log(`Reconnecting... (${retryCount}/${maxRetries})`);
                    setTimeout(connect, 1000);
                } else {
                    console.log("Max retries reached. Stopped reconnecting.");
                }
            };

            ws.onclose = () => {
                if (wsRef.current != ws) return;

                console.log("🔌 WebSocket Disconnected. Attempting to reconnect...");

                if (retryCount < maxRetries) {
                    retryCount++;
                    console.log(`Reconnecting... (${retryCount}/${maxRetries})`);
                    setTimeout(connect, 1000);
                } else {
                    console.log("Max retries reached. Stopped reconnecting.");
                }
            };
        };
        
        connect();

        return () => {
            console.log("Closing WebSocket connection.");
            if(wsRef.current)
            {
                wsRef.current.close();
            }
        };
    }, []);

    return { btcPrice, ethPrice, dogePrice, solPrice, xrpPrice };
}
