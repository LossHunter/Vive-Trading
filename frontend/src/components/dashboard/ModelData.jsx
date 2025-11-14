import WandChart from "./WanChart.jsx"
import WanData from "../../hooks/WanDB_Api"
import Loading from "../Loading"
import { useState, useEffect } from "react";
import "../../styles/ModelData.css"

export default function ModelData() {
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
                <div className="modeldata">
                    {data.map((item, index) =>
                        <div className="wandcart">
                            <WandChart data ={item}/>
                        </div>
                    )}
                </div>
            )}
        </>
    );
}