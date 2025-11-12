import { motion, Reorder, AnimatePresence } from "framer-motion";
import "../styles/Wallet_Rank.css";

import GPT_Logo from "../assets/ChatGPT_LOGO.png";
import Gemini_LOGO from "../assets/Gemini_LOGO.png";
import DeepSeek_LOGO from "../assets/DeepSeek_LOGO.png";
import Grok_LOGO from "../assets/Grok_LOGO.png";

const logoMap = {
    "GPT_Logo.png": GPT_Logo,
    "Gemini_LOGO.png": Gemini_LOGO,
    "DeepSeek_LOGO.png": DeepSeek_LOGO,
    "Grok_LOGO.png": Grok_LOGO,
};

export default function WalletList({ sender_wallet, setbot }) {
    const sortedWallets = [...sender_wallet].sort(
        (a, b) => (b.total.at(-1) ?? 0) - (a.total.at(-1) ?? 0)
    );

    return (
        <Reorder.Group
            className="recoder"
            axis="y" values={sortedWallets} onReorder={() => { }}>
            <AnimatePresence>
                {sortedWallets.map((wallet) => (
                    <Reorder.Item
                        key={wallet.userId}
                        value={wallet}
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        layout
                        className="wallet-item"
                    >
                        <div 
                        style={{
                            background: wallet.colors
                            }}
                        className="wallet" onClick={() => setbot(Number(wallet.userId))}>
                            <div className="wallet-img">
                                <img src={logoMap[wallet.logo]} />
                                <p>{wallet.username}</p>
                            </div>
                            <div className="space"></div>
                            <table className="wallet-table">
                                <tbody>
                                    <tr>
                                        <td>Total Asset</td>
                                        <td>{(wallet.total.at(-1) ?? 0).toFixed(0)}</td>
                                        <td>₩</td>
                                    </tr>
                                    <tr>
                                        <td>Bitcoin</td>
                                        <td>{(wallet.bit.at(-1) ?? 0).toFixed(6)}</td>
                                        <td>EA</td>
                                    </tr>
                                    <tr>
                                        <td>Ethereum</td>
                                        <td>{(wallet.eth.at(-1) ?? 0).toFixed(6)}</td>
                                        <td>EA</td>
                                    </tr>
                                    <tr>
                                        <td>Doge</td>
                                        <td>{(wallet.dog.at(-1) ?? 0).toFixed(6)}</td>
                                        <td>EA</td>
                                    </tr>
                                    <tr>
                                        <td>Solana</td>
                                        <td>{(wallet.sol.at(-1) ?? 0).toFixed(6)}</td>
                                        <td>EA</td>
                                    </tr>
                                    <tr>
                                        <td>XRP</td>
                                        <td>{(wallet.xrp.at(-1) ?? 0).toFixed(6)}</td>
                                        <td>EA</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </Reorder.Item>
                ))}
            </AnimatePresence>
        </Reorder.Group>
    );
}
