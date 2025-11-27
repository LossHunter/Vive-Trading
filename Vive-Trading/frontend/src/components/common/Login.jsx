import { useGoogleLogin } from '@react-oauth/google';
import '../../styles/Main-Login.css';
import Google_Login from '../../assets/Google-Sign.svg'
import { LoginTokenSend } from '../../services/Http_Post.jsx'
import Loading from './Loading.jsx'
import { useState } from 'react';

export default function LoginModel({ onClose }) {
    const [loading, setLoading] = useState(false)

    const googleLogin = useGoogleLogin({
        flow: 'auth-code',

        onSuccess: async (codeResponse) => {
            setLoading(true);

            const ok = await LoginTokenSend(codeResponse.code); 
            if(!ok)
            {
                alert("로그인 실패. 관리자에게 문의하세요.");
                setLoading(false);
                return;
            }
            
            setLoading(false);
            
            localStorage.setItem("isLogin", true);
            window.location.reload(); 
        },
        onError: (error) => {
            console.log('Google 리디렉션 로그인 실패:', error);
            setLoading(false);
            window.location.reload(); 
        }
    });
    
    return (
        <div className="login-modal-overlay">
            {loading ? (
            <Loading />
                ) : (
            
                <div className="login-modal">
                    <button
                    className="google-login"
                        onClick={() => googleLogin()}       
                    >
                        <img src={Google_Login} />

                    </button>
                    <button className="close-btn" onClick={onClose}>닫기</button>
                </div>
            
            )}
        </div>
    );
}
