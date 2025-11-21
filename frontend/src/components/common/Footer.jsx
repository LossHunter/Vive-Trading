import "../../styles/Footer.css"

export default function Header() {
    return (
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
    )
}