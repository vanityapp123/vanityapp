import React,{useEffect,useState} from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";
export default function Product({user}) {
  const {id}=useParams(); const [p,setP]=useState(null); const nav=useNavigate();
  useEffect(()=> axios.get(`${API_BASE}/products/${id}`).then(r=>setP(r.data.product)).catch(console.error),[id]);
  if(!p) return <div>Loading...</div>;
  const add=()=>{ const cart=JSON.parse(localStorage.getItem("cart")||"[]"); cart.push({product_id:p.id,quantity:1}); localStorage.setItem("cart",JSON.stringify(cart)); alert("Added"); }
  return (<div style={{display:"flex",gap:12}}>
    <div style={{flex:1}}>{p.media_urls.map((u,i)=>(<img key={i} src={u} style={{width:"100%",marginBottom:8}}/>))}</div>
    <div style={{flex:1}}><h2>{p.name}</h2><p>{p.description}</p><p>Price: {p.price_sol} SOL</p><button onClick={add}>Add to cart</button><button onClick={()=>nav("/cart")}>Cart</button></div>
  </div>);
}
