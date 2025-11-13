import { useState, useEffect } from "react";
import Header from "../components/Header"
import "../styles/dashboard.css"
import WanData from "../components/WanDB_Api"
import Loading from "../components/Loading"
import WandChart from "../components/WanChart"
import Footer from "../components/Footer"

export default function WandbRuns() {
    const [loading, setLoading] = useState(true);

    const data = WanData();
    useEffect(() => {
        if (data && data.length > 0) {
            setLoading(false);
        }
    }, [data]);

    return (
        <>
            {loading ? (
            <Loading />
            ) : (
            <div className="dash-frame">
                <Header/>
                <main>
                    <div className="main-left">

                    </div>
                    <div className="main-center">
                        <div className="grid-chart">
                            {data.map((item)=>
                                <div className="chart-component">
                                    <WandChart data={item}/>
                                </div>
                            )}
                        </div>
                    </div>
                </main>
                <Footer />
            </div>
        )}
        </>
    );
}
