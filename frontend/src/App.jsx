import { Route, Routes, BrowserRouter } from 'react-router-dom';
import './App.css'
import Home from './pages/home.jsx'
import Dashboard from './pages/dashboard.jsx'
import { useState, useEffect } from "react";
import { Settings } from "lucide-react";

import { getDB } from "./components/common/OpenDB.jsx"


function Home_Page({ setAnalyzeData  }) {
    return <Home setAnalyzeData={setAnalyzeData} />;
}

function Dash_Board({ analyzeData }) {
    return <Dashboard analyzeData={analyzeData} />;
}

function App() {
    const [analyzeData, setAnalyzeData] = useState(null);

    // DB 테이블 생성
    useEffect(() => {
        (async () => {
            await getDB();
        })();
    }, []);

    // 다크모드 저장
    const [darkMode, setDarkMode] = useState(() => {
            const saved = localStorage.getItem("darkMode");
            return saved ? JSON.parse(saved) : false;
        });

    useEffect(() => {
        if (darkMode) {
            document.body.classList.add("dark-mode");
        } else {
            document.body.classList.remove("dark-mode");
        }

        localStorage.setItem("darkMode", JSON.stringify(darkMode));
    }, [darkMode]);

    return (
        <>
            <button 
                className="dark-toggle-btn"
                onClick={() => setDarkMode(prev => !prev)}
            >
                <Settings size={20} />
            </button>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Home_Page setAnalyzeData={setAnalyzeData} />} />
                    <Route path="/dashboard" element={<Dash_Board analyzeData={analyzeData} />} />
                </Routes>
            </BrowserRouter>
        </>
    )
}
export default App
