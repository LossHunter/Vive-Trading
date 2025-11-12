import React, { useState, useEffect } from "react";
import Header from "../components/Header"
import "../styles/dashboard.css"
import WanData from "../components/WanDB_Api"
import Loading from "../components/Loading"

export default function WandbRuns() {
    const [loading, setLoading] = useState(true);

    const data = WanData();
    useEffect(() => {
        if (data && data.length > 0) {
            console.log("W&B Data:", data);
            setLoading(false);
        }
    }, [data]);

    return (
        <div className="frame">
            <Header/>
            <main>
                <div className="main-left">

                </div>
                <div className="main-center">
                    <div className="grid-chart">

                        <div className="chart-component">
                            
                        </div>
                        <div className="chart-component">
                            
                        </div>
                        <div className="chart-component">
                            
                        </div>
                    </div>
                </div>
                <div className="main-right">
                    
                </div>
            </main>
            <footer>
                <div className="footer-content">
                    <p>
                        **생성형 AI 1회차 프로젝트** |
                        AI 기반 투자 분석 및 실시간 트래커 시스템
                    </p>
                    <p>
                        데이터 소스: Upbit WebSocket API |
                        차트 라이브러리: ApexCharts
                    </p>
                    <p>
                        © 2025 Team [T-Bone]. All Rights Reserved.
                    </p>
                </div>
            </footer>
        </div>
    );
}
