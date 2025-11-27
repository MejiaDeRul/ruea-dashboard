// src/layouts/TabsOnly.tsx
import { Outlet, NavLink } from "react-router-dom";

export default function TabsOnly() {
  return (
    <>
      <div className="topbar" />

      <div className="tabbar">
        <div className="container">
          <NavLink to="/general" className={({isActive}) => isActive ? "tab active" : "tab"}>General</NavLink>
          <NavLink to="/estadisticas" className={({isActive}) => isActive ? "tab active" : "tab"}>Estadísticas</NavLink>
        </div>
      </div>

      <main className="container py">
        <Outlet />
      </main>
    </>
  );
}
