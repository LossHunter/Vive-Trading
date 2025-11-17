import { useEffect, useState } from "react";

export default function WandDB() {
    const [convey, setConvey] = useState([]);

    useEffect(() => {
        const fetchData = async (retries = 3) => {
            try {
                const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/wandb_runs`);
                if (!res.ok) throw new Error("Network response was not ok");
                const data = await res.json();
                setConvey(data);
            } catch (err) {
                console.error("Error fetching W&B runs:", err);
                if (retries > 0) {
                    fetchData(retries - 1);
                }
            }
        };

        fetchData();
    }, []);

    return convey;
}
