import { useEffect, useState } from "react";

//
export default function WandDB() {
    const [convey, setConvey] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL}/api/wandb_runs`) 
        .then((res) => res.json())
        .then((data) => {
            setConvey(data)
        })
        .catch((err) => {
            console.error("Error fetching W&B runs:", err);
            setError(err);
        })
        .finally(() => setLoading(false));
    }, []);

    return { convey, loading, error };
}
