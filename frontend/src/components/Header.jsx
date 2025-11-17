import "../styles/Header.css"

import { useUpbitTicker } from '../services/UpbitSocket.jsx';
import { useNavigate, useLocation  } from "react-router-dom";

import BitcoinLogo from '../assets/Bitcoin_logo.png';
import EthuLogo from '../assets/Ethereum_logo.png';
import DogeLogo from '../assets/Doge_log.png';
import SolanaLogo from '../assets/Solana_logo.png';
import XRPLogo from '../assets/XRP_logo.png';
import { useEffect, useState } from "react";

import LoginModel from './Login.jsx';

import { LogOut } from "../services/Http_Post.jsx"

export default function Header() {
    const [isOpen, setIsOpen] =useState(false)
    const [loginText, setloginText] = useState("Login")
    const navigate = useNavigate();

    const goDash = () => {
        const savedCode = localStorage.getItem("isLogin");
        if (!savedCode) {
            setIsOpen(true);
        } else {
            navigate("/dashboard")
        }
    };

    const Login = async () => {
        if (loginText === "Login") {
            setIsOpen(true);
        } else {
            localStorage.removeItem("isLogin");

            const check = await LogOut();

            if(check)
            {
                setloginText("Login");
                navigate("/");
                window.location.reload();
            }
            else
            {
                alert("로그아웃 실패, 관리자에게 문의 하세요.")
            }
        }
    };

    // 로그인 상황 파악
    const location = useLocation();
    useEffect(() => {
        const savedCode = localStorage.getItem("isLogin");
        if (savedCode) {
            const searchParams = new URLSearchParams(location.search);
            setloginText("LogOut")
        }
    }, [location, navigate]);
    
    const { btcPrice, ethPrice, dogePrice, solPrice, xrpPrice } = useUpbitTicker();
    
    return (
            <header>
                <div className="link">
                    <button onClick={() => window.open("https://www.tistory.com/")}>Blog</button>
                    <button
                        className="login-btn"
                        onClick={Login}>
                        {loginText}</button>
                    <button 
                    className="home-btn"
                    onClick={() => navigate('/')}>
                        Home
                    </button>
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
                
                {isOpen && <LoginModel onClose={() => setIsOpen(false)} />}
            </header>
    )
}