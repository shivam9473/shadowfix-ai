import { useEffect, useState } from "react";
import { getIncident } from "../api";

const TERMINAL = new Set(["awaiting_approval", "deployed", "failed", "halted"]);

export function useIncident(id) {
  const [incident, setIncident] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return undefined;
    let stop = false;

    async function pull() {
      try {
        const data = await getIncident(id);
        if (!stop) {
          setIncident(data);
          setError("");
        }
        return data;
      } catch (err) {
        if (!stop) setError(err.message);
        return null;
      }
    }

    pull();
    const timer = setInterval(async () => {
      const data = await pull();
      if (data && TERMINAL.has(data.status)) clearInterval(timer);
    }, 700);

    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [id]);

  return { incident, error };
}
