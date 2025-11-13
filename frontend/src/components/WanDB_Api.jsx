import { useEffect, useState } from "react";

//
export default function WandDB() {
    const [convey, setConvey] = useState([]);

    useEffect(() => {
    fetch(`${import.meta.env.VITE_GET_URL}/api/wandb_runs`) 
        .then((res) => res.json())
        .then((data) => {
            setConvey(data)
        })
        .catch((err) => {
            console.error("Error fetching W&B runs:", err);
        })
    }, []);

    return convey;
}
