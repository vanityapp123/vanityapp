import React,{useState,useEffect} from "react";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";
export default function Orders({user}) {
  const [orders,setOrders]=useState([]);
  useEffect(()=> { if(!user) return; axios.get(`${API_BASE}/orders/${user.telegram_id}`).then(r=>setOrders(r.data.orders)).catch(console.error); }, [user]);
  return (<div><h2>Orders</h2><ul>{orders.map(o=><li key={o.order_id}>{o.order_id} — {o.product_name || o.product_id} — {o.price || o.price_sol} SOL — {o.status || 'delivered'}</li>)}</ul></div>);
}
