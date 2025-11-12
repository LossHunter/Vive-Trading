import { useGoogleLogin } from '@react-oauth/google';
import '../styles/login.css';
import { useState, React } from "react";
import Google_Login from '../assets/Google_Login.png'

export default function LoginModel({ onClose }) {
    
    const googleLogin = useGoogleLogin({
        flow: 'auth-code',

        onSuccess: (codeResponse) => {
            localStorage.setItem('googleAuthCode', codeResponse.code);
            setIslogin(true);
            window.location.reload()
        },
        onError: (error) => {
            console.log('❌ Google 리디렉션 로그인 실패:', error);
        }
    });
    

    return (
        <div className="login-modal-overlay">
            <div className="login-modal">
                <button
                className="google-login"
                    onClick={() => googleLogin()}       
                >
                    <img src={Google_Login} />

                </button>
                <button className="close-btn" onClick={onClose}>닫기</button>
            </div>
        </div>
    );
}
