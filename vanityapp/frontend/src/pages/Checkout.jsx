import React,{useState} from "react";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";
export default function Checkout({user}) {
  const [status,setStatus]=useState(null);
  async function doCheckout(){
    const cart = JSON.parse(localStorage.getItem("cart")||"[]");
    if(!user){ alert("Wait for Telegram auth"); return; }
    try {
      const res = await axios.post(`${API_BASE}/cart/checkout`, { telegram_id: user.telegram_id, items: cart });
      if(!res.data.ok){ setStatus({ok:false, error: res.data.error, balance: res.data.balance, required: res.data.required}); return; }
      localStorage.removeItem("cart"); setStatus({ok:true, orders: res.data.orders, balance: res.data.balance});
      if(window.Telegram?.WebApp) window.Telegram.WebApp.close();
    } catch(e){ setStatus({ok:false, error: e.message}); }
  }
  return (<div><h2>Checkout</h2><button onClick={doCheckout}>Confirm</button>{status && <pre>{JSON.stringify(status,null,2)}</pre>}</div>);
}
