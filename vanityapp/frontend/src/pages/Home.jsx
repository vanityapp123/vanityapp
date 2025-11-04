import React, {useEffect,useState} from "react";
import axios from "axios";
const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";
export default function Home(){
  const [prods,setProds]=useState([]);
  useEffect(()=> axios.get(`${API_BASE}/products`).then(r=>setProds(r.data.products)).catch(console.error),[]);
  return (<div style={{padding:12}}>
    <h2>Products</h2>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))",gap:12}}>
      {prods.map(p=>(<div key={p.id} style={{border:"1px solid #ddd",padding:8}}>
        <img src={p.media_urls[0] || '/placeholder.png'} style={{width:"100%",height:140,objectFit:"cover"}}/>
        <h4>{p.name}</h4><p>{p.city} • {p.price_sol} SOL</p>
        <a href={`/product/${p.id}`}>View</a>
      </div>))}
    </div>
  </div>);
}
