import "../styles/Header.css"

import { useUpbitTicker } from '../components/UpbitSocket';
import { useNavigate, useLocation  } from "react-router-dom";

import BitcoinLogo from '../assets/Bitcoin_logo.png';
import EthuLogo from '../assets/Ethereum_logo.png';
import DogeLogo from '../assets/Doge_log.png';
import SolanaLogo from '../assets/Solana_logo.png';
import XRPLogo from '../assets/XRP_logo.png';

export default function Header() {
    const navigate = useNavigate();
    const goDash = () => {
        const savedCode = localStorage.getItem("googleAuthCode");
        if (!savedCode) {
            setIsOpen(true); // 로그인 모달 띄움
        } else {
            const searchParams = new URLSearchParams(location.search);
            searchParams.set("code", savedCode); 
            navigate({
                pathname: `/dashboard/${location.pathname}`,
                search: searchParams.toString(), 
            }, { replace: true });
        }
    };

    const { btcPrice, ethPrice, dogePrice, solPrice, xrpPrice } = useUpbitTicker();
    
    return (
            <header>
                <div className="link">
                    <button onClick={() => window.open("https://www.tistory.com/")}>Blog</button>
                    <button
                        className="login-btn"
                        onClick={() =>
                            setIsOpen(true) }>
                        Login</button>
                    <button onClick={goDash}>Dash+</button>
                </div>
                <div className="alert">
                    <div className="TICKER">
                        <a href="https://kr.investing.com/crypto/bitcoin"
                            target="_blank"
                            rel="noopener noreferrer">
                            <img
                                src={BitcoinLogo}
                            />
                            BTC
                        </a>
                        <label>{btcPrice} KRW</label>
                    </div>
                    <div className="TICKER">
                        <a href="https://kr.investing.com/indices/investing.com-eth-usd"
                            target="_blank"
                            rel="noopener noreferrer">
                            <img
                                src={EthuLogo}
                            />
                            ETH
                        </a>
                        <label>{ethPrice} KRW</label>
                    </div>
                    <div className="TICKER">
                        <a href="https://kr.investing.com/indices/investing.com-doge-usd"
                            target="_blank"
                            rel="noopener noreferrer">
                            <img
                                src={DogeLogo}
                            />
                            DOGE
                        </a>
                        <label>{dogePrice} KRW</label>
                    </div>
                    <div className="TICKER">
                        <a href="https://kr.investing.com/indices/investing.com-sol-usd"
                            target="_blank"
                            rel="noopener noreferrer">
                            <img
                                src={SolanaLogo}
                            />
                            SOL
                        </a>
                        <label>{solPrice} KRW</label>
                    </div>
                    <div className="TICKER">
                        <a href="https://kr.investing.com/indices/investing.com-xrp-usd"
                            target="_blank"
                            rel="noopener noreferrer">
                            <img
                                src={XRPLogo}
                            />
                            XRP
                        </a>
                        <label>{xrpPrice} KRW</label>
                    </div>
                </div>
            </header>
    )
}