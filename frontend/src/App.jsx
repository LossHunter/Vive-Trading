import { Route, Routes, BrowserRouter } from 'react-router-dom';
import './App.css'
import Home from './pages/home.jsx'
import Dashboard from './pages/dashboard.jsx'
import { useState, useEffect } from "react";
import { Settings } from "lucide-react";
import getDB from "./components/OpenDB.jsx"

function Home_Page() {
    return <Home />;
}

function Dash_Board() {
    return <Dashboard />;
}

function App() {
    const [darkMode, setDarkMode] = useState(false);

    useEffect(() => {
        (async () => {
            await getDB();
        })();
    }, []);

    useEffect(() => {
    if (darkMode) {
        document.body.classList.add("dark-mode");
        } else {
        document.body.classList.remove("dark-mode");
        }
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
                    <Route path="/" element={<Home_Page />} />
                    <Route path="/dashboard" element={<Dash_Board />} />
                </Routes>
            </BrowserRouter>
        </>
    )
}
export default App
