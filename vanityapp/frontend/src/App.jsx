import React, {useEffect, useState} from "react";
import { Routes, Route, Link } from "react-router-dom";
import axios from "axios";
import Home from "./pages/Home";
import Product from "./pages/Product";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import Balance from "./pages/Balance";
import Orders from "./pages/Orders";

const API_BASE = import.meta.env.VITE_API_BASE || "https://vanityapp-backend.onrender.com";

function App(){
  const [user, setUser] = useState(null);
  useEffect(()=> {
    const tg = window.Telegram?.WebApp;
    const initData = tg ? (tg.initData || window.location.search.substring(1)) : window.location.search.substring(1);
    if (initData) {
      axios.post(`${API_BASE}/auth/verify`, { initData }).then(r=> { if (r.data.ok) setUser(r.data.user) }).catch(console.error);
    }
  }, []);
  return (<div>
    <header style={{padding:12,borderBottom:"1px solid #eee"}}><Link to="/">Home</Link> | <Link to="/cart">Cart</Link> | <Link to="/balance">Balance</Link></header>
    <Routes>
      <Route path="/" element={<Home/>} />
      <Route path="/product/:id" element={<Product user={user}/>} />
      <Route path="/cart" element={<Cart/>} />
      <Route path="/checkout" element={<Checkout user={user}/>} />
      <Route path="/balance" element={<Balance user={user}/>} />
      <Route path="/orders" element={<Orders user={user}/>} />
    </Routes>
  </div>);
}
export default App;
