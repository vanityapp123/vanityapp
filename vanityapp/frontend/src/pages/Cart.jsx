import React,{useState} from "react";
import { useNavigate } from "react-router-dom";
export default function Cart(){ const [items,setItems]=useState(JSON.parse(localStorage.getItem("cart")||"[]")); const nav=useNavigate();
  function remove(i){ items.splice(i,1); setItems([...items]); localStorage.setItem("cart",JSON.stringify(items)); }
  return (<div><h2>Cart</h2>{items.length===0? <p>Empty</p>: <>
    <ul>{items.map((it,idx)=><li key={idx}>Product #{it.product_id} × {it.quantity} <button onClick={()=>remove(idx)}>Remove</button></li>)}</ul>
    <button onClick={()=>nav("/checkout")}>Checkout</button></>}</div>);
}
