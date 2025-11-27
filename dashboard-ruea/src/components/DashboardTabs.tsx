import { NavLink } from "react-router-dom";

export default function DashboardTabs() {
  return (
    <div className="tabbar">
      <div className="container">
        <NavLink to="/dashboards/general" className={({isActive}) => isActive ? "tab active" : "tab"}>
          General
        </NavLink>
        <NavLink to="/dashboards/estadisticas" className={({isActive}) => isActive ? "tab active" : "tab"}>
          Estadísticas
        </NavLink>
      </div>
    </div>
  );
}
