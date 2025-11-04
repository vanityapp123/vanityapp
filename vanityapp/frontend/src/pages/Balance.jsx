import React,{useState,useEffect} from "react";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";
export default function Balance({user}) {
  const [data,setData]=useState(null);
  useEffect(()=> { if(!user) return; axios.get(`${API_BASE}/user/${user.telegram_id}/balance`).then(r=>setData(r.data)).catch(console.error); }, [user]);
  if(!user) return <div>Authenticating...</div>;
  if(!data) return <div>Loading...</div>;
  return (<div><h2>Balance</h2><p>Balance: {data.user.balance_sol} SOL</p><p>Deposit address: <code>{data.deposit_address}</code> <button onClick={()=>navigator.clipboard.writeText(data.deposit_address)}>Copy</button></p></div>);
}
